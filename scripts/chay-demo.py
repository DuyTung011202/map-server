#!/usr/bin/env python3
"""Máy chủ CHỈ DÙNG KHI PHÁT TRIỂN: phục vụ web/ và tự sinh ô bản đồ giả.

Lý do tồn tại: ô thật nằm ở đường cùng gốc /tiles/... phía sau nginx, nên mở
web/index.html bằng localhost trần thì không có ô nào và không kiểm được gì.
Tệp này sinh ô tại chỗ để xem trang chạy đúng không — không gọi mạng ngoài,
không lấy ô của ai.

    python scripts/chay-demo.py          # http://localhost:8080
    python scripts/chay-demo.py --self-check

Cố tình KHÔNG giả lập /chu-quyen/chu-quyen-dao.json: thiếu lớp chủ quyền thì
trang phải hiện cảnh báo đỏ, và đó là thứ cần nhìn thấy khi chạy thử.
"""

import io
import json
import math
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw

# Dùng chung với scripts/dung-o-dia-hinh.py: ô giả và ô thật phải mã hoá độ
# cao giống hệt nhau, không thì đổi nguồn là mặt đất đổi hình.
from dia_hinh_chung import ma_hoa_terrarium, o_sang_toa_do

if hasattr(sys.stdout, "reconfigure"):  # console Windows mặc định cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parent.parent / "web"
O = re.compile(r"^/tiles/(nen|ve-tinh|dia-hinh|do-doc)/(\d+)/(\d+)/(\d+)\.png$")

# Quả đồi giả, đặt quanh Hoa Lư để trùng với vị trí mở đầu của trang.
DOI_LON, DOI_LAT, DOI_CAO, DOI_RONG = 105.93, 20.25, 900.0, 0.18

# ponytail: đếm lượt gọi trong RAM, đủ để kiểm hiển thị X-Tile-Cache HIT/MISS.
_da_goi: set[str] = set()

PHAM_VI_MAC_DINH = {
    "phien_ban": 1,
    "ma_hoa": "terrarium",
    "bounds": [DOI_LON - DOI_RONG, DOI_LAT - DOI_RONG,
               DOI_LON + DOI_RONG, DOI_LAT + DOI_RONG],
    "minzoom": 8,
    "maxzoom": 12,
    "nguon": "dữ liệu giả của máy chủ dev",
}


def pham_vi() -> dict:
    """Dùng web/phamvi.json thật nếu có, không thì bịa tạm.

    Trang đọc bounds và minzoom/maxzoom từ đây để đặt vào source lúc tạo map,
    nên phục vụ đúng tệp thật là cách duy nhất kiểm được đường đi đó.
    """
    that = GOC / "phamvi.json"
    if that.is_file():
        return json.loads(that.read_text("utf-8"))
    return PHAM_VI_MAC_DINH


def o_trong_pham_vi(z: int, x: int, y: int) -> bool:
    pv = pham_vi()
    if not (pv.get("minzoom", 0) <= z <= pv.get("maxzoom", 22)):
        return False
    b = pv.get("bounds")
    if not (isinstance(b, list) and len(b) == 4):
        return True
    lon1, lat1, lon2, lat2 = o_sang_toa_do(z, x, y)
    return not (lon2 < b[0] or lon1 > b[2] or lat1 < b[1] or lat2 > b[3])


def do_cao(lon: float, lat: float) -> float:
    """Độ cao giả: một quả đồi Gauss cộng gợn sóng cho có dốc mà xem."""
    d2 = ((lon - DOI_LON) ** 2 + (lat - DOI_LAT) ** 2) / DOI_RONG**2
    doi = DOI_CAO * math.exp(-d2)
    gon = 40.0 * math.sin(lon * 90) * math.cos(lat * 90)
    return doi + gon


def o_dia_hinh(z: int, x: int, y: int) -> Image.Image:
    """Ô raster-dem thật sự mã hoá độ cao, để kiểm được setTerrain và hillshade.

    Nội suy ĐỘ CAO rồi mới mã hoá, không bao giờ resize ảnh đã mã hoá:
    bilinear nội suy riêng từng kênh R/G/B làm vỡ mã terrarium ở biên byte,
    ra mặt đất bậc thang. Lỗi này áp dụng cho mọi pipeline terrain-RGB, kể cả
    pipeline thật ở Phase 3 — đừng resize tệp terrain đã mã hoá.
    """
    lon1, lat1, lon2, lat2 = o_sang_toa_do(z, x, y)
    # ponytail: lấy mẫu thưa 65x65 rồi nội suy, đủ mượt mà vẫn nhanh.
    n = 65
    tho = Image.new("F", (n, n))
    px = tho.load()
    for j in range(n):
        lat = lat1 + (lat2 - lat1) * j / (n - 1)
        for i in range(n):
            lon = lon1 + (lon2 - lon1) * i / (n - 1)
            px[i, j] = do_cao(lon, lat)

    cao = tho.resize((256, 256), Image.BILINEAR).load()
    anh = Image.new("RGB", (256, 256))
    ra = anh.load()
    for j in range(256):
        for i in range(256):
            ra[i, j] = ma_hoa_terrarium(cao[i, j])
    return anh


