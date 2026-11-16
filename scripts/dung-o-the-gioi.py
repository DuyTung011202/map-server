#!/usr/bin/env python3
"""Dựng ô nền THẾ GIỚI ở zoom thấp, để zoom ra không thấy Việt Nam trôi giữa khoảng trắng.

    python scripts/dung-o-the-gioi.py              # dựng data/tiles/the-gioi.pmtiles
    python scripts/dung-o-the-gioi.py --self-check # assert, không dựng

VẤN ĐỀ NÓ GIẢI: `vietnam.pmtiles` là bản trích Việt Nam, bounds chỉ từ
102.1°Đ. Zoom ra tới z6 thì khung nhìn trải từ 95.6°Đ — Lào, Thái Lan, Trung
Quốc, Campuchia trống trơn, không ranh giới, không tên nước. Biển vẫn xanh vì
lớp water-polygons là toàn cầu, nên nhìn ra như Việt Nam trôi trên nền kem.
Với một bản đồ để TRANG KHÁC NHÚNG thì ai cũng sẽ zoom ra, và cảnh đó đọc ra
là "bản đồ hỏng".

CÁCH LÀM: chạy Planetiler lần nữa với bounds cả thế giới nhưng CHỈ tới z6.
Dữ liệu OSM vẫn chỉ Việt Nam; thứ phủ toàn cầu là các lớp sinh từ Natural
Earth — ranh giới quốc gia, tên nước, thành phố lớn, sông hồ lớn. Nguồn NE đã
nằm sẵn trong data/osm, không tải thêm gì.

VÌ SAO PHẢI CHẶN Ở z6, KHÔNG DỰNG THẲNG CẢ THẾ GIỚI TỚI z14: lớp nước là
toàn cầu, mà đại dương chiếm 70% bề mặt. Dựng tới z14 thì riêng thư mục ô
phải có 4^14 ≈ 268 triệu mục — không phải tệp to, mà là bất khả thi. Tới z6
thì nhiều nhất 5.461 ô.

Tệp này rất ít khi phải dựng lại: nguồn của nó là Natural Earth, cỡ vài năm
mới đổi một lần. Đừng ghép vào việc cập nhật OSM hàng tuần.
"""

import subprocess
import sys
from pathlib import Path

from pmtiles_chung import doc_header, mo_ta

GOC = Path(__file__).resolve().parent.parent
RA = GOC / "data" / "tiles" / "the-gioi.pmtiles"
PLANETILER = GOC / "data" / "planetiler.jar"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# -85..85 chứ không phải -90..90: ngoài khoảng đó phép chiếu Web Mercator
# giãn ra vô tận, không có ô nào.
BOUNDS = "-180,-85,180,85"
# z8 chứ không phải z6: phóng to ra ngoài biên giới Việt Nam ở z7–8 là chuyện
# thường (xem biên Lào, Campuchia, hay Biển Đông), mà dừng ở z6 thì chỗ đó
# trống trơn. Cả thế giới tới z8 là 87.381 ô — chịu được thoải mái.
#
# Vẫn KHÔNG dựng sâu hơn: lớp nước là toàn cầu và đại dương chiếm 70% bề mặt,
# nên số ô nhân 4 mỗi bậc. Tới z14 là 4^14 ~ 268 triệu mục thư mục ô, bất khả
# thi — đó là ngưỡng thật, không phải thận trọng thừa.
MAXZOOM = 8
RAM = "4g"


def lenh_planetiler() -> list[str]:
    return ["java", f"-Xmx{RAM}", "-jar", str(PLANETILER),
            "--download", "--area=vietnam",
            f"--bounds={BOUNDS}",
            f"--maxzoom={MAXZOOM}",
            "--http-timeout=120s", "--http-retries=5",
            f"--output={RA}", f"--download-dir={GOC / 'data' / 'osm'}",
            "--force"]


def dung() -> None:
    if not PLANETILER.is_file():
        sys.exit(f"Thiếu {PLANETILER.relative_to(GOC)}")
    print(f"Dựng nền thế giới z0–{MAXZOOM}, bounds {BOUNDS}")
    if subprocess.run(lenh_planetiler(), cwd=GOC).returncode != 0:
        sys.exit("Planetiler hỏng")
    h = doc_header(RA)
    print(f"Đã ghi {RA.relative_to(GOC)} — {mo_ta(h)}")
    for l in kiem(h):
        print(f"  CẢNH BÁO: {l}")


def kiem(h: dict) -> list[str]:
    """Trả lý do tệp không dùng được. Rỗng là đạt."""
    loi = []
    if h["kieu_o"] != 1:
        loi.append(f"kiểu ô {h['kieu_o']}, cần 1 (MVT vector)")
    if h["maxzoom"] > 8:
        loi.append(f"maxzoom {h['maxzoom']} — quá sâu cho nền thế giới, "
                   "số ô sẽ bùng nổ")
    lon1, lat1, lon2, lat2 = h["bounds"]
    # Phải phủ RỘNG HƠN Việt Nam nhiều, không thì nó vô dụng — đây chính là
    # thứ phải kiểm, vì Planetiler mặc định cắt theo bbox của bản trích.
    if not (lon1 <= -170 and lon2 >= 170):
        loi.append(f"bounds {h['bounds']} không phủ cả thế giới — "
                   "có phải --bounds bị bỏ quên không?")
    if h["so_o"] < 100:
        loi.append(f"chỉ có {h['so_o']} ô")
    return loi


def tu_kiem_tra() -> int:
    loi = 0

    def kd(dk, ten):
        nonlocal loi
        if dk:
            print(f"đúng: {ten}")
        else:
            loi += 1
            print(f"SAI: {ten}")

    lenh = lenh_planetiler()
    kd(f"--bounds={BOUNDS}" in lenh, "lệnh dựng có --bounds cả thế giới")
    kd(f"--maxzoom={MAXZOOM}" in lenh, f"lệnh dựng chặn ở z{MAXZOOM}")
    kd(MAXZOOM <= 8, f"z{MAXZOOM} đủ nông để số ô không bùng nổ "
                     f"(nhiều nhất {sum(4**z for z in range(MAXZOOM + 1)):,} ô)")

    lanh = {"kieu_o": 1, "maxzoom": 6, "bounds": [-180.0, -85.0, 180.0, 85.0],
            "so_o": 5000, "so_muc": 3000, "minzoom": 0, "kich_thuoc": 9_000_000}
    kd(kiem(lanh) == [], "một tệp nền thế giới lành thì đạt")

    # Lỗi dễ mắc nhất: quên --bounds, Planetiler cắt theo bbox Việt Nam và ta
    # được một tệp trông bình thường mà vô dụng.
    vn = dict(lanh, bounds=[102.09, 7.38, 114.64, 23.40])
    kd(any("bounds" in l for l in kiem(vn)),
       "bắt được tệp chỉ phủ Việt Nam (quên --bounds)")
    kd(any("maxzoom" in l for l in kiem(dict(lanh, maxzoom=14))),
       "bắt được maxzoom quá sâu")
    kd(kiem(dict(lanh, kieu_o=2)) != [], "bắt được tệp không phải MVT")

    if RA.is_file():
        h = doc_header(RA)
        kd(kiem(h) == [], f"tệp đã dựng đạt ({mo_ta(h)})")
    else:
        print(f"bỏ qua: chưa dựng {RA.name}, chỉ kiểm phần logic")

    print("Tự kiểm tra: tất cả đúng" if loi == 0 else f"Tự kiểm tra: {loi} lỗi")
    return loi


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(1 if tu_kiem_tra() else 0)
    dung()
