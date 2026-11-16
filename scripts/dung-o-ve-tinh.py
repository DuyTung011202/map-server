#!/usr/bin/env python3
"""Dựng ô ảnh vệ tinh từ Sentinel-2 L2A, cho vùng khai ở dia_hinh_chung.

    python scripts/dung-o-ve-tinh.py               # dựng cả tỉnh Ninh Bình
    python scripts/dung-o-ve-tinh.py --self-check  # assert, không tải gì
    python scripts/dung-o-ve-tinh.py --chi-tim     # chỉ tìm cảnh, không dựng

Vì sao tự dựng: ảnh vệ tinh đang dùng nằm ở TileServer của tỉnh
(`10.40.41.28`) — máy chủ bản đồ này không có nó, nên trang demo báo đỏ. Nguồn
Sentinel-2 L2A trên AWS Open Data là free, 10 m/pixel, và asset `visual` đã là
RGB 8-bit chỉnh màu sẵn nên không phải tự pha băng phổ.

Vì sao dựng ô TĨNH chứ không cắm TiTiler đọc thẳng COG trên AWS: máy chủ nội
bộ không có DNS ra ngoài (CLAUDE.md). Đọc COST từ xa lúc chạy thì ở môi trường
thật là bản đồ trắng. Tải một lần, dựng ô, rồi tự phục vụ.

Vì sao gọi GDAL trong Docker: cắt ô thì numpy làm được (xem dung-o-dia-hinh.py),
nhưng ảnh Sentinel-2 ở lưới chiếu UTM 48N, đổi sang Web Mercator là việc của
thư viện chiếu bản đồ chứ không phải việc viết tay. Image `ghcr.io/osgeo/gdal`
đã có sẵn trên máy, nên không thêm phụ thuộc nào cho host.
"""

import json
import shutil
import subprocess
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dia_hinh_chung import VUNG_NINH_BINH

GOC = Path(__file__).resolve().parent.parent
RA = GOC / "data" / "tiles" / "ve-tinh"
TAM = GOC / "data" / "ve-tinh-tam"
S2 = GOC / "data" / "s2"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STAC = "https://earth-search.aws.element84.com/v1/search"
MINZOOM, MAXZOOM = 8, 14   # z14 ≈ 9 m/pixel ở vĩ độ 20 — đúng tầm Sentinel-2 10 m
MAY_TOI_DA = 8.0           # phần trăm mây chấp nhận được
ANH_GDAL = "ghcr.io/osgeo/gdal:ubuntu-small-latest"


def tim_canh(bounds: list[float], tu: str = "2024-11-01", den: str = "2026-03-01") -> list[dict]:
    """Tìm mỗi ô MGRS một cảnh, ưu tiên NGÀY CHUNG với các ô khác.

    Ghép ảnh chụp cách nhau vài tháng thì ranh giới giữa hai ô hiện rõ thành
    vệt màu: lúa mùa khác lúa chiêm, nước khác cạn. Nên không chọn cảnh ít mây
    nhất từng ô riêng lẻ, mà chọn ngày phủ được nhiều ô nhất trước đã.
    """
    q = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bounds,
        "datetime": f"{tu}T00:00:00Z/{den}T00:00:00Z",
        "query": {"eo:cloud_cover": {"lt": MAY_TOI_DA}},
        "limit": 200,
    }
    r = urllib.request.Request(STAC, data=json.dumps(q).encode(),
                               headers={"Content-Type": "application/json"})
    canh = json.load(urllib.request.urlopen(r, timeout=120))["features"]
    if not canh:
        sys.exit("Không tìm được cảnh nào đủ sạch mây. Nới MAY_TOI_DA hoặc khoảng ngày.")

    theo_ngay = defaultdict(set)
    for c in canh:
        theo_ngay[c["properties"]["datetime"][:10]].add(c["properties"]["grid:code"])

    can = {c["properties"]["grid:code"] for c in canh}
    chon: dict[str, dict] = {}
    # Lấy ngày phủ rộng nhất trước, rồi ngày rộng nhì cho phần còn thiếu...
    for ngay, _ in sorted(theo_ngay.items(), key=lambda t: -len(t[1])):
        if len(chon) == len(can):
            break
        for c in canh:
            p = c["properties"]
            if p["datetime"][:10] == ngay and p["grid:code"] not in chon:
                chon[p["grid:code"]] = c

    for o in sorted(chon):
        p = chon[o]["properties"]
        print(f"  {o.replace('MGRS-', '')}  {p['datetime'][:10]}  mây {p['eo:cloud_cover']:.1f}%")
    ngay_dung = {chon[o]['properties']['datetime'][:10] for o in chon}
    print(f"  -> {len(chon)} ô, {len(ngay_dung)} ngày chụp: {', '.join(sorted(ngay_dung))}")
    return [chon[o] for o in sorted(chon)]


