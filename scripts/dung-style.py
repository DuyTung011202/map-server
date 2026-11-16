#!/usr/bin/env python3
"""Dựng style của máy chủ từ style gốc OSM Bright.

Vì sao có script này thay vì sửa tay một tệp JSON 129 lớp: style gốc trỏ font
và sprite vào máy chủ của người khác, và nguồn ô trỏ vào dịch vụ trả phí. Mỗi
lần style gốc cập nhật mà sửa tay là một dịp sót. Script làm đúng bốn việc:

  1. Nguồn ô  -> tệp PMTiles của mình
  2. Glyph    -> web/vendor/font/   (không gọi api.maptiler.com)
  3. Sprite   -> web/vendor/sprite/ (không gọi openmaptiles.github.io)
  4. Lớp chủ quyền -> đặt vào cuối style

Việc 4 là lý do chính style phải do MÁY CHỦ phát: ứng dụng nào dùng style này
là có lớp chủ quyền sẵn, không cần một dòng mã client. Xem PLAN.md mục 4.

Ra HAI tệp, khác nhau đúng ba đường dẫn (nguồn ô, glyph, sprite):

  web/style/nen-pho.json      cho TRÌNH DUYỆT — pmtiles:// đọc bằng HTTP Range
  web/style/nen-pho-may.json  cho TILESERVER GL — nó raster hoá ra PNG cho
                              `cách 1` ở PLAN.md mục 6, và nó dùng cú pháp
                              đường dẫn riêng (pmtiles://{ten}, {styleJsonFolder})

Dựng cả hai từ một hàm nên lớp chủ quyền không thể có ở bản này mà thiếu ở bản
kia — đó chính là thứ cần giữ.

    python scripts/dung-style.py
    python scripts/dung-style.py --self-check
"""

import json
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
STYLE_GOC = GOC / "web" / "style-goc.json"
STYLE_RA = GOC / "web" / "style" / "nen-pho.json"
STYLE_MAY_RA = GOC / "web" / "style" / "nen-pho-may.json"
CHU_QUYEN = GOC / "web" / "chu-quyen" / "chu-quyen-dao.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Nguồn ô: pmtiles:// để thư viện PMTiles bắt lấy và đọc bằng HTTP range
# request. Không cần tile server, chỉ cần một tệp tĩnh.
NGUON_O = "pmtiles:///tiles/vietnam.pmtiles"
GLYPH = "/vendor/font/{fontstack}/{range}.pbf"
SPRITE = "/vendor/sprite/sprite"

# TileServer GL không nhận URL: nó có cú pháp riêng. `pmtiles://{ten}` trỏ vào
# khoá trong mục `data` của trien-khai/tileserver.json; glyph tìm dưới thư mục
# `paths.fonts`; `{styleJsonFolder}` là thư mục chứa chính tệp style này.
NGUON_O_MAY = "pmtiles://{vietnam}"
GLYPH_MAY = "{fontstack}/{range}.pbf"
SPRITE_MAY = "{styleJsonFolder}/sprite/sprite"


def lop_chu_quyen(du: dict | None) -> list[dict]:
    """Lớp Hoàng Sa, Trường Sa đặt ở CUỐI style nên luôn nằm trên mọi lớp nền.

    Không có công tắc tắt: không sinh ra `layout.visibility`, để client không
    có chỗ nào tắt đi mà vẫn đúng schema.

    Tên đảo lấy từ thuộc tính của chính dữ liệu, KHÔNG lấy từ OSM — kể cả OSM
    do mình tự build, vì ô nền OSM ghi sai tên và vẽ sai ranh ở Biển Đông.
    """
    if du is None:
        return []
    return [
        {
            "id": "chu-quyen-vung",
            "type": "fill",
            "source": "chu-quyen",
            "filter": ["!=", ["geometry-type"], "Point"],
            "paint": {"fill-color": "#1b4f8a", "fill-opacity": 0.85},
        },
        {
            "id": "chu-quyen-nhan",
            "type": "symbol",
            "source": "chu-quyen",
            "filter": ["==", ["geometry-type"], "Point"],
            "layout": {
                "text-field": ["coalesce", ["get", "ten"], ["get", "name"]],
                "text-font": ["Noto Sans Bold"],
                "text-size": 12,
            },
            "paint": {
                "text-color": "#ffffff",
                "text-halo-color": "#0f2c4d",
                "text-halo-width": 1.4,
            },
        },
    ]


def dung(goc: dict, chu_quyen: dict | None,
         nguon_o: str = NGUON_O, glyph: str = GLYPH, sprite: str = SPRITE) -> dict:
    s = json.loads(json.dumps(goc))  # không sửa vào bản gốc

    s["name"] = "Nền đường phố — máy chủ bản đồ"
    s["glyphs"] = glyph
    s["sprite"] = sprite

    # Style gốc khai source tên 'openmaptiles' trỏ vào dịch vụ trả phí.
    # Planetiler xuất đúng schema đó nên chỉ cần đổi chỗ lấy dữ liệu.
    for ten, ng in s.get("sources", {}).items():
        if ng.get("type") == "vector":
            s["sources"][ten] = {"type": "vector", "url": nguon_o}

    if chu_quyen is not None:
        s["sources"]["chu-quyen"] = {"type": "geojson", "data": chu_quyen}
        s["layers"] = s["layers"] + lop_chu_quyen(chu_quyen)

    return s


