#!/usr/bin/env python3
"""Dựng ô địa hình (terrarium) và ô độ dốc từ DEM thật, cho một vùng khai sẵn.

    python scripts/dung-o-dia-hinh.py              # dựng cả tỉnh Ninh Bình
    python scripts/dung-o-dia-hinh.py --self-check # assert, không tải gì
    python scripts/dung-o-dia-hinh.py --bounds 105.5,19.8,106.7,20.8

Nguồn DEM: bộ "skadi" của AWS Open Data — chính là SRTM 1 arcsec đã vá lỗ,
đóng gói thành `.hgt.gz`. Chọn nó thay vì COG Copernicus vì `.hgt` là mảng
int16 big-endian TRẦN: `numpy.frombuffer` đọc thẳng, kho này không phải thêm
GDAL hay rasterio chỉ để cắt ô. Tải một lần về `data/dem/`, sau đó dựng lại
không cần mạng.

LUẬT KHÔNG ĐƯỢC PHÁ (CLAUDE.md): nội suy ĐỘ CAO trước, mã hoá terrarium sau.
Tệp này lấy mẫu DEM ra lưới độ cao 258x258 rồi mới mã hoá từng điểm. Đừng bao
giờ đổi sang hướng "mã hoá rồi resize ảnh" — bilinear nội suy riêng từng kênh
R/G/B làm vỡ mã ở biên byte, ra mặt đất bậc thang mà không ai báo lỗi.
"""

import gzip
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

from dia_hinh_chung import (VUNG_NINH_BINH, giai_terrarium, ma_hoa_terrarium,
                            met_moi_do, o_sang_toa_do, toa_do_sang_o)

GOC = Path(__file__).resolve().parent.parent
DEM = GOC / "data" / "dem"
RA_DIA_HINH = GOC / "data" / "tiles" / "dia-hinh"
RA_DO_DOC = GOC / "data" / "tiles" / "do-doc"
PHAM_VI_RA = GOC / "web" / "phamvi.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOUNDS_NINH_BINH = VUNG_NINH_BINH  # khai ở dia_hinh_chung, dùng chung với ô vệ tinh
MINZOOM, MAXZOOM = 8, 12

NGUON = "https://s3.amazonaws.com/elevation-tiles-prod/skadi"
CANH = 3601          # 1 arcsec: 3601 x 3601 điểm cho mỗi ô 1 độ
BUOC = 1.0 / 3600.0  # khoảng cách giữa hai điểm DEM, theo độ

# Ô biển hoàn toàn: không ghi ra tệp. Phần lớn vùng này giáp biển nên bỏ được
# kha khá ô, và MapLibre coi ô 404 là ô phẳng — đúng thứ ta muốn ở ngoài khơi.
NGUONG_O_BIEN = 0.5  # mét


# ----------------------------------------------------------------- tải DEM
def ten_hgt(lat: int, lon: int) -> str:
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def tai_hgt(lat: int, lon: int) -> Path:
    """Tải một ô DEM 1 độ nếu chưa có. Trả về đường dẫn tệp .hgt.gz."""
    ten = ten_hgt(lat, lon)
    dich = DEM / f"{ten}.hgt.gz"
    if dich.is_file():
        return dich
    url = f"{NGUON}/{ten[:3]}/{ten}.hgt.gz"
    DEM.mkdir(parents=True, exist_ok=True)
    print(f"  tải {ten} ...", end="", flush=True)
    tam = dich.with_suffix(".tam")
    with urllib.request.urlopen(url, timeout=120) as r, tam.open("wb") as f:
        f.write(r.read())
    tam.replace(dich)  # đổi tên sau khi tải xong: nửa chừng đứt thì không để lại tệp hỏng
    print(f" {dich.stat().st_size / 1e6:.1f} MB")
    return dich