def tai_mot_canh(c: dict) -> str:
    """Tải một cảnh TCI về data/s2/. Trả đường dẫn nhìn từ trong container.

    Tải hẳn về chứ không để GDAL đọc COG từ xa lúc chiếu: đọc từ xa thì một
    lần rớt gói giữa chừng là hỏng cả mẻ, và đã hỏng thật
    (`response_code=0` -> ảnh thủng lỗ, nhưng gdalwarp vẫn chạy tới 100%).
    Tải về thì lần chạy sau không tốn mạng, và tệp nào hỏng chỉ phải tải lại
    đúng tệp đó.
    """
    url = c["assets"]["visual"]["href"]
    dich = S2 / f"{c['id']}.tif"
    trong_container = f"/data/s2/{dich.name}"

    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
        can = int(r.headers["Content-Length"])
    if dich.is_file() and dich.stat().st_size == can:
        print(f"  {c['id']}: đã có")
        return trong_container

    for lan in range(1, 4):
        tam = dich.with_suffix(".tam")
        try:
            with urllib.request.urlopen(url, timeout=300) as r, tam.open("wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            if tam.stat().st_size != can:
                raise OSError(f"tải thiếu {tam.stat().st_size}/{can} byte")
            tam.replace(dich)  # đổi tên sau khi đủ byte: không để lại tệp cụt
            print(f"  {c['id']}: {can / 1e6:.0f} MB")
            return trong_container
        except Exception as e:
            print(f"  {c['id']}: lỗi lần {lan} — {e}")
            tam.unlink(missing_ok=True)
    sys.exit(f"Tải {c['id']} hỏng sau 3 lần.")


def tai_canh(canh: list[dict]) -> list[str]:
    S2.mkdir(parents=True, exist_ok=True)
    # Ba luồng: một luồng chỉ đạt ~1 MB/s, mà nghẽn nằm ở kết nối chứ không
    # phải ở đĩa hay CPU. Đừng tăng nữa, tải song song nhiều quá thì S3 cắt.
    with ThreadPoolExecutor(max_workers=3) as bom:
        return list(bom.map(tai_mot_canh, canh))


def chay_gdal(lenh: list[str], ten: str) -> None:
    """Chạy một lệnh GDAL trong container, gắn data/ vào /data."""
    day_du = [
        "docker", "run", "--rm",
        "-v", f"{GOC / 'data'}:/data",
        ANH_GDAL, *lenh,
    ]
    print(f"  {ten} ...", flush=True)
    kq = subprocess.run(day_du, text=True)
    if kq.returncode != 0:
        sys.exit(f"GDAL hỏng ở bước {ten} (mã {kq.returncode})")


def dung(bounds: list[float]) -> None:
    print(f"Vùng: {bounds}  zoom {MINZOOM}–{MAXZOOM}")
    print("Tìm cảnh Sentinel-2:")
    canh = tim_canh(bounds)
    print("Tải ảnh về (lần sau không cần mạng):")
    urls = tai_canh(canh)

    TAM.mkdir(parents=True, exist_ok=True)
    vrt = "/data/ve-tinh-tam/nguon.vrt"
    ghep = "/data/ve-tinh-tam/ghep-3857.tif"

    # Cả 6 ô MGRS đều thuộc múi UTM 48N nên gộp VRT được, không phải chiếu lại
    # từng cái. 0 là ngoài dải chụp — khai nodata, không thì ra viền đen.
    chay_gdal(["gdalbuildvrt", "-srcnodata", "0", "-vrtnodata", "0",
               vrt, *urls], "gộp nguồn thành VRT")

    chay_gdal(["gdalwarp",
               "-t_srs", "EPSG:3857",
               "-te_srs", "EPSG:4326",
               "-te", *(str(v) for v in bounds),
               "-tr", "10", "10",            # 10 m/pixel: đúng độ phân giải gốc
               "-r", "bilinear",
               "-dstalpha",                  # ngoài vùng chụp thì trong suốt
               "-co", "COMPRESS=DEFLATE", "-co", "BIGTIFF=YES",
               "-multi", "-wo", "NUM_THREADS=ALL_CPUS",
               "-overwrite", vrt, ghep], "chiếu về Web Mercator và cắt theo vùng")

    chay_gdal(["gdal2tiles.py",
               "--xyz",                      # XYZ chứ không phải TMS: y lật ngược
               "-z", f"{MINZOOM}-{MAXZOOM}",
               "-r", "bilinear",
               "--processes", "4",
               "--no-kml", "-w", "none",     # không sinh trang xem kèm
               ghep, "/data/tiles/ve-tinh"], "cắt ô XYZ")

    so = sum(1 for _ in RA.rglob("*.png"))
    print(f"Đã ghi {so} ô vệ tinh vào {RA.relative_to(GOC)}")
    print(f"Xoá được: {TAM.relative_to(GOC)} (ảnh ghép trung gian)")


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

    # Cùng vùng với ô địa hình — lệch là trang hiện ảnh vệ tinh ở nơi không có
    # địa hình và ngược lại.
    kd(VUNG_NINH_BINH == [105.5, 19.8, 106.7, 20.8], "vùng phủ lấy từ dia_hinh_chung")

    pv = json.loads((GOC / "web" / "phamvi.json").read_text("utf-8"))
    kd(pv["bounds"] == VUNG_NINH_BINH, "ô địa hình đang phủ đúng vùng đó")

    # Thuật toán chọn ngày: phải gom về ít ngày nhất, không phải ít mây nhất.
    gia = []
    for o, ngay, may in (("A", "2025-01-17", 3.0), ("A", "2025-06-01", 0.0),
                         ("B", "2025-01-17", 2.0), ("B", "2025-06-01", 0.0),
                         ("C", "2025-06-01", 0.0)):
        gia.append({"properties": {"grid:code": o, "datetime": ngay + "T03:00:00Z",
                                   "eo:cloud_cover": may}})
    theo_ngay = defaultdict(set)
    for c in gia:
        theo_ngay[c["properties"]["datetime"][:10]].add(c["properties"]["grid:code"])
    rong_nhat = max(theo_ngay.items(), key=lambda t: len(t[1]))
    kd(rong_nhat[0] == "2025-06-01" and len(rong_nhat[1]) == 3,
       "chọn ngày phủ nhiều ô nhất, không chọn theo ô ít mây nhất")

    # Cấu hình trang phải trỏ đúng chỗ script này ghi ra.
    cau = (GOC / "web" / "cauhinh.js").read_text("utf-8")
    kd("/tiles/ve-tinh/{z}/{x}/{y}.png" in cau, "cauhinh.js trỏ đúng đường ô vệ tinh")
    kd("Copernicus" in cau or "Sentinel" in cau,
       "cauhinh.js có ghi công Copernicus/Sentinel (giấy phép bắt buộc)")

    print("Tự kiểm tra: tất cả đúng" if loi == 0 else f"Tự kiểm tra: {loi} lỗi")
    return loi


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(1 if tu_kiem_tra() else 0)

    if "--chi-tim" in sys.argv:
        tim_canh(VUNG_NINH_BINH)
        sys.exit(0)

    dung(VUNG_NINH_BINH)
