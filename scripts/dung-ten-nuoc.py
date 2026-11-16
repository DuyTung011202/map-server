#!/usr/bin/env python3
"""Trích tên nước và vùng Việt Nam từ Natural Earth, để zoom ra có bản đồ thế giới.

    python scripts/dung-ten-nuoc.py              # ghi web/the-gioi/*.json
    python scripts/dung-ten-nuoc.py --self-check # assert, không cần nguồn

VÌ SAO CẦN: `the-gioi.pmtiles` có ranh giới và biển toàn cầu, nhưng mục
`place` của nó chỉ chứa ĐÚNG MỘT nước — Việt Nam. Lý do: Planetiler lấy nhãn
địa danh từ OSM, mà đầu vào OSM của ta là bản trích Việt Nam. Zoom ra thì có
đường biên các nước mà không nước nào có tên.

Natural Earth giải đúng việc này và ta đã có sẵn nguồn trong
`data/osm/natural_earth_vector.sqlite.zip`:

  - cột `name_vi`  -> tên nước BẰNG TIẾNG VIỆT, không phải tự dịch
  - cột `label_x`, `label_y` -> chỗ đặt nhãn do người làm bản đồ chọn, không
    phải trọng tâm hình học (trọng tâm Việt Nam rơi ra ngoài biển)
  - cột `GEOMETRY` -> WKB thuần, đọc bằng struct, không cần GDAL

Ra hai tệp nhỏ, nhúng thẳng vào style như dữ liệu chủ quyền:

  web/the-gioi/ten-nuoc.json   177 điểm nhãn
  web/the-gioi/viet-nam.json   vùng Việt Nam, để tô khác màu các nước khác

LƯU Ý CHỦ QUYỀN: vùng Việt Nam của Natural Earth KHÔNG gồm Hoàng Sa và
Trường Sa. Vì vậy lớp tô này không được coi là "ranh giới Việt Nam" — nó chỉ
là màu nền cho phần đất liền. Lớp chủ quyền vẫn nằm ở cuối style và vẫn là
nguồn sự thật duy nhất về hai quần đảo. Đừng đổi thứ tự đó.
"""

import json
import os
import struct
import sys
import zipfile
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
ZIP_NE = GOC / "data" / "osm" / "natural_earth_vector.sqlite.zip"
TAM_NE = GOC / "data" / "ne.sqlite"
RA_TEN = GOC / "web" / "the-gioi" / "ten-nuoc.json"
RA_VN = GOC / "web" / "the-gioi" / "viet-nam.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 50m đủ mượt cho zoom 0–6 mà vẫn nhỏ; 110m thì Việt Nam chỉ còn 44 điểm,
# nhìn ra hình răng cưa.
BANG = "ne_50m_admin_0_countries"
BANG_DU_PHONG = "ne_110m_admin_0_countries"


# ------------------------------------------------------------------- WKB
def doc_wkb(b: bytes) -> list:
    """Đọc WKB Polygon (3) hoặc MultiPolygon (6). Trả danh sách polygon.

    Chỉ làm đúng hai kiểu đó — Natural Earth admin_0 không có kiểu nào khác.
    Gặp kiểu lạ thì ném lỗi chứ không đoán.
    """
    vt = 0

    def lay(dang: str, n: int):
        nonlocal vt
        kq = struct.unpack_from(dang, b, vt)
        vt += n
        return kq

    (endian,) = lay("<B", 1)
    dau = "<" if endian == 1 else ">"
    (kieu,) = lay(dau + "I", 4)

    def doc_polygon() -> list:
        (so_vong,) = lay(dau + "I", 4)
        vong = []
        for _ in range(so_vong):
            (so_diem,) = lay(dau + "I", 4)
            toa_do = lay(dau + f"{so_diem * 2}d", so_diem * 16)
            vong.append([[round(toa_do[i], 5), round(toa_do[i + 1], 5)]
                         for i in range(0, len(toa_do), 2)])
        return vong

    if kieu == 3:
        return [doc_polygon()]
    if kieu == 6:
        (so_pg,) = lay(dau + "I", 4)
        ra = []
        for _ in range(so_pg):
            lay("<B", 1)          # endian của từng polygon con
            lay(dau + "I", 4)     # kiểu, luôn là 3
            ra.append(doc_polygon())
        return ra
    raise ValueError(f"WKB kiểu {kieu}, chỉ đọc được Polygon(3) và MultiPolygon(6)")


