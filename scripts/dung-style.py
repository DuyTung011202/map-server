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
TEN_NUOC = GOC / "web" / "the-gioi" / "ten-nuoc.json"
VIET_NAM = GOC / "web" / "the-gioi" / "viet-nam.json"
STYLE_RA = GOC / "web" / "style" / "nen-pho.json"
STYLE_MAY_RA = GOC / "web" / "style" / "nen-pho-may.json"
CHU_QUYEN = GOC / "web" / "chu-quyen" / "chu-quyen-dao.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Nguồn ô: pmtiles:// để thư viện PMTiles bắt lấy và đọc bằng HTTP range
# request. Không cần tile server, chỉ cần một tệp tĩnh.
NGUON_O = "pmtiles:///tiles/vietnam.pmtiles"
# Phải khớp maxzoom thật của data/tiles/vietnam.pmtiles. Sai số này là bản đồ
# trắng ở zoom cao mà không một dòng lỗi — xem chú thích trong dung().
MAXZOOM_O = 16
NGUON_THE_GIOI = "pmtiles:///tiles/the-gioi.pmtiles"
# Phải khớp MAXZOOM trong scripts/dung-o-the-gioi.py.
MAXZOOM_THE_GIOI = 6
NGUON_THE_GIOI_MAY = "pmtiles://{the-gioi}"
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


# KHÔNG có `["get", "name"]` ở cuối, và đó là chủ ý. `name` thô có thể là chữ
# Hán ("三沙市"), mà một ký tự ngoài dải glyph đã tải là TileServer GL trả 500
# cho cả ô. Đã đo trên dữ liệu thật: 1039 nhãn có tên, 0 nhãn thiếu
# `name:latin` — nên bỏ `name` thô không mất gì.
TEN_VIET = ["coalesce", ["get", "name:vi"], ["get", "name:latin"]]


def uu_tien_tieng_viet(s: dict) -> int:
    """Mọi nhãn lấy tên tiếng Việt trước, và BỎ HẲN `{name:nonlatin}`.

    Hai lý do, lý do thứ hai mới là lý do chính:

    1. Style gốc dùng `{name:latin}\\n{name:nonlatin}` ở 16 lớp. Phần
       `nonlatin` kéo theo chữ Hán, Hàn, Nhật — và TileServer GL gặp dải
       glyph thiếu thì trả HTTP 500 cho CẢ Ô, không phải chỉ mất chữ:
           ERROR: Font not found: .../Noto Sans Italic/49152-49407.pbf
       Lấy đủ 256 dải glyph thì vendor phình từ 2.8 MB lên ~60 MB. Bỏ
       nonlatin thì không cần dải nào ngoài Latin.

    2. Ô nền OSM ghi tên Trung Quốc ở Biển Đông ("三沙市 Sansha"). Hiện
       `{name:nonlatin}` nghĩa là in đúng cái tên đó lên bản đồ. Ép tên tiếng
       Việt là hàng phòng thủ thứ hai, sau lớp chủ quyền. Xem CLAUDE.md.

    Trả về số lớp đã sửa.
    """
    dem = 0
    for l in s.get("layers", []):
        tf = l.get("layout", {}).get("text-field")
        if isinstance(tf, str) and "name" in tf:
            l["layout"]["text-field"] = json.loads(json.dumps(TEN_VIET))
            dem += 1
    return dem


# Màu theo nhóm POI, lấy tinh thần từ bản đồ thương mại: ăn uống cam, y tế
# đỏ, mua sắm xanh dương, tài chính tím, giáo dục xanh lá, giao thông lam.
# `class` là trường của schema OpenMapTiles, không phải ta tự đặt.
MAU_POI = [
    (["restaurant", "fast_food", "cafe", "bar", "ice_cream", "bakery"], "#e8701a"),
    (["pharmacy", "hospital", "doctors", "clinic", "dentist", "veterinary"], "#d9353a"),
    (["bank", "atm", "bureau_de_change"], "#8257c7"),
    (["shop", "grocery", "clothing_store", "department_store", "convenience",
      "supermarket", "alcohol_shop", "furniture", "hardware"], "#2d79c7"),
    (["school", "college", "library", "kindergarten"], "#3f9d4a"),
    (["bus", "railway", "airport", "aerodrome", "ferry_terminal"], "#1b8f9b"),
    (["park", "garden", "pitch", "stadium", "swimming_pool"], "#4f9e3f"),
    (["lodging", "hotel"], "#c7418f"),
    (["fuel", "car_repair", "parking"], "#5a6b78"),
    (["place_of_worship", "cemetery"], "#8a6d3b"),
    (["police", "town_hall", "fire_station", "post", "government"], "#3b6ea8"),
]
MAU_POI_KHAC = "#7b7f87"