def nap_luoi(bounds: list[float]) -> tuple[np.ndarray, float, float]:
    """Ghép các ô DEM 1 độ thành MỘT lưới độ cao phủ hết bounds.

    Trả (luoi, lat_tren, lon_trai): luoi[r][c] là độ cao tại
    lat = lat_tren - r * BUOC, lon = lon_trai + c * BUOC.
    """
    lon1, lat1, lon2, lat2 = bounds
    lons = range(math.floor(lon1), math.floor(lon2) + 1)
    lats = range(math.floor(lat1), math.floor(lat2) + 1)
    lon_trai, lat_tren = min(lons), max(lats) + 1

    # Các ô kề nhau chia nhau hàng/cột ở biên, nên mỗi ô đóng góp 3600 hàng,
    # cộng thêm một hàng/cột cuối cùng để khép lưới.
    cao = len(lats) * (CANH - 1) + 1
    rong = len(lons) * (CANH - 1) + 1
    luoi = np.zeros((cao, rong), dtype=np.int16)

    for lat in lats:
        for lon in lons:
            duong = tai_hgt(lat, lon)
            o = np.frombuffer(gzip.open(duong, "rb").read(), dtype=">i2")
            o = o.reshape(CANH, CANH).astype(np.int16)
            r0 = (lat_tren - (lat + 1)) * (CANH - 1)
            c0 = (lon - lon_trai) * (CANH - 1)
            luoi[r0:r0 + CANH, c0:c0 + CANH] = o

    # SRTM đánh dấu lỗ bằng -32768. Bộ skadi đã vá, nhưng nếu còn sót thì coi
    # là mực nước biển — thà phẳng còn hơn một hố sâu 32 km giữa bản đồ.
    luoi[luoi < -500] = 0
    return luoi, float(lat_tren), float(lon_trai)


# ------------------------------------------------------------- lấy mẫu & vẽ
def lay_mau(luoi: np.ndarray, lat_tren: float, lon_trai: float,
            lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """Nội suy song tuyến độ cao tại lưới điểm (lats x lons). Ra mảng mét."""
    fr = (lat_tren - lats) / BUOC
    fc = (lons - lon_trai) / BUOC
    r0 = np.clip(np.floor(fr).astype(np.int32), 0, luoi.shape[0] - 2)
    c0 = np.clip(np.floor(fc).astype(np.int32), 0, luoi.shape[1] - 2)
    dr = np.clip(fr - r0, 0.0, 1.0)[:, None]
    dc = np.clip(fc - c0, 0.0, 1.0)[None, :]

    a = luoi[np.ix_(r0, c0)].astype(np.float32)
    b = luoi[np.ix_(r0, c0 + 1)].astype(np.float32)
    c = luoi[np.ix_(r0 + 1, c0)].astype(np.float32)
    d = luoi[np.ix_(r0 + 1, c0 + 1)].astype(np.float32)
    return (a * (1 - dr) * (1 - dc) + b * (1 - dr) * dc
            + c * dr * (1 - dc) + d * dr * dc)


def cao_cua_o(luoi, lat_tren, lon_trai, z, x, y, vien=1) -> np.ndarray:
    """Độ cao cho một ô, kèm `vien` điểm thừa mỗi phía để tính dốc không rỗ mép."""
    lon1, lat1, lon2, lat2 = o_sang_toa_do(z, x, y)
    n = 256 + 2 * vien
    # Lấy mẫu tại TÂM từng pixel, lùi ra `vien` pixel mỗi phía.
    buoc_lon = (lon2 - lon1) / 256.0
    i = np.arange(n, dtype=np.float64) - vien + 0.5
    lons = lon1 + buoc_lon * i
    # Trục y của Mercator không đều theo vĩ độ: phải đi qua toạ độ Mercator,
    # lấy mẫu đều theo ĐỘ là ảnh địa hình lệch dần so với ô nền.
    def y_mercator(lat):
        return math.asinh(math.tan(math.radians(lat)))
    ym1, ym2 = y_mercator(lat1), y_mercator(lat2)
    yms = ym1 + (ym2 - ym1) * (i / 256.0)
    lats = np.degrees(np.arctan(np.sinh(yms)))
    return lay_mau(luoi, lat_tren, lon_trai, lons, lats)


def ve_terrarium(cao: np.ndarray) -> Image.Image:
    """Mã hoá lưới độ cao 256x256 thành PNG terrarium."""
    v = np.clip(cao + 32768.0, 0.0, 65535.999)
    nguyen = v.astype(np.uint32)
    r = (nguyen >> 8).astype(np.uint8)
    g = (nguyen & 0xFF).astype(np.uint8)
    b = ((v - nguyen) * 256).astype(np.uint8)
    return Image.fromarray(np.dstack([r, g, b]), "RGB")


def do_doc_deg(cao_vien: np.ndarray, lat_giua: float, z: int) -> np.ndarray:
    """Độ dốc (độ) cho 256x256 pixel giữa, từ lưới 258x258 có viền."""
    met_lon, met_lat = met_moi_do(lat_giua)
    # Bề rộng một pixel theo độ, ở zoom này.
    do_moi_px = 360.0 / (2**z * 256.0)
    dx_met = do_moi_px * met_lon
    dy_met = do_moi_px * met_lat * math.cos(math.radians(lat_giua))

    dz_dx = (cao_vien[1:-1, 2:] - cao_vien[1:-1, :-2]) / (2 * dx_met)
    dz_dy = (cao_vien[2:, 1:-1] - cao_vien[:-2, 1:-1]) / (2 * dy_met)
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))


