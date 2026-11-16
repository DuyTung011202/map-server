#!/usr/bin/env python3
"""Kiểm kê file QGIS: project trỏ vào dữ liệu nào, CRS gì, có đường dẫn tuyệt đối không.

Chạy trước khi mang .qgs/.qgz lên QGIS Server — đường dẫn tuyệt đối kiểu
D:\\data\\x.shp là lý do số 1 làm project chạy tốt trên desktop nhưng trắng
trơn trên server Linux.

    python qgis-inventory.py qgis/                # quét cả thư mục
    python qgis-inventory.py a.qgs b.qgz          # vài file cụ thể
    python qgis-inventory.py --self-check         # tự kiểm tra
"""

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# ponytail: regex đủ cho 3 dạng hay gặp (ổ đĩa Windows, POSIX root, UNC share).
ABS_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")


def project_xml(path: Path) -> str:
    """Lấy nội dung .qgs, mở .qgz nếu cần."""
    if path.suffix.lower() == ".qgz":
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".qgs"))
            return z.read(name).decode("utf-8", "replace")
    return path.read_text("utf-8", errors="replace")


def layers(xml: str):
    """Sinh (tên layer, provider, datasource, authid) cho từng maplayer."""
    root = ET.fromstring(xml)
    for ml in root.iter("maplayer"):
        yield (
            (ml.findtext("layername") or "?").strip(),
            (ml.findtext("provider") or "?").strip(),
            (ml.findtext("datasource") or "").strip(),
            (ml.findtext("srs/spatialrefsys/authid") or "?").strip(),
        )


def warnings(provider: str, datasource: str, authid: str) -> list[str]:
    """Những thứ sẽ làm project vỡ khi đưa lên server."""
    out = []
    # Datasource của ogr/gdal có thể kèm |layername=... — chỉ xét phần đường dẫn.
    head = datasource.split("|", 1)[0]
    if provider in ("ogr", "gdal") and ABS_PATH.match(head):
        out.append("ĐƯỜNG DẪN TUYỆT ĐỐI")
    if provider == "postgres":
        if "password=" in datasource:
            out.append("MẬT KHẨU TRONG PROJECT")
        if "service=" not in datasource:
            out.append("không dùng service= (nên dùng pg_service.conf)")
    if provider in ("wms", "wfs", "arcgisfeatureserver", "arcgismapserver"):
        out.append(f"phụ thuộc dịch vụ ngoài ({provider})")
    # VN-2000 và các biến thể: phải reproject sang 3857/4326 cho vector tiles.
    if authid.startswith("EPSG:") and authid not in ("EPSG:3857", "EPSG:4326"):
        out.append(f"CRS {authid} — cần reproject cho web")
    return out


def report(paths: list[Path]) -> int:
    """In báo cáo; trả về số layer có cảnh báo."""
    flagged = 0
    for p in paths:
        try:
            rows = list(layers(project_xml(p)))
        except Exception as e:  # project hỏng / không phải QGIS
            print(f"\n{p.name}: KHÔNG ĐỌC ĐƯỢC — {type(e).__name__}: {e}")
            continue

        print(f"\n{'=' * 70}\n{p}  ({len(rows)} layer)\n{'=' * 70}")
        for name, provider, datasource, authid in rows:
            warn = warnings(provider, datasource, authid)
            flagged += bool(warn)
            print(f"  [{provider:<10}] {name}  <{authid}>")
            print(f"      {datasource[:110] or '(rỗng)'}")
            for w in warn:
                print(f"      ! {w}")
    return flagged


def self_check() -> None:
    """Dựng project tổng hợp, xác nhận từng cảnh báo bật đúng lúc."""
    def ml(name, provider, ds, authid):
        return (f"<maplayer><layername>{name}</layername>"
                f"<provider>{provider}</provider><datasource>{ds}</datasource>"
                f"<srs><spatialrefsys><authid>{authid}</authid>"
                f"</spatialrefsys></srs></maplayer>")

    xml = "<qgis>" + "".join([
        ml("abs_win", "ogr", r"D:\data\ranh.shp", "EPSG:4326"),
        ml("abs_posix", "ogr", "/mnt/data/ranh.shp|layername=ranh", "EPSG:4326"),
        ml("tuong_doi", "ogr", "./data/ranh.gpkg|layername=ranh", "EPSG:4326"),
        ml("pg_xau", "postgres", "dbname=gis password=123 table=poi", "EPSG:4326"),
        ml("pg_tot", "postgres", "service=gis table=poi", "EPSG:3857"),
        ml("vn2000", "ogr", "./data/thua.gpkg", "EPSG:3405"),
        ml("ngoai", "wms", "url=https://example.com/ows", "EPSG:3857"),
    ]) + "</qgis>"

    got = {n: warnings(p, d, a) for n, p, d, a in layers(xml)}

    assert "ĐƯỜNG DẪN TUYỆT ĐỐI" in got["abs_win"], got["abs_win"]
    assert "ĐƯỜNG DẪN TUYỆT ĐỐI" in got["abs_posix"], got["abs_posix"]
    # Đường dẫn tương đối là trường hợp tốt — không được cảnh báo gì.
    assert got["tuong_doi"] == [], got["tuong_doi"]
    assert "MẬT KHẨU TRONG PROJECT" in got["pg_xau"], got["pg_xau"]
    assert got["pg_tot"] == [], got["pg_tot"]
    assert any("EPSG:3405" in w for w in got["vn2000"]), got["vn2000"]
    assert any("wms" in w for w in got["ngoai"]), got["ngoai"]
    # .qgz phải đọc được như .qgs.
    import io, tempfile
    with tempfile.TemporaryDirectory() as d:
        qgz = Path(d) / "t.qgz"
        with zipfile.ZipFile(qgz, "w") as z:
            z.writestr("t.qgs", xml)
        assert len(list(layers(project_xml(qgz)))) == 7

    print("self-check OK")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--self-check":
        self_check() if args else print(__doc__)
        sys.exit(0)

    files: list[Path] = []
    for a in args:
        p = Path(a)
        files += sorted(p.rglob("*.qg[sz]")) if p.is_dir() else [p]

    if not files:
        sys.exit("Không tìm thấy .qgs/.qgz nào")

    n = report(files)
    print(f"\n{'-' * 70}\n{len(files)} project, {n} layer cần xử lý trước khi lên server")