def doc_chu_quyen() -> dict | None:
    if CHU_QUYEN.is_file():
        return json.loads(CHU_QUYEN.read_text("utf-8"))
    return None


def tu_kiem_tra() -> int:
    loi = 0

    def kd(dk, ten):
        nonlocal loi
        if dk:
            print(f"đúng: {ten}")
        else:
            loi += 1
            print(f"SAI: {ten}")

    gia = {
        "version": 8,
        "glyphs": "https://api.maptiler.com/fonts/{fontstack}/{range}.pbf?key=X",
        "sprite": "https://openmaptiles.github.io/osm-bright-gl-style/sprite",
        "sources": {"openmaptiles": {"type": "vector", "url": "https://api.maptiler.com/x.json?key=X"}},
        "layers": [{"id": "nen", "type": "background"}],
    }

    s = dung(gia, None)
    van_ban = json.dumps(s)
    kd("maptiler.com" not in van_ban, "không còn URL maptiler.com trong style")
    kd("openmaptiles.github.io" not in van_ban, "không còn URL sprite ngoài")
    kd("http" not in s["glyphs"] and "http" not in s["sprite"],
       "glyph và sprite đều là đường cùng gốc")
    kd(s["sources"]["openmaptiles"]["url"].startswith("pmtiles://"),
       "nguồn ô trỏ vào tệp PMTiles của mình")
    kd(gia["glyphs"].startswith("https://"), "không sửa vào style gốc")

    # Không có dữ liệu chủ quyền thì KHÔNG được âm thầm sinh style trống lớp.
    kd(len(s["layers"]) == 1, "thiếu dữ liệu chủ quyền thì không bịa lớp ra")

    cq = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"ten": "X"},
                      "geometry": {"type": "Point", "coordinates": [112, 16]}}],
    }
    s2 = dung(gia, cq)
    ids = [l["id"] for l in s2["layers"]]
    kd(ids[-2:] == ["chu-quyen-vung", "chu-quyen-nhan"],
       "lớp chủ quyền nằm ở CUỐI style, tức là trên cùng")
    kd(all("visibility" not in l.get("layout", {}) for l in s2["layers"][-2:]),
       "lớp chủ quyền không có công tắc tắt")

    # Bản cho TileServer GL. Sai một trong ba đường dẫn này thì nó không báo
    # lỗi style — nó render ra ô TRẮNG, hoặc ô có hình mà mất hết chữ.
    sm = dung(gia, cq, NGUON_O_MAY, GLYPH_MAY, SPRITE_MAY)
    kd(sm["sources"]["openmaptiles"]["url"] == "pmtiles://{vietnam}",
       "bản máy chủ trỏ nguồn bằng tên trong tileserver.json, không phải URL")
    kd("{fontstack}" in sm["glyphs"] and "{range}" in sm["glyphs"]
       and not sm["glyphs"].startswith("/"),
       "bản máy chủ giữ token glyph và không có / đứng đầu")
    kd("{styleJsonFolder}" in sm["sprite"], "bản máy chủ tìm sprite cạnh tệp style")
    kd([l["id"] for l in sm["layers"]][-2:] == ["chu-quyen-vung", "chu-quyen-nhan"],
       "bản máy chủ cũng có lớp chủ quyền ở cuối")

    print("Tự kiểm tra: tất cả đúng" if loi == 0 else f"Tự kiểm tra: {loi} lỗi")
    return loi


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(1 if tu_kiem_tra() else 0)

    if not STYLE_GOC.is_file():
        sys.exit(f"Thiếu {STYLE_GOC}. Tải style gốc OSM Bright về trước.")

    cq = doc_chu_quyen()
    goc = json.loads(STYLE_GOC.read_text("utf-8"))
    s = dung(goc, cq)
    s_may = dung(goc, cq, NGUON_O_MAY, GLYPH_MAY, SPRITE_MAY)

    STYLE_RA.parent.mkdir(parents=True, exist_ok=True)
    STYLE_RA.write_text(json.dumps(s, ensure_ascii=False, indent=1), "utf-8")
    STYLE_MAY_RA.write_text(json.dumps(s_may, ensure_ascii=False, indent=1), "utf-8")

    print(f"Đã ghi {STYLE_RA.relative_to(GOC)} — {len(s['layers'])} lớp (trình duyệt)")
    print(f"Đã ghi {STYLE_MAY_RA.relative_to(GOC)} — {len(s_may['layers'])} lớp (TileServer GL)")
    if cq is None:
        print()
        print("  ⚠ CHƯA CÓ LỚP CHỦ QUYỀN.")
        print(f"  Thiếu {CHU_QUYEN.relative_to(GOC)}.")
        print("  Style này chưa dùng được cho ứng dụng thật: ô nền OSM ghi sai")
        print("  tên và vẽ sai ranh ở Hoàng Sa, Trường Sa. Xem PLAN.md mục 4.")
