# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Toàn bộ kho này viết bằng tiếng Việt: tài liệu, chú thích, **và cả tên tệp / tên
hàm / tên biến** (`cauhinh.js`, `dung-style.py`, `phanLoaiPhanHoi`, `o_dia_hinh`).
Giữ đúng quy ước đó khi thêm mã mới.

## Lệnh

```bash
bash scripts/tai-vendor.sh          # một lần: MapLibre, PMTiles, font, sprite -> web/vendor/
python scripts/dung-style.py        # dựng web/style/*.json từ web/style-goc.json
python scripts/dung-o-dia-hinh.py   # tải DEM + dựng ô địa hình/độ dốc cả tỉnh Ninh Bình
python scripts/dung-o-ve-tinh.py    # tìm cảnh Sentinel-2 + dựng ô vệ tinh (cần Docker)
python scripts/dung-o-ve-tinh.py --chi-tim   # chỉ xem chọn được cảnh nào, không dựng
python scripts/capnhat-osm.py       # dựng lại ô nền từ OSM mới rồi đổi sang (blue/green)
python scripts/capnhat-osm.py --chi-kiem     # kiểm tệp đang phục vụ, không dựng
python scripts/capnhat-osm.py --quay-lai     # trả về bản trước
python scripts/chay-demo.py         # máy chủ dev http://localhost:8080 (ô bản đồ GIẢ)
python scripts/chay-demo.py 9000    # đổi cổng

docker compose up -d                # máy chủ THẬT http://localhost:8088 (ô thật)
docker compose logs -f o-raster     # log TileServer GL
docker compose down                 # giữ cache ô; thêm -v để xoá luôn cache
```

`chay-demo.py` và `docker compose` khác nhau ở chỗ nào: cái đầu sinh ô giả tại
chỗ, chạy được khi chưa có `vietnam.pmtiles`; cái sau là chính thứ sẽ đem lên
máy chủ. Trang demo giống hệt nhau, chỉ khác cổng.

Kiểm tra — không có framework test, mỗi tệp tự mang assert của nó:

```bash
python scripts/dung-style.py  --self-check   # style: hết URL ngoài, lớp chủ quyền đúng chỗ
python scripts/chay-demo.py   --self-check   # mã hoá terrarium, phạm vi ô, PNG sinh ra
python scripts/dung-o-dia-hinh.py --self-check  # mã hoá hàng loạt, nội suy, góc dốc, bảng màu
python scripts/dung-o-ve-tinh.py  --self-check  # vùng phủ khớp ô địa hình, ghi công
python scripts/capnhat-osm.py     --self-check  # bắt được tệp PMTiles hỏng/co/tụt zoom
python scripts/qgis-inventory.py --self-check
http://localhost:8080/?self-check            # assert của kiem-o.js, kết quả ở console
```

Build ô nền đường phố (cần `data/planetiler.jar`, đã có trong `data/`):

```bash
java -Xmx6g -jar data/planetiler.jar --download --area=vietnam \
  --output=data/tiles/vietnam.pmtiles --download-dir=data/osm
```

## Kiến trúc

Đây là dự án **máy chủ bản đồ dùng chung** cho nhiều ứng dụng (E-Commune SPA,
Zalo Mini App...). Nguyên tắc gốc: *không tự viết máy chủ nào* — ghép phần mềm
mã nguồn mở bằng `docker-compose`. Phần tự viết chỉ có style JSON, một trang UI
demo, vài script build dữ liệu. `PLAN.md` là nguồn sự thật về phạm vi và các
phase; `KHAO-SAT.md` là tham chiếu (Goong, so sánh Google Maps, tiếp nhận QGIS).

Luồng dữ liệu:

```
data/osm/*.osm.pbf --(Planetiler)--> data/tiles/vietnam.pmtiles
web/style-goc.json --(dung-style.py)--> web/style/nen-pho.json
      + web/chu-quyen/chu-quyen-dao.json (CHƯA CÓ)
web/index.html đọc style + web/phamvi.json --> MapLibre
```

Ba quyết định định hình mọi thứ:

1. **PMTiles một tệp, không tile server.** Trình duyệt đọc từng lát bằng HTTP
   Range. `chay-demo.py` phải tự trả 206 vì `SimpleHTTPRequestHandler` không
   biết `Range` (trả 200 kèm cả tệp thì thư viện PMTiles đọc nhầm vị trí).
2. **Lớp chủ quyền Hoàng Sa / Trường Sa nằm SẴN trong style do máy chủ phát**
   (`scripts/dung-style.py`), không phải việc của client. Đây là lợi ích chính
   của việc tách máy chủ riêng: cổng kiểm tra co từ "so từng byte giữa N bản sao
   ở N ứng dụng" về "kiểm style của máy chủ có đủ lớp". `PLAN.md` mục 4.
3. **Mọi tham số chạy đọc từ tệp, không ghi cứng trong trang.** URL nguồn ô và
   vị trí mở đầu ở `web/cauhinh.js`; bounds / zoom / mã hoá / ghi công / chú
   giải độ dốc ở `web/phamvi.json`. Mở rộng vùng ô địa hình thì không phải sửa
   frontend. `index.html` không được ghi cứng URL nào.

Trang demo cố tình **không** có nghiệp vụ: không đọc dữ liệu theo xã, không
đăng nhập, không vẽ/sửa. Nó là **bộ kiểm tra chạy được** của máy chủ.

## Luật bất biến — vi phạm là bản đồ trắng mà mọi request vẫn xanh

- **Không bao giờ gọi `map.setStyle()`.** Nó reset toàn bộ source và layer, tức
  là xoá lớp chủ quyền. Đổi nền bằng bật/tắt `visibility` của cụm lớp.