def bieu_thuc_mau_poi(nhat: bool) -> list:
    """Biểu thức `match` đổi `class` thành màu. `nhat`=True cho nền badge."""
    bt: list = ["match", ["get", "class"]]
    for nhom, mau in MAU_POI:
        bt.append(nhom)
        bt.append(lam_nhat(mau) if nhat else mau)
    bt.append(lam_nhat(MAU_POI_KHAC) if nhat else MAU_POI_KHAC)
    return bt


def lam_nhat(mau: str) -> str:
    """Trộn màu với trắng theo tỉ lệ 1:4 — ra nền đủ nhạt để icon sẫm đọc được."""
    r, g, b = (int(mau[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(v + (255 - v) * 0.78) for v in (r, g, b))


def lop_poi() -> list[dict]:
    """Badge tròn + icon + tên bên dưới, thay cho ba lớp poi-level của style gốc.

    Vì sao nền NHẠT mà không phải nền đậm chữ trắng như bản đồ thương mại:
    sprite của ta có 103 icon và KHÔNG cái nào là SDF (`sdf: false`), nên
    MapLibre không tô lại màu glyph được — icon luôn giữ màu sẫm gốc. Đặt
    icon sẫm lên nền đậm thì không đọc nổi. Muốn đúng kiểu chữ trắng trên nền
    đậm thì phải dựng lại sprite dạng SDF, đó là việc riêng.
    """
    # Lọc theo HẠNG, tăng dần theo zoom. Style gốc làm việc này bằng ba lớp
    # riêng (poi-level-1/2/3); gộp lại một biểu thức thì chỉ còn một lớp mà
    # vẫn giữ nguyên cách thưa dần. Không lọc thì z17 hiện hàng trăm badge
    # chồng lên nhau, nhãn bị nuốt gần hết vì va chạm.
    co_ten = ["all",
              ["==", ["geometry-type"], "Point"],
              ["has", "name"],
              ["<=", ["coalesce", ["get", "rank"], 0],
               ["step", ["zoom"], 14, 15, 24, 16, 60, 17, 1000]]]
    return [
        {
            "id": "poi-badge",
            "type": "circle",
            "source": "openmaptiles",
            "source-layer": "poi",
            "minzoom": 14,
            "filter": co_ten,
            "paint": {
                "circle-color": bieu_thuc_mau_poi(True),
                "circle-stroke-color": bieu_thuc_mau_poi(False),
                "circle-stroke-width": 1.6,
                "circle-radius": ["interpolate", ["linear"], ["zoom"],
                                  14, 5, 16, 7.5, 18, 9],
                "circle-opacity": 0.95,
            },
        },
        {
            "id": "poi-nhan",
            "type": "symbol",
            "source": "openmaptiles",
            "source-layer": "poi",
            "minzoom": 14,
            "filter": co_ten,
            "layout": {
                "icon-image": ["concat", ["get", "class"], "_11"],
                "icon-size": ["interpolate", ["linear"], ["zoom"], 14, 0.75, 18, 1],
                # Icon thiếu thì vẫn phải hiện tên, không bỏ cả nhãn.
                "icon-optional": True,
                "text-field": TEN_VIET,
                "text-font": ["Noto Sans Regular"],
                "text-anchor": "top",
                "text-offset": [0, 0.85],
                "text-size": ["interpolate", ["linear"], ["zoom"], 14, 10, 18, 12],
                "text-max-width": 7,
                "text-padding": 3,
                "text-optional": True,
            },
            "paint": {
                "text-color": "#3f4349",
                "text-halo-color": "#ffffff",
                "text-halo-width": 1.5,
            },
        },
    ]


def thay_lop_poi(s: dict) -> int:
    """Bỏ ba lớp poi-level-* của style gốc, chèn badge vào đúng chỗ cũ.

    Chèn ĐÚNG VỊ TRÍ CŨ chứ không nối vào cuối: nối vào cuối thì POI vẽ đè
    lên cả lớp chủ quyền.
    """
    vi_tri = None
    con_lai = []
    for l in s["layers"]:
        if l["id"].startswith("poi-level-"):
            if vi_tri is None:
                vi_tri = len(con_lai)
            continue
        con_lai.append(l)
    if vi_tri is None:
        return 0
    s["layers"] = con_lai[:vi_tri] + lop_poi() + con_lai[vi_tri:]
    return 1


def lop_the_gioi() -> list[dict]:
    """Nền thế giới ở zoom thấp: đất, ranh giới quốc gia, tên nước.

    Chèn NGAY TRÊN `background` và dưới mọi lớp Việt Nam, nên ở nơi có dữ
    liệu Việt Nam thì lớp Việt Nam vẽ đè lên — không ai thấy lớp này. Nó chỉ
    hiện ra ở chỗ trước đây trống trơn.

    `maxzoom: 7` vì `the-gioi.pmtiles` chỉ dựng tới z6; để MapLibre phóng to
    thêm một bậc cho mượt rồi thôi, chứ không kéo lên z14 làm nhoè.
    """
    return [
        {
            "id": "the-gioi-dat",
            "type": "background",
            "maxzoom": 7,
            # Hơi khác màu nền để phân biệt được đất với biển khi zoom xa.
            "paint": {"background-color": "#f2ece3"},
        },
        {
            "id": "the-gioi-nuoc",
            "type": "fill",
            "source": "the-gioi",
            "source-layer": "water",
            "maxzoom": 7,
            # Phải TRÙNG màu lớp `water` của style gốc (hsl(210,67%,85%)).
            # Lệch một chút là hiện ra khung chữ nhật quanh Việt Nam ở zoom
            # thấp — đúng biên của vietnam.pmtiles, trông như lỗi dữ liệu.
            "paint": {"fill-color": "hsl(210, 67%, 85%)"},
        },
        {
            "id": "the-gioi-ranh-gioi",
            "type": "line",
            "source": "the-gioi",
            "source-layer": "boundary",
            "maxzoom": 7,
            "filter": ["<=", ["get", "admin_level"], 2],
            "paint": {"line-color": "#9a9a9a", "line-width": 0.8,
                      "line-dasharray": [3, 2]},
        },
        # Việt Nam tô khác màu hẳn các nước còn lại. Vùng lấy từ Natural
        # Earth — KHÔNG gồm Hoàng Sa, Trường Sa, nên đây chỉ là màu nền đất
        # liền, không phải tuyên bố ranh giới. Lớp chủ quyền ở cuối style vẫn
        # là nguồn sự thật duy nhất về hai quần đảo.
        {
            "id": "viet-nam-noi-bat",
            "type": "fill",
            "source": "viet-nam",
            "maxzoom": 7,
            "paint": {"fill-color": "#e8f0e0", "fill-outline-color": "#b9c9ab"},
        },
        # Nhãn tên nước lấy từ Natural Earth (cột name_vi), KHÔNG lấy từ ô
        # nền: mục `place` của the-gioi.pmtiles chỉ có đúng Việt Nam, vì
        # Planetiler sinh nhãn địa danh từ OSM mà đầu vào OSM chỉ có Việt Nam.
        {
            "id": "the-gioi-ten-nuoc",
            "type": "symbol",
            "source": "ten-nuoc",
            "maxzoom": 7,
            "layout": {
                "text-field": ["get", "ten"],
                "text-font": ["Noto Sans Regular"],
                "text-size": ["interpolate", ["linear"], ["zoom"], 2, 10, 6, 13],
                "text-max-width": 7,
            },
            "paint": {"text-color": "#6f675d", "text-halo-color": "#ffffff",
                      "text-halo-width": 1.4},
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
            # Khai THẲNG maxzoom thay vì để MapLibre đợi TileJSON của giao
            # thức pmtiles trả về. Thiếu nó thì bản đồ TRẮNG TRƠN từ z16 trở
            # lên: MapLibre không biết nguồn dừng ở đâu nên không phóng to ô
            # z14 ra, và không báo lỗi gì cả.
            s["sources"][ten] = {"type": "vector", "url": nguon_o,
                                 "minzoom": 0, "maxzoom": MAXZOOM_O}

    uu_tien_tieng_viet(s)
    thay_lop_poi(s)

    # Nền thế giới: chèn NGAY SAU `background`, tức dưới mọi lớp Việt Nam.
    # Thứ tự quan trọng — đặt lên trên thì nó che mất bản đồ chi tiết.
    nguon_tg = NGUON_THE_GIOI_MAY if nguon_o == NGUON_O_MAY else NGUON_THE_GIOI
    # Khai maxzoom thẳng, cùng lý do với nguồn Việt Nam ở trên.
    s["sources"]["the-gioi"] = {"type": "vector", "url": nguon_tg,
                                "minzoom": 0, "maxzoom": MAXZOOM_THE_GIOI}
    # Hai tệp nhỏ nhúng thẳng, như dữ liệu chủ quyền: tên nước và vùng Việt
    # Nam. Thiếu thì bỏ qua lớp dùng chúng chứ KHÔNG bịa ra — cùng luật với
    # lớp chủ quyền.
    for ten_nguon, duong in (("ten-nuoc", TEN_NUOC), ("viet-nam", VIET_NAM)):
        if duong.is_file():
            s["sources"][ten_nguon] = {
                "type": "geojson",
                "data": json.loads(duong.read_text("utf-8")),
            }
    co = set(s["sources"])
    lop_tg = [l for l in lop_the_gioi() if l.get("source", "the-gioi") in co]
    vi_tri = 1 if s["layers"] and s["layers"][0].get("type") == "background" else 0
    s["layers"] = s["layers"][:vi_tri] + lop_tg + s["layers"][vi_tri:]

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
    ids = [l["id"] for l in s["layers"]]
    kd("chu-quyen-vung" not in ids, "thiếu dữ liệu chủ quyền thì không bịa lớp ra")

    # POI: badge phải thay đúng chỗ ba lớp poi-level-*, và phải nằm TRƯỚC lớp
    # chủ quyền. Nối vào cuối là POI vẽ đè lên tên đảo.
    gia3 = {"version": 8, "sources": {}, "layers": [
        {"id": "duong", "type": "line"},
        {"id": "poi-level-1", "type": "symbol"},
        {"id": "poi-level-2", "type": "symbol"},
        {"id": "poi-level-3", "type": "symbol"},
        {"id": "nhan-cuoi", "type": "symbol"},
    ]}
    thay_lop_poi(gia3)
    ids3 = [l["id"] for l in gia3["layers"]]
    kd(ids3 == ["duong", "poi-badge", "poi-nhan", "nhan-cuoi"],
       "badge POI thay đúng chỗ ba lớp poi-level, giữ nguyên thứ tự quanh nó")
    kd(not any(l["id"].startswith("poi-level") for l in s["layers"]),
       "style thật không còn lớp poi-level-* cũ")
    ten_lop = [l["id"] for l in s["layers"]]
    kd(ten_lop.index("poi-badge") < ten_lop.index("chu-quyen-vung"),
       "POI nằm dưới lớp chủ quyền") if "chu-quyen-vung" in ten_lop else None
    kd(lam_nhat("#d9353a") != "#d9353a" and lam_nhat("#ffffff") == "#ffffff",
       "làm nhạt màu đúng hướng, trắng thì giữ trắng")

    # Nhãn: không được còn `nonlatin` ở bất cứ đâu. Còn một chỗ là TileServer
    # GL có thể 500 cả ô, và bản đồ có thể in tên Trung Quốc ở Biển Đông.
    van_ban_nhan = json.dumps([l.get("layout", {}).get("text-field")
                               for l in s["layers"]], ensure_ascii=False)
    kd("nonlatin" not in van_ban_nhan, "không còn {name:nonlatin} ở nhãn nào")

    gia2 = {"version": 8, "sources": {}, "layers": [
        {"id": "a", "type": "symbol", "layout": {"text-field": "{name:latin}\n{name:nonlatin}"}},
        {"id": "b", "type": "symbol", "layout": {"text-field": "{ref}"}},
    ]}
    so = uu_tien_tieng_viet(gia2)
    kd(so == 1, "chỉ sửa nhãn tên, không đụng nhãn {ref} của biển số đường")
    kd(gia2["layers"][0]["layout"]["text-field"][1][1] == "name:vi",
       "nhãn ưu tiên name:vi trước")
    kd(gia2["layers"][1]["layout"]["text-field"] == "{ref}", "{ref} giữ nguyên")

    # Nền thế giới phải nằm NGAY SAU background và TRƯỚC mọi lớp Việt Nam.
    # Đặt nhầm lên trên là nó che cả bản đồ chi tiết bằng một mảng màu.
    kd(ids[0] == "nen" and ids[1] == "the-gioi-dat",
       "nền thế giới chèn ngay sau background")
    kd(all(l.get("maxzoom") == 7 for l in s["layers"] if l["id"].startswith("the-gioi")),
       "lớp thế giới chỉ sống tới z7, không đè lên bản đồ chi tiết")
    kd(s["sources"]["the-gioi"]["url"].startswith("pmtiles://"),
       "nguồn thế giới trỏ vào tệp PMTiles của mình")

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
