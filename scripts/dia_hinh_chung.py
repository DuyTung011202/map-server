"""Phép toán ô bản đồ và vùng phủ, dùng chung giữa các script dựng ô.

Tên tệp dùng GẠCH DƯỚI chứ không gạch ngang như phần còn lại của kho: Python
không import được tên có gạch ngang. Đây là ngoại lệ duy nhất, và nó tồn tại
vì lý do nghiêm túc — `chay-demo.py` (ô giả) và `dung-o-dia-hinh.py` (ô thật)
phải mã hoá độ cao GIỐNG HỆT nhau. Lệch một byte là mặt đất bậc thang ở bản
này mà mượt ở bản kia, và không request nào báo lỗi.
"""

import math

# Cả tỉnh Ninh Bình sau sáp nhập 2025 (gồm Hà Nam và Nam Định cũ), nới mỗi
# phía một chút để ô ở rìa không bị cắt cụt. Ô địa hình, ô độ dốc và ô vệ
# tinh phải phủ CÙNG một vùng — để hai nơi khai riêng là sớm muộn lệch nhau.
VUNG_NINH_BINH = [105.5, 19.8, 106.7, 20.8]

# Terrarium (Mapzen/Tilezen): h = R * 256 + G + B / 256 - 32768
# MapLibre giải mã đúng công thức này khi source khai `encoding: "terrarium"`.
GOC_TERRARIUM = 32768.0


def o_sang_toa_do(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Góc tây-bắc và đông-nam của một ô, theo độ. Trả (lon1, lat1, lon2, lat2)."""
    n = 2.0**z
    lon1 = x / n * 360.0 - 180.0
    lon2 = (x + 1) / n * 360.0 - 180.0
    lat1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat2 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return lon1, lat1, lon2, lat2


def toa_do_sang_o(lon: float, lat: float, z: int) -> tuple[int, int]:
    """Ngược của o_sang_toa_do: điểm này rơi vào ô nào."""
    n = 2.0**z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def ma_hoa_terrarium(h: float) -> tuple[int, int, int]:
    """Mã hoá một độ cao (mét) thành RGB terrarium."""
    v = max(0.0, min(65535.999, h + GOC_TERRARIUM))
    r = int(v) >> 8
    g = int(v) & 0xFF
    b = int((v - int(v)) * 256) & 0xFF
    return r, g, b


def giai_terrarium(r: int, g: int, b: int) -> float:
    """Giải RGB terrarium ngược lại thành độ cao (mét)."""
    return r * 256 + g + b / 256 - GOC_TERRARIUM


def met_moi_do(lat: float) -> tuple[float, float]:
    """Một độ kinh / vĩ dài bao nhiêu mét ở vĩ độ này.

    Cần cho việc tính độ dốc: chênh cao chia cho khoảng cách THẬT. Lấy chênh
    cao chia cho số ĐỘ thì ra dốc sai theo vĩ độ, và sai nhiều ở gần cực.
    """
    return 111320.0 * math.cos(math.radians(lat)), 110540.0