- **Lớp `chu-quyen-*` phải ở CUỐI `layers` và không có `layout.visibility`.**
  Không công tắc tắt, kể cả đang bật. Lớp phủ mới phải chèn *trước* nó.
- **Thiếu `web/chu-quyen/chu-quyen-dao.json` thì không được bịa lớp ra** —
  `dung-style.py` in cảnh báo, trang hiện dải đỏ. Im lặng vẽ bản đồ thiếu lớp
  là lỗi nặng nhất của dự án.
- **Tên đảo chỉ lấy từ dữ liệu chủ quyền, không lấy từ OSM** — kể cả OSM tự
  build: ô nền OSM ghi "三沙市 Sansha" và vẽ ranh yêu sách ở Biển Đông.
- **HTTP 200 kèm `text/html` phải tính là LỖI.** Đó là bẫy nginx để ô rơi vào
  SPA fallback rồi trả `index.html`. Xem cả `Content-Type`, không chỉ xem mã.
- **MapLibre coi ô 404 là ô rỗng và KHÔNG bắn event `error`** — chuỗi nguồn dự
  phòng cũng không nhảy. Đó là lý do `kiem-o.js` tự gọi thử từng nguồn, và
  `index.html` đếm `queryRenderedFeatures()` trong `map.on('idle')`.
- **Sprite phải là URL tuyệt đối** khi style đưa vào MapLibre dạng đối tượng;
  `/vendor/sprite/sprite` bị từ chối và *cả style không nạp*. ⛔ Nhưng **đừng
  chuẩn hoá `glyphs` bằng `new URL()`** — nó mã hoá `{}` thành `%7B` và MapLibre
  báo thiếu token `{fontstack}`.
- **Terrain: nội suy ĐỘ CAO trước, mã hoá terrarium sau.** Resize ảnh đã mã hoá
  làm bilinear nội suy riêng từng kênh R/G/B, vỡ mã ở biên byte, ra mặt đất bậc
  thang. Áp dụng cho cả pipeline thật ở Phase 3.
- **Không nhúng CDN, không gọi mạng ngoài từ trang.** Máy chủ nội bộ không có
  DNS ra ngoài. Mọi thư viện/font/sprite nằm trong `web/vendor/`
  (`tai-vendor.sh` kiểm từng tệp, thấy `<!doctype` là dừng — `curl -f` coi
  trang lỗi HTML mã 200 là thành công).
- **Giữ ghi công nguồn dữ liệu.** Giấy phép OpenMapTiles bắt buộc hiện thấy
  được; đừng rút gọn `ghiCong` trong `cauhinh.js`.
- **Ranh giới dữ liệu: máy chủ bản đồ chỉ chứa dữ liệu dùng chung, không có cột
  `tenant_id`.** Dữ liệu theo xã ở lại `core` / service `gis` của E-Commune.
  Dải phân chia đầy đủ ở `PLAN.md` mục 9.

## Lưu ý khi làm việc

- `chay-demo.py` **chỉ dùng khi phát triển**: sinh ô giả tại chỗ, không lấy ô
  của ai. Nó cố tình không giả lập `/chu-quyen/chu-quyen-dao.json`.
- Ngoài bounds trong `phamvi.json` (hiện phủ cả tỉnh Ninh Bình,
  `105.5, 19.8, 106.7, 20.8`) MapLibre không gọi ô địa hình nên mặt đất phẳng
  — **đó không phải lỗi**.
- `scripts/dia_hinh_chung.py` là tệp DUY NHẤT trong kho đặt tên bằng gạch
  dưới, vì Python không import được tên có gạch ngang. Nó giữ phép mã hoá
  terrarium dùng chung giữa ô giả (`chay-demo.py`) và ô thật
  (`dung-o-dia-hinh.py`) — đừng chép lại phép đó vào chỗ khác.
- `data/dem/*.hgt.gz` (26 MB) và `data/s2/*.tif` (1.45 GB) là nguồn tải về,
  dựng lại ô không cần mạng. Xoá được, chạy lại script là tải lại.
  `data/ve-tinh-tam/` (374 MB) là ảnh ghép trung gian, xoá ngay sau khi dựng
  xong cũng được.
- **Đổi ô nền thì phải XOÁ cache của nginx.** Ô raster cache 7 ngày
  (`proxy_cache_valid 200 7d`). Đổi `vietnam.pmtiles` mà quên xoá cache thì cả
  tuần sau người dùng vẫn xem bản đồ cũ, trong khi mọi bước đều báo thành
  công. `capnhat-osm.py` coi việc xoá cache là một bước của việc đổi, không
  phải việc dọn dẹp làm sau.
- **TileServer GL mở tệp PMTiles lúc khởi động và giữ nguyên.** Đổi tệp dưới
  chân nó thì phải `docker compose restart o-raster`, symlink cũng không cứu
  được. Vì vậy blue/green ở kho này là đổi TÊN TỆP rồi nạp lại dịch vụ, không
  phải đổi symlink như PLAN.md mục 10 viết.
- **Đừng để GDAL đọc COG từ xa (`/vsicurl/`) trong lúc chiếu ảnh.** Đã hỏng
  thật: ba request rớt với `response_code=0`, `gdalwarp` vẫn chạy tới 100% và
  vẫn ghi ra tệp — chỉ khác là tệp thủng lỗ và mã thoát là 1. Tải hẳn về,
  kiểm đủ `Content-Length`, rồi mới dựng.
- Mọi dẫn chứng `file:line` trong `PLAN.md` trỏ sang kho E-Commune (kho khác),
  nên sẽ lệch dần. Hiện trạng ở mục 1 là ảnh chụp ngày 13/11/2026.
- Kho này **chưa được git theo dõi**.