def ve_do_doc(doc: np.ndarray, lop: list[dict]) -> Image.Image:
    """Tô màu độ dốc theo đúng bảng chú giải trong phamvi.json.

    Trang web dựng chú giải từ cùng một bảng (`dungChuGiai`), nên màu ở ô và
    màu ở chú giải không thể lệch nhau.
    """
    h, w = doc.shape
    anh = np.zeros((h, w, 4), dtype=np.uint8)
    for muc in lop:
        tu = muc["tu"]
        den = muc["den"] if muc["den"] is not None else 1e9
        mau = muc["mau"].lstrip("#")
        r, g, b = (int(mau[i:i + 2], 16) for i in (0, 2, 4))
        chon = (doc >= tu) & (doc < den)
        anh[chon] = (r, g, b, 255)
    return Image.fromarray(anh, "RGBA")


# ------------------------------------------------------------------- dựng
def o_trong_bounds(z, x, y, bounds) -> bool:
    lon1, lat1, lon2, lat2 = o_sang_toa_do(z, x, y)
    return not (lon2 < bounds[0] or lon1 > bounds[2]
                or lat1 < bounds[1] or lat2 > bounds[3])


def dung(bounds: list[float]) -> dict:
    print(f"Vùng: {bounds}  zoom {MINZOOM}–{MAXZOOM}")
    luoi, lat_tren, lon_trai = nap_luoi(bounds)
    print(f"Lưới DEM: {luoi.shape[0]}x{luoi.shape[1]} điểm, "
          f"cao {int(luoi.min())}–{int(luoi.max())} m")

    lop_doc = json.loads(PHAM_VI_RA.read_text("utf-8"))["do_doc"]["lop"]
    dem_dh = dem_dd = bo_qua = 0

    for z in range(MINZOOM, MAXZOOM + 1):
        x1, y1 = toa_do_sang_o(bounds[0], bounds[3], z)
        x2, y2 = toa_do_sang_o(bounds[2], bounds[1], z)
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                if not o_trong_bounds(z, x, y, bounds):
                    continue
                cao_vien = cao_cua_o(luoi, lat_tren, lon_trai, z, x, y)
                cao = cao_vien[1:-1, 1:-1]

                if float(np.abs(cao).max()) < NGUONG_O_BIEN:
                    bo_qua += 1
                    continue

                d = RA_DIA_HINH / str(z) / str(x)
                d.mkdir(parents=True, exist_ok=True)
                ve_terrarium(cao).save(d / f"{y}.png", optimize=True)
                dem_dh += 1

                _, lat1, _, lat2 = o_sang_toa_do(z, x, y)
                doc = do_doc_deg(cao_vien, (lat1 + lat2) / 2, z)
                if float(doc.max()) >= lop_doc[0]["tu"]:
                    d2 = RA_DO_DOC / str(z) / str(x)
                    d2.mkdir(parents=True, exist_ok=True)
                    ve_do_doc(doc, lop_doc).save(d2 / f"{y}.png", optimize=True)
                    dem_dd += 1
        print(f"  z{z}: xong")

    print(f"Đã ghi {dem_dh} ô địa hình, {dem_dd} ô độ dốc, bỏ {bo_qua} ô biển")
    return {"dia_hinh": dem_dh, "do_doc": dem_dd, "bo_qua": bo_qua,
            "cao_nhat": float(luoi.max())}