# ------------------------------------------------------------------ nguồn
def mo_ne():
    import sqlite3
    if not TAM_NE.is_file():
        if not ZIP_NE.is_file():
            sys.exit(f"Thiếu {ZIP_NE.relative_to(GOC)}. Chạy dung-o-the-gioi.py trước.")
        print("  giải nén Natural Earth (một lần) ...", flush=True)
        with zipfile.ZipFile(ZIP_NE) as z:
            ten = next(n for n in z.namelist() if n.endswith(".sqlite"))
            with z.open(ten) as s, TAM_NE.open("wb") as d:
                while True:
                    khoi = s.read(1 << 22)
                    if not khoi:
                        break
                    d.write(khoi)
    c = sqlite3.connect(TAM_NE)
    co = {r[0] for r in c.execute(
        "select name from sqlite_master where type='table'")}
    return c, (BANG if BANG in co else BANG_DU_PHONG)


def dung() -> None:
    c, bang = mo_ne()
    print(f"  dùng bảng {bang}")

    RA_TEN.parent.mkdir(parents=True, exist_ok=True)

    # --- nhãn tên nước ---
    hang = c.execute(
        f"select name_vi, name_en, name, label_x, label_y, iso_a2 from {bang}"
    ).fetchall()
    diem = []
    for vi, en, ten, x, y, iso in hang:
        if x is None or y is None:
            continue
        diem.append({
            "type": "Feature",
            "properties": {"ten": vi or en or ten, "iso": iso},
            "geometry": {"type": "Point", "coordinates": [round(x, 4), round(y, 4)]},
        })
    RA_TEN.write_text(json.dumps(
        {"type": "FeatureCollection", "features": diem}, ensure_ascii=False), "utf-8")
    print(f"  {RA_TEN.relative_to(GOC)} — {len(diem)} nước "
          f"({RA_TEN.stat().st_size / 1024:.0f} KB)")

    # --- vùng Việt Nam ---
    g = c.execute(f"select GEOMETRY from {bang} where iso_a2='VN'").fetchone()
    if not g:
        sys.exit("Không tìm thấy Việt Nam trong Natural Earth")
    pgs = doc_wkb(g[0])
    vn = {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {"ten": "Việt Nam"},
        "geometry": {"type": "MultiPolygon", "coordinates": pgs},
    }]}
    RA_VN.write_text(json.dumps(vn, ensure_ascii=False), "utf-8")
    so_diem = sum(len(v) for p in pgs for v in p)
    print(f"  {RA_VN.relative_to(GOC)} — {len(pgs)} vùng, {so_diem} điểm "
          f"({RA_VN.stat().st_size / 1024:.0f} KB)")
    print(f"  Xoá được: {TAM_NE.relative_to(GOC)} (nguồn giải nén, 850 MB)")


# -------------------------------------------------------------- tự kiểm tra
def tu_kiem_tra() -> int:
    loi = 0

    def kd(dk, ten):
        nonlocal loi
        if dk:
            print(f"đúng: {ten}")
        else:
            loi += 1
            print(f"SAI: {ten}")

    # WKB Polygon một vòng, bốn điểm — dựng tay để assert không cần nguồn.
    diem = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]
    b = struct.pack("<BII", 1, 3, 1) + struct.pack("<I", len(diem))
    for x, y in diem:
        b += struct.pack("<dd", x, y)
    ra = doc_wkb(b)
    kd(len(ra) == 1 and len(ra[0]) == 1 and len(ra[0][0]) == 4,
       "đọc được WKB Polygon một vòng")
    kd(ra[0][0][1] == [1.0, 0.0], "toạ độ đúng thứ tự lon, lat")

    # MultiPolygon gồm hai polygon trên.
    mb = struct.pack("<BII", 1, 6, 2) + b + b
    ra2 = doc_wkb(mb)
    kd(len(ra2) == 2, "đọc được WKB MultiPolygon hai vùng")

    try:
        doc_wkb(struct.pack("<BI", 1, 1))
        kd(False, "từ chối WKB kiểu không hỗ trợ")
    except ValueError:
        kd(True, "từ chối WKB kiểu không hỗ trợ")

    if RA_TEN.is_file():
        d = json.loads(RA_TEN.read_text("utf-8"))
        ten = {f["properties"]["ten"] for f in d["features"]}
        kd(len(d["features"]) > 150, f"có {len(d['features'])} nước")
        kd({"Lào", "Thái Lan", "Campuchia", "Trung Quốc"} <= ten,
           "tên nước láng giềng bằng tiếng Việt")
    else:
        print(f"bỏ qua: chưa dựng {RA_TEN.name}, chỉ kiểm phần logic")

    print("Tự kiểm tra: tất cả đúng" if loi == 0 else f"Tự kiểm tra: {loi} lỗi")
    return loi


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(1 if tu_kiem_tra() else 0)
    dung()
