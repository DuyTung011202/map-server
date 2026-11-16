"""Đọc header PMTiles v3. Dùng chung cho mọi script động tới tệp ô.

Tên tệp gạch dưới vì Python không import được tên có gạch ngang — cùng lý do
với `dia_hinh_chung.py`.

Bố cục 127 byte đầu lấy từ đặc tả v3 và đã đối chiếu với tệp thật: bounds đọc
ra `102.10, 7.38, 114.64, 23.40` đúng là Việt Nam, zoom 0–14, kiểu ô 1 (MVT).
"""

import struct
from pathlib import Path


def doc_header(duong: Path) -> dict:
    with Path(duong).open("rb") as f:
        d = f.read(127)
    if len(d) < 127 or d[:7] != b"PMTiles":
        raise ValueError(f"{Path(duong).name}: không phải tệp PMTiles")
    if d[7] != 3:
        raise ValueError(f"{Path(duong).name}: PMTiles phiên bản {d[7]}, cần 3")
    b = struct.unpack_from("<iiii", d, 102)
    return {
        "so_o": struct.unpack_from("<Q", d, 72)[0],
        "so_muc": struct.unpack_from("<Q", d, 80)[0],
        "kieu_o": d[99],          # 1 = MVT vector
        "minzoom": d[100],
        "maxzoom": d[101],
        "bounds": [v / 1e7 for v in b],
        "kich_thuoc": Path(duong).stat().st_size,
    }


def mo_ta(h: dict) -> str:
    return (f"{h['kich_thuoc'] / 1e6:.0f} MB · {h['so_o']:,} ô · "
            f"z{h['minzoom']}–{h['maxzoom']} · "
            f"bounds {', '.join(f'{v:.2f}' for v in h['bounds'])}")