def o_luoi(z: int, x: int, y: int, nen: tuple, vien: tuple, nhan: str) -> Image.Image:
    """Ô có khung và nhãn toạ độ — đủ để thấy ô nào vào đúng chỗ nào."""
    anh = Image.new("RGBA", (256, 256), nen)
    ve = ImageDraw.Draw(anh)
    ve.rectangle([0, 0, 255, 255], outline=vien, width=1)
    for k in (64, 128, 192):
        ve.line([(k, 0), (k, 255)], fill=vien)
        ve.line([(0, k), (255, k)], fill=vien)
    ve.text((10, 10), f"{nhan}\n{z}/{x}/{y}", fill=vien)
    return anh


def o_do_doc(z: int, x: int, y: int) -> Image.Image:
    """Lớp phủ nửa trong suốt, đậm ở nơi dốc — kiểm thanh độ mờ."""
    lon1, lat1, lon2, lat2 = o_sang_toa_do(z, x, y)
    n = 64
    anh = Image.new("RGBA", (n, n))
    px = anh.load()
    dlon, dlat = (lon2 - lon1) / n, (lat2 - lat1) / n
    for j in range(n):
        lat = lat1 + dlat * (j + 0.5)
        for i in range(n):
            lon = lon1 + dlon * (i + 0.5)
            dx = do_cao(lon + dlon, lat) - do_cao(lon, lat)
            dy = do_cao(lon, lat + dlat) - do_cao(lon, lat)
            doc = min(1.0, math.hypot(dx, dy) / 60.0)
            px[i, j] = (int(40 + 215 * doc), int(200 * (1 - doc)), 60, int(210 * doc))
    return anh.resize((256, 256), Image.BILINEAR)


def sinh_o(loai: str, z: int, x: int, y: int) -> bytes:
    if loai == "dia-hinh":
        anh = o_dia_hinh(z, x, y)
    elif loai == "do-doc":
        anh = o_do_doc(z, x, y)
    elif loai == "ve-tinh":
        anh = o_luoi(z, x, y, (34, 48, 36, 255), (92, 120, 92, 255), "VE TINH (gia)")
    else:
        anh = o_luoi(z, x, y, (238, 236, 230, 255), (176, 170, 158, 255), "NEN PHO (gia)")
    bo = io.BytesIO()
    anh.save(bo, "PNG")
    return bo.getvalue()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(GOC), **kw)

    def log_message(self, fmt, *a):
        if "/tiles/" not in (self.path or ""):
            super().log_message(fmt, *a)

    def do_GET(self):
        if self.path == "/tiles/dia-hinh/phamvi.json":
            return self._json(pham_vi())

        if self.path.endswith(".pmtiles"):
            return self._tep_range(
                GOC.parent / "data" / "tiles" / Path(self.path).name,
                "application/octet-stream",
            )

        m = O.match(self.path)
        if m:
            loai, z, x, y = m.group(1), *map(int, m.groups()[1:])
            # Ô địa hình và độ dốc chỉ có trong phạm vi khai ở phamvi.json.
            # Trả 404 thật ở ngoài vùng cho giống máy chủ thật — và để thấy
            # rằng MapLibre có bounds thì không thèm gọi ra ngoài vùng.
            if loai in ("dia-hinh", "do-doc") and not o_trong_pham_vi(z, x, y):
                return self.send_error(404)
            noi_dung = sinh_o(loai, z, x, y)
            lan_dau = self.path not in _da_goi
            _da_goi.add(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(noi_dung)))
            self.send_header("X-Tile-Cache", "MISS" if lan_dau else "HIT")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(noi_dung)

        return super().do_GET()

    def _tep_range(self, duong: Path, kieu: str):
        """Phục vụ một tệp lớn có hỗ trợ HTTP range request.

        PMTiles là MỘT tệp duy nhất chứa toàn bộ ô; trình duyệt đọc từng lát
        bằng header Range thay vì tải cả tệp. SimpleHTTPRequestHandler không
        biết Range — nó trả 200 kèm cả tệp, và thư viện PMTiles sẽ đọc nhầm.
        Nên phải tự trả 206.
        """
        if not duong.is_file():
            # ASCII thôi: dòng trạng thái HTTP mã hoá latin-1, chữ có dấu làm
            # vỡ kết nối và client nhận "không phản hồi" chứ không phải 404.
            return self.send_error(404, "not built yet")

        kich = duong.stat().st_size
        dau, cuoi = 0, kich - 1
        ma = 200
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            if a:
                dau = int(a)
                cuoi = int(b) if b else kich - 1
            elif b:  # dạng "bytes=-500": 500 byte cuối
                dau = max(0, kich - int(b))
            cuoi = min(cuoi, kich - 1)
            if dau > cuoi:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{kich}")
                return self.end_headers()
            ma = 206

        self.send_response(ma)
        self.send_header("Content-Type", kieu)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(cuoi - dau + 1))
        if ma == 206:
            self.send_header("Content-Range", f"bytes {dau}-{cuoi}/{kich}")
        self.end_headers()
        with duong.open("rb") as f:
            f.seek(dau)
            con = cuoi - dau + 1
            while con > 0:
                khoi = f.read(min(65536, con))
                if not khoi:
                    break
                self.wfile.write(khoi)
                con -= len(khoi)

    def do_HEAD(self):
        if self.path.endswith(".pmtiles"):
            duong = GOC.parent / "data" / "tiles" / Path(self.path).name
            if not duong.is_file():
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(duong.stat().st_size))
            return self.end_headers()
        return super().do_HEAD()

    def _json(self, du):
        noi_dung = json.dumps(du, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(noi_dung)))
        self.end_headers()
        self.wfile.write(noi_dung)