def ghi_pham_vi(bounds: list[float], cao_nhat: float) -> None:
    """Cập nhật web/phamvi.json — trang đọc bounds/zoom/ghi công từ đây."""
    pv = json.loads(PHAM_VI_RA.read_text("utf-8"))
    pv["bounds"] = bounds
    pv["minzoom"] = MINZOOM
    pv["maxzoom"] = MAXZOOM
    pv["ma_hoa"] = "terrarium"
    pv["nguon"] = ("SRTM 1 arcsec (NASA/USGS, phạm vi công cộng) "
                   "qua AWS Open Data — bộ skadi")
    pv["moc_do_cao"] = "EGM96 (xấp xỉ mực nước biển)"
    pv["ngay_dung"] = "2026-11-16"
    pv["vung"] = "Tỉnh Ninh Bình (sau sáp nhập 2025)"
    pv["cao_nhat_m"] = round(cao_nhat)
    PHAM_VI_RA.write_text(json.dumps(pv, ensure_ascii=False, indent=2), "utf-8")
    print(f"Đã ghi {PHAM_VI_RA.relative_to(GOC)}")


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

    # Mã hoá hàng loạt phải ra ĐÚNG như mã hoá từng điểm của dia_hinh_chung.
    # Đây là cái bẫy chính của tệp này: bản numpy và bản thuần Python lệch
    # nhau một bậc là cả vùng sai độ cao mà ảnh trông vẫn bình thường.
    mau = np.array([[0.0, 1.5, -50.0], [250.0, 900.0, 1667.25]], dtype=np.float32)
    anh = np.asarray(ve_terrarium(mau))
    lech = 0.0
    for j in range(mau.shape[0]):
        for i in range(mau.shape[1]):
            r, g, b = (int(v) for v in anh[j, i])
            kd((r, g, b) == ma_hoa_terrarium(float(mau[j, i])),
               f"mã hoá hàng loạt khớp từng điểm tại {mau[j, i]} m")
            lech = max(lech, abs(giai_terrarium(r, g, b) - float(mau[j, i])))
    kd(lech < 0.02, f"giải mã lại sai số dưới 2 cm (lớn nhất {lech:.4f} m)")

    # Nội suy trên lưới phẳng phải ra đúng hằng số đó, không rỉ ra số lạ.
    phang = np.full((50, 50), 123.0, dtype=np.int16)
    ra = lay_mau(phang, 21.0, 105.0, np.linspace(105.001, 105.005, 16),
                 np.linspace(20.999, 20.995, 16))
    kd(np.allclose(ra, 123.0), "nội suy trên lưới phẳng giữ nguyên độ cao")

    # Dốc: một mặt nghiêng đều phải ra đúng góc tính tay.
    z = 12
    lat = 20.25
    met_lon, _ = met_moi_do(lat)
    do_moi_px = 360.0 / (2**z * 256.0)
    dx = do_moi_px * met_lon
    cao = np.tile(np.arange(258, dtype=np.float32) * dx * math.tan(math.radians(30.0)),
                  (258, 1))
    doc = do_doc_deg(cao, lat, z)
    kd(abs(float(doc.mean()) - 30.0) < 0.5,
       f"mặt nghiêng 30° ra đúng 30° (được {float(doc.mean()):.2f}°)")

    # Ô nào nằm trong vùng: ô Hoa Lư phải có, ô giữa Lào phải không.
    b = BOUNDS_NINH_BINH
    kd(o_trong_bounds(12, 3253, 1812, b), "ô Hoa Lư nằm trong vùng Ninh Bình")
    kd(not o_trong_bounds(12, 3200, 1812, b), "ô cách xa về phía tây là ngoài vùng")

    # Bảng màu phải lấy từ phamvi.json, không ghi cứng trong tệp này.
    lop = json.loads(PHAM_VI_RA.read_text("utf-8"))["do_doc"]["lop"]
    anh2 = np.asarray(ve_do_doc(np.full((4, 4), 40.0), lop))
    cuoi = lop[-1]["mau"].lstrip("#")
    kd(tuple(anh2[0, 0][:3]) == tuple(int(cuoi[i:i + 2], 16) for i in (0, 2, 4)),
       "dốc 40° tô đúng màu bậc cuối của chú giải")
    anh3 = np.asarray(ve_do_doc(np.full((4, 4), 2.0), lop))
    kd(int(anh3[0, 0][3]) == 0, "dốc dưới bậc đầu thì trong suốt, không tô bừa")

    print("Tự kiểm tra: tất cả đúng" if loi == 0 else f"Tự kiểm tra: {loi} lỗi")
    return loi


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(1 if tu_kiem_tra() else 0)

    bounds = BOUNDS_NINH_BINH
    if "--bounds" in sys.argv:
        bounds = [float(v) for v in sys.argv[sys.argv.index("--bounds") + 1].split(",")]

    kq = dung(bounds)
    ghi_pham_vi(bounds, kq["cao_nhat"])