def tu_kiem_tra() -> int:
    loi = 0

    def kd(dieu_kien, ten):
        nonlocal loi
        if dieu_kien:
            print(f"đúng: {ten}")
        else:
            loi += 1
            print(f"SAI: {ten}")

    # Mã hoá terrarium phải giải ra đúng độ cao ban đầu.
    for h in (0.0, 1.5, 250.0, 900.0, -50.0):
        r, g, b = ma_hoa_terrarium(h)
        lai = r * 256 + g + b / 256 - 32768
        kd(abs(lai - h) < 0.02, f"terrarium giải lại {h} m (lệch {abs(lai - h):.4f})")

    kd(ma_hoa_terrarium(0.0) == (128, 0, 0), "mực nước biển là RGB(128,0,0)")

    # Ô 12/3253/1812 (ô kiểm tra trong cauhinh.js) phải trùm Ninh Bình.
    lon1, lat1, lon2, lat2 = o_sang_toa_do(12, 3253, 1812)
    kd(lon1 < DOI_LON < lon2 and lat2 < DOI_LAT < lat1,
       f"ô 12/3253/1812 trùm Hoa Lư ({lon1:.3f}..{lon2:.3f}, {lat2:.3f}..{lat1:.3f})")

    # Sinh được PNG hợp lệ cho cả bốn loại.
    for loai in ("nen", "ve-tinh", "dia-hinh", "do-doc"):
        du = sinh_o(loai, 12, 3253, 1812)
        anh = Image.open(io.BytesIO(du))
        kd(du[:8] == b"\x89PNG\r\n\x1a\n" and anh.size == (256, 256),
           f"ô {loai} là PNG 256x256 ({len(du)} byte)")

    # Ô địa hình giải ngược ra phải LIÊN TỤC. Resize ảnh đã mã hoá terrarium
    # làm vỡ mã ở biên byte, ra mặt đất bậc thang — assert này bắt đúng lỗi đó.
    anh = Image.open(io.BytesIO(sinh_o("dia-hinh", 12, 3253, 1812))).convert("RGB")
    px = anh.load()

    def giai(i, j):
        r, g, b = px[i, j]
        return r * 256 + g + b / 256 - 32768

    buoc_max = max(
        abs(giai(i + 1, j) - giai(i, j))
        for j in range(0, 256, 8)
        for i in range(0, 255)
    )
    kd(buoc_max < 5.0, f"độ cao liên tục giữa hai pixel kề (bước lớn nhất {buoc_max:.2f} m)")

    # Phạm vi phải là tệp thật nếu có, và ô kiểm tra phải nằm trong vùng —
    # không thì panel trạng thái báo đỏ một cách vô cớ.
    pv = pham_vi()
    kd(isinstance(pv.get("bounds"), list) and len(pv["bounds"]) == 4,
       f"phamvi.json có bounds hợp lệ (nguồn: {pv.get('nguon')})")
    kd(o_trong_pham_vi(12, 3253, 1812), "ô kiểm tra 12/3253/1812 nằm trong phạm vi")
    kd(not o_trong_pham_vi(12, 3253, 1812 + 40), "ô cách xa về phía nam là ngoài phạm vi")
    kd(not o_trong_pham_vi(pv["maxzoom"] + 1, 3253, 1812), "zoom quá maxzoom là ngoài phạm vi")

    # Đỉnh đồi phải cao hơn rìa, nếu không hillshade sẽ phẳng lì.
    kd(do_cao(DOI_LON, DOI_LAT) > do_cao(DOI_LON + 0.5, DOI_LAT) + 500,
       "đỉnh đồi cao hơn rìa, có dốc để hillshade ăn")

    print("Tự kiểm tra: tất cả đúng" if loi == 0 else f"Tự kiểm tra: {loi} lỗi")
    return loi


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(1 if tu_kiem_tra() else 0)

    cong = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"web/ tại http://localhost:{cong}  — ô bản đồ là ô GIẢ, sinh tại chỗ")
    print("Lớp chủ quyền cố tình không có: trang phải hiện cảnh báo đỏ.")
    ThreadingHTTPServer(("127.0.0.1", cong), Handler).serve_forever()
