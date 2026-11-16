# Khảo sát — tham chiếu

Tệp này là **tham chiếu, không phải việc cần làm**. Kế hoạch ở `PLAN.md`.

Ba phần:
1. Goong Maps — dùng ở đâu, không dùng ở đâu
2. So sánh với Google Maps — cái gì làm được, cái gì không
3. Tiếp nhận file QGIS có sẵn

---

## 1. Goong Maps

Goong (goong.io) là dịch vụ bản đồ hosted của Việt Nam, **không self-host
được**. Điểm mạnh kỹ thuật: API có format request/response giống Google Maps,
nên code đang gọi Google chuyển sang Goong gần như không phải viết lại.

> Nội dung dựa trên `help.goong.io` và `goong.io/pricing` đọc **tháng 11/2026**.
> Goong có song song V1 và V2, cần xác nhận lại trước khi code.

### Goong có gì

| API | Chức năng | Ghi chú |
|---|---|---|
| Autocomplete (V1, V2) | Gợi ý địa chỉ theo từ khoá | Điểm mạnh nhất |
| Place Detail (V1, V2) | Chi tiết địa điểm | |
| Children ID (V2) | Địa điểm con theo ID cha | Cửa hàng trong TTTM, căn hộ trong toà nhà |
| Geocode (V1, V2) | Địa chỉ ↔ toạ độ, cả hai chiều | |
| Geocode Street (V2) | Geocode cấp đường | |
| Directions (V1, V2) | Chỉ đường turn-by-turn | Trả `html_instructions` tiếng Việt sẵn |
| Distance Matrix | Ma trận khoảng cách / thời gian | |
| Trip | Tối ưu tuyến nhiều điểm (TSP) | |
| Speed Limit | Tốc độ giới hạn + biển báo + camera giao thông | Không có bản tương đương mã nguồn mở |
| Static Map | Bản đồ dạng ảnh PNG | |
| Map Load | Vector tile + SDK, 100+ style mẫu | SDK là fork MapLibre/Mapbox |
| DEM tiles | Raster-dem cho địa hình 3D | Encoding `terrarium` |

SDK: Web, iOS, Android, Flutter, React Native, plugin WordPress.

### Goong không có

| Thiếu | Hệ quả |
|---|---|
| Isochrone | Cần vùng tiếp cận theo thời gian thì Valhalla là bắt buộc |
| Map matching / snap cả trace | Xử lý GPS trace thì Valhalla `trace_route` là bắt buộc |
| Tham số traffic trong Directions | Xem phần dưới |
| Profile xe máy | `vehicle` chỉ có `car`, `bike`, `taxi`, `truck`, `hd`. Không có `motorcycle` |
| Profile đi bộ | Không thấy trong tài liệu |
| Ảnh vệ tinh, Street View, 3D Tiles | Không cung cấp |
| Giờ mở cửa, điện thoại, website, ảnh, đánh giá, rating | Place Detail V2 không trả các field này |
| Self-host | Không có |

### Goong không có traffic thời gian thực

`Directions V2` chỉ nhận `origin`, `destination`, `vehicle`, `alternatives`,
`api_key`. Không có `departure_time`, không có `duration_in_traffic`, không có
tham số traffic nào — tức không có cách nào để *yêu cầu* ETA theo traffic, cũng
không có field nào để *nhận* nó.

Trang marketing của Goong có nói về "thông tin giao thông phức tạp tại Việt
Nam", nhưng đó là văn bán hàng, không phải tham số API. `Speed Limit API` là
tốc độ giới hạn **tĩnh** theo đoạn đường, không phải tốc độ dòng xe thực tế.

Kết luận: **không có lý do kỹ thuật nào để Goong làm dẫn đường chính.** Ngược
lại, Valhalla hơn ở Việt Nam vì có profile `motorcycle` và `motor_scooter` — xe
máy là phương tiện áp đảo mà Goong không có profile riêng.

### Bốn thứ Goong thắng rõ

**1. Ánh xạ địa chỉ hành chính cũ ↔ mới — giá trị cao nhất.**

Place Detail V2 trả kèm:
- `compound` — phường/xã + tỉnh hiện hành
- `deprecated_compound` — đơn vị hành chính cũ
- `deprecated_description` — địa chỉ dạng cũ
- `formatted_address` — đã cập nhật theo địa giới mới

Sau đợt sáp nhập tỉnh/xã, đây là bài toán thật mà **không có nguồn mở nào
giải**: dữ liệu cũ trong DB ghi địa chỉ theo đơn vị cũ, người dùng gõ theo đơn
vị mới hoặc ngược lại. OSM không có mapping này, Nominatim và Photon cũng không.

Nếu hệ thống có dữ liệu địa chỉ lịch sử thì đây là lý do mạnh hơn cả
autocomplete để dùng Goong.

**2. Speed Limit API.**

```
GET https://speedlimit.goong.io/api/v1/speedlimit?lat=&lon=&bearing=&api_key=
```

Trả: `name` (tên đường), `latitude`/`longitude` đã snap vào đường, `max_speed`,
`re_speed` (chiều ngược, chỉ có khi không truyền `bearing`), `distance` (km từ
điểm hỏi tới điểm khớp), `id_sy`. Tài liệu nói có cả dữ liệu biển báo và camera
giao thông; changelog ghi đã đồng bộ toàn quốc 3–9/2025.

Tag `maxspeed` trong OSM ở Việt Nam rất thưa, nên đây là dữ liệu Goong thắng
rõ. Hàm này snap toạ độ vào đường nên là một dạng snap-to-road đơn điểm — không
thay được map matching cả trace, nhưng đủ cho "xe đang ở đường nào, giới hạn
bao nhiêu". Dữ liệu camera giao thông không có nguồn mở nào tương đương.

**3. DEM terrain tiles.**

```js
map.addSource('dem', {
  type: 'raster-dem',
  tiles: [`https://dem.goong.io/{z}/{x}/{y}.png?api_key=${mapKey}`],
  encoding: 'terrarium',
  tileSize: 256,
  maxzoom: 15
});
// hillshade gợi ý từ docs: exaggeration 0.6, shadow #473B24,
// highlight #ffffff, accent #888888
```

Docs lưu ý phải add source **sau** event `style.load`, vì `map.setStyle()` reset
toàn bộ source và layer.

Nhưng **tự build vẫn hơn**: `terrarium` là chuẩn mở của Mapzen/Tilezen, và dữ
liệu nền gần như chắc chắn cũng là SRTM/Copernicus — cùng nguồn free mà mình tự
build được. Dùng Goong DEM thì tốn tiền theo lượt, giới hạn `maxzoom 15`, phụ
thuộc uptime, để đổi lấy đúng con số độ cao mình tự có miễn phí.

Chỉ dùng như lối tắt tạm nếu muốn có địa hình 3D sớm mà chưa muốn làm pipeline
DEM. Dự án này đã có ô địa hình tự build nên không cần.

**4. Children ID V2 và Geocode Street V2.**

Children ID lấy địa điểm con theo ID cha: cửa hàng trong trung tâm thương mại,
căn hộ trong toà nhà, gian hàng trong chợ. OSM gần như không map mức này ở VN.
Geocode Street hữu ích khi chỉ có tên đường mà không có số nhà.

### Dẫn đường: Valhalla hay Goong

| | Valhalla (self-host) | Goong Directions |
|---|---|---|
| Traffic thời gian thực | Không | Không (không có tham số) |
| Profile xe máy | **Có** (`motorcycle`, `motor_scooter`) | Không |
| Profile đi bộ | Có | Không thấy trong docs |
| Profile xe tải có ràng buộc | Có, chi tiết | Có `truck`, mức chi tiết chưa rõ |
| Isochrone | **Có** | Không |
| Map matching | **Có** | Không |
| Distance matrix | Có | Có |
| Tối ưu nhiều điểm | Có | Có (Trip API) |
| Hướng dẫn tiếng Việt | Locale `vi`, chất lượng khá | Native, sẵn trong response |
| Dữ liệu đường VN | Tag OSM, nhiều nơi thiếu | Dữ liệu riêng, khả năng đầy hơn |
| Số request | Không giới hạn | Quota / trả phí |
| Chạy mạng nội bộ | Được | Không |

Khuyến nghị: **Valhalla làm dẫn đường chính.** Goong Directions chỉ dùng nếu
thực nghiệm cho thấy dữ liệu đường của Goong tốt hơn OSM rõ rệt ở khu vực quan
tâm — việc này **phải đo**, không suy luận được. Cách đo: lấy ~100 cặp điểm
thật, chạy qua cả hai, so chiều dài và tính hợp lý của tuyến.

### Chi phí (11/2026)

- **Free:** $100 credit cho người mới; 30.000 request/tháng, 5 req/s, ~1.000
  map load.
- **Trả phí dưới 100k request/tháng** (USD/1.000 request): Map Load $3.00 ·
  Directions $2.50 · Distance Matrix $2.50 · Autocomplete $1.40 · Reverse
  Geocode $1.50 · Static Map $1.00.
- Giảm giá theo bậc 100k / 200k / 500k. Trên 500k thì thương lượng.
- Gói trả trước (VND): Lite 30k req < 2tr · Basic 100k req > 2tr · Pro 200k
  req > 5tr · Business 400k req > 10tr.

**Phép tính quyết định:** 100.000 request Directions/tháng = **$250/tháng**.
Valhalla self-host = **$0** chi phí biên, chỉ tốn ~20 phút build.

Ngược lại, 30k request free/tháng là thừa đủ cho phần dự phòng geocoding —
Photon xử lý phần lớn truy vấn, Goong chỉ nhận phần khó.

### Nên và không nên dùng Goong ở đâu

**Nên:**

| Chỗ | Lý do |
|---|---|
| Địa chỉ hành chính cũ ↔ mới (`deprecated_compound`) | Giá trị cao nhất, không nguồn mở nào có |
| Autocomplete / geocode địa chỉ VN | OSM gần như không có số nhà, hẻm/ngách/kiệt, tên toà nhà |
| Speed Limit API | `maxspeed` OSM ở VN rất thưa; thêm biển báo + camera giao thông |
| Children ID V2 | Địa điểm con trong toà nhà, TTTM |
| Geocode Street V2 | Khi chỉ có tên đường |
| Làm chuẩn để đo chất lượng | Biết geocoder tự host còn sai bao nhiêu, và khi nào đủ tốt để bỏ Goong |

**Không nên:**

| Chỗ | Lý do |
|---|---|
| Ô nền / Map Load | $3/1.000 lượt xem, và phá bỏ lý do self-host. PMTiles tự host là $0 |
| Dẫn đường chính | Không traffic, thiếu profile xe máy và đi bộ, $2.50/1k |
| Isochrone, map matching | Không có |
| Vệ tinh, Street View, 3D Tiles | Không cung cấp |
| Địa hình DEM lâu dài | Cùng nguồn dữ liệu free, `maxzoom 15`, tốn tiền theo lượt |
| Thông tin doanh nghiệp, review, ảnh | Place Detail không trả |
| Lưu kết quả vĩnh viễn vào DB | Xem cảnh báo giấy phép bên dưới |

### Cách ghép vào kiến trúc

Goong nằm **sau** proxy, không bao giờ gọi trực tiếp từ trình duyệt:

```
Trình duyệt → /geocode?q=...   → Photon (self-host)
                                  └─ rỗng / điểm thấp → Goong Autocomplete
Trình duyệt → /place/{id}      → Goong Place Detail (cache ngắn)
Trình duyệt → /place/{id}/kids → Goong Children ID
Trình duyệt → /speedlimit?...  → Goong Speed Limit
Trình duyệt → /route?...       → Valhalla
Trình duyệt → /isochrone?...   → Valhalla (Goong không có)
Trình duyệt → /match?...       → Valhalla (Goong không có)
Trình duyệt → /terrain/*       → PMTiles tự build
```

Lợi ích:
1. API key không lộ ra client.
2. Đổi hoặc bỏ Goong không cần sửa frontend — khi geocoder tự host đủ tốt thì
   xoá nhánh dự phòng là xong.
3. Kiểm soát chi phí: Photon xử lý phần lớn truy vấn nên giữ được trong 30k
   free/tháng.
4. Đặt được cache ngắn và giới hạn tốc độ. **Quan trọng:** Goong giới hạn
   5 req/s ở tier free, không có rate limit thì burst sẽ lỗi.

### Bảo mật API key

Goong cho giới hạn key theo:
- URL/referrer, có wildcard: `http*://example.com/*`, `http*://*.example.com/*`
- IP — dùng cho server backend

Kiến trúc này gọi Goong từ server nên dùng key **giới hạn theo IP của server**.
Không dùng key referrer, không để key xuống trình duyệt.

**Rủi ro vận hành:** docs Goong ghi rõ hệ thống tự động vô hiệu hoá key nếu
lượng request tăng đột biến bất thường. Một đợt traffic tăng thật, hoặc một bug
vòng lặp trong code, có thể làm mất chức năng tìm địa chỉ giữa giờ làm việc mà
không báo trước.

Đây là lý do kỹ thuật để Photon làm lớp chính, Goong làm lớp phụ — không phải
ngược lại. Key bị khoá thì tìm kiếm xuống cấp chứ không sập. Nên có cảnh báo
khi tỉ lệ lỗi Goong tăng.

### Cảnh báo giấy phép

Điều khoản của các dịch vụ map hosted thường **cấm lưu trữ lâu dài kết quả
geocoding** và **cấm dùng dữ liệu của họ để xây database riêng**:

- Cache ngắn hạn cho hiệu năng: thường được phép.
- Ghi vĩnh viễn toạ độ/POI Goong trả về vào DB thành lớp của mình: rất có thể
  vi phạm.

**Chưa đọc được ToS cụ thể của Goong** (chỉ đọc được docs và pricing). Nếu định
lưu POI của Goong thành lớp riêng thì phải xác nhận điều khoản trực tiếp hoặc
hỏi Goong trước khi làm.

### Ước tính thời gian nếu làm

- Dự phòng autocomplete/geocode qua Goong: +0.5 ngày
- Proxy Place Detail + Children ID + cache + rate limit: +0.5 ngày
- Ánh xạ địa chỉ cũ ↔ mới qua `deprecated_compound`: +1 ngày
- Proxy Speed Limit: +0.5 ngày

Tối đa +2.5 ngày nếu lấy hết. Dẫn đường giữ ở Valhalla nên không phát sinh thêm.

**Nguồn (đọc 11/2026):**
[help.goong.io](https://help.goong.io/) ·
[docs.goong.io/rest](https://docs.goong.io/rest/) ·
[REST API V1](https://help.goong.io/kb/rest-api/) ·
[REST API V2](https://help.goong.io/kb/rest-api-v2/) ·
[Directions V2](https://help.goong.io/kb/rest-api-v2/directions-rest-api-v2/directions-v2/) ·
[Place Detail V2](https://help.goong.io/kb/rest-api-v2/place-detail-rest-api-v2/place-detail-place-detail-v2/) ·
[Speed Limit](https://help.goong.io/kb/rest-api/speed-limit/speed-limit-canh-bao-gioi-han-toc-do/) ·
[DEM + MapLibre](https://help.goong.io/kb/website-javascrip-api/dem/tich-hop-ban-do-dia-hinh-dem-voi-maplibre-tren-goong-map/) ·
[Giới hạn URL/IP cho key](https://help.goong.io/kb/gioi-thieu-tong-quan/dang-ky-va-tao-key/tao-gioi-han-ulr-ip-cho-api-key-yeu-to-quan-trong-bao-mat-he-thong/) ·
[Changelog Speed Limit](https://help.goong.io/kb/changelog/speed-limit-changelog/) ·
[Pricing](https://goong.io/pricing/)

---

## 2. So sánh với Google Maps

Phần lớn *bề mặt API* của Google Maps là làm được. Những chỗ không làm được đều
có cùng một nguyên nhân, và nó không phải phần mềm:

> Google thắng bằng **hạ tầng thu thập dữ liệu** — đội xe Street View chạy khắp
> thế giới, hàng tỷ điện thoại Android gửi về tốc độ di chuyển, hàng trăm triệu
> người viết đánh giá. Tự host được mọi phần mềm, nhưng không tự host được ba
> thứ đó.

Ký hiệu: ✅ làm được · ⚠️ một phần, cần tiền hoặc công · ❌ không thực tế

### A. Bản đồ và hiển thị

| Chức năng | | Cách làm / lý do |
|---|---|---|
| Nền vector đa zoom | ✅ | Planetiler + PMTiles |
| Nhãn tiếng Việt | ✅ | OSM `name:vi` |
| Style tuỳ biến, dark mode | ✅ hơn Google | Toàn quyền sửa style JSON, Google chỉ cho vài preset |
| Bản đồ offline | ✅ hơn Google | Tải cả file `.pmtiles`, không giới hạn vùng hay thời hạn |
| Địa hình / topo | ✅ | Copernicus DEM |
| Chế độ quả cầu | ✅ | MapLibre globe projection |
| Nhà 3D dạng khối | ✅ | `fill-extrusion` từ `building:height` — nhưng VN thiếu tag này |
| Ảnh vệ tinh | ⚠️ **gap lớn nhất** | Sentinel-2 free nhưng 10 m/pixel, Google ~0.3–0.5 m. Khác ~30 lần: thấy khu phố, không thấy mái nhà. Muốn bằng thì phải mua Maxar/Airbus/Planet, hoặc bay drone cho vùng nhỏ |
| 3D photorealistic | ⚠️ chỉ vùng nhỏ | Google dùng ảnh hàng không photogrammetry cả thành phố. Tự làm: drone + OpenDroneMap → 3D Tiles. Khả thi cho một khu, không khả thi cho một tỉnh |
| Street View | ⚠️ có phần mềm, không có dữ liệu | **Panoramax** self-host được, có blur mặt/biển số sẵn. Nhưng độ phủ Việt Nam gần như bằng 0 — phải tự chụp bằng camera 360 gắn xe |
| Bản đồ trong nhà | ⚠️ | OSM indoor + IndoorEqual, nhưng VN hầu như chưa ai map |
| Ảnh vệ tinh lịch sử | ✅ hơn Google | Sentinel-2 archive từ 2015 qua STAC, truy vấn theo ngày tuỳ ý. Google không mở API này |

### B. Tìm kiếm và địa điểm

| Chức năng | | Cách làm / lý do |
|---|---|---|
| Autocomplete địa chỉ | ✅ | Photon + Goong cho phần khó |
| Geocode / reverse geocode | ✅ | Photon / Nominatim |
| Plus Codes | ✅ | Open Location Code là thuật toán mở |
| Tìm POI | ✅ | **Overture Maps Places** (~81M, 9/2026) + **Foursquare OS Places** (100M+, 22 thuộc tính, cập nhật hàng tháng). Cả hai Apache 2.0 / CDLA — dùng thương mại được, tải GeoParquet từ AWS Open Data |
| Giờ mở cửa, điện thoại, website | ⚠️ | Overture + FSQ có một phần, độ phủ không đều. Goong không trả |
| Ảnh địa điểm | ⚠️ | Wikimedia Commons (có toạ độ) + Panoramax. Thưa |
| Đánh giá, rating | ❌ | Không có nguồn mở nào. Chỉ có nếu tự xây hệ người dùng góp nội dung và có người dùng thật — đó là bài toán sản phẩm |
| Mức đông theo giờ | ❌ | Cần telemetry vị trí từ hàng triệu thiết bị |
| Chủ shop tự quản lý thông tin | ⚠️ | Tự xây được, nhưng là tính năng sản phẩm riêng |

### C. Dẫn đường

| Chức năng | | Cách làm / lý do |
|---|---|---|
| Route ô tô / xe máy / đi bộ / xe đạp | ✅ | Valhalla, có `motorcycle` + `motor_scooter` |
| Turn-by-turn tiếng Việt | ✅ | Valhalla locale `vi` |
| Tuyến thay thế | ✅ | Valhalla `alternates` |
| Ma trận khoảng cách | ✅ | Valhalla `/sources_to_targets` |
| Tối ưu nhiều điểm | ✅ | Valhalla `/optimized_route` |
| Map matching / snap-to-road | ✅ | Valhalla `/trace_route`, `/trace_attributes` |
| Độ cao dọc tuyến | ✅ | Valhalla `/height` |
| Isochrone | ✅ hơn Google | Valhalla `/isochrone`. Google không mở API này |
| Route xe lăn | ⚠️ | Valhalla hỗ trợ nhưng phụ thuộc tag OSM, VN thiếu |
| Cảnh báo tốc độ giới hạn | ⚠️ | `maxspeed` OSM ở VN rất thưa → Goong Speed Limit |
| Phí cầu đường | ⚠️ | OSM có `toll=yes` nhưng không có giá, phải tự nhập |
| Traffic thời gian thực | ❌ | Self-host không có nguồn. Goong cũng không expose tham số. Muốn có thì mua TomTom/HERE, hoặc tự dựng từ GPS đội xe của mình (chỉ đúng trên tuyến mình chạy) |
| ETA chính xác giờ cao điểm | ❌ | Hệ quả của dòng trên. Valhalla tính theo tốc độ tĩnh nên giờ cao điểm sẽ lạc quan đáng kể |
| Dẫn đường xe buýt | ⚠️ vướng dữ liệu | Phần mềm có sẵn: OpenTripPlanner 2 + GTFS. Nhưng GTFS Việt Nam rất thiếu — Hà Nội có feed qua World Bank nhưng bản mới nhất ~6/2020, TP.HCM không tìm thấy feed công khai. Muốn làm thật phải tự xây GTFS từ dữ liệu tuyến của Sở GTVT |

### D. API phụ trợ

| Chức năng | | Cách làm |
|---|---|---|
| Static Maps | ✅ | `mbgl-renderer` (MapLibre headless) |
| Elevation | ✅ | Valhalla `/height` hoặc TiTiler point query trên DEM |
| Time Zone | ✅ | `timezone-boundary-builder` + PostGIS point-in-polygon |
| Roads (snap) | ✅ | Valhalla `/trace_attributes` |
| Chất lượng không khí | ✅ | OpenAQ |
| Thời tiết | ✅ | Open-Meteo, free, không cần key |
| Định vị wifi/cell | ⚠️ | Mozilla Location Service đã tắt 3/2024. Thay bằng **BeaconDB** — public domain, dùng cùng format request như MLS nên code cũ chạy được. Độ phủ VN cần kiểm tra thực tế |
| Solar | ⚠️ | PVGIS có phủ toàn cầu, không chi tiết mức mái nhà như Google |
| Pollen | ❌ | Không có nguồn mở tương đương |

### E. Tính năng ứng dụng — tự xây, đều dễ

| Chức năng | | Ghi chú |
|---|---|---|
| Lưu địa điểm / danh sách | ✅ | Một bảng PostGIS |
| Chia sẻ vị trí trực tiếp | ✅ | WebSocket + PostGIS |
| Geofencing | ✅ | `ST_Contains` |
| Lịch sử di chuyển | ✅ | Bảng điểm + Valhalla map matching |
| Người dùng góp ý sửa bản đồ | ✅ hơn Google | iD editor → OSM, hoặc sửa thẳng DB |

### Tổng kết

| Mảng | Mức đạt được |
|---|---|
| Nền bản đồ, style, offline, địa hình, nhà 3D khối | 100%, có chỗ hơn Google |
| Dẫn đường trừ traffic | ~95%, có isochrone mà Google không mở |
| Geocoding và POI | ~85% với Overture + FSQ + Goong |
| API phụ trợ | ~90% |
| Ảnh vệ tinh | ~30% nếu không mua ảnh |
| Street View | ~5%, phải tự chụp |
| Giao thông công cộng | ~20% ở VN, thiếu GTFS chứ không thiếu phần mềm |
| Traffic và ETA thực | 0% nếu không mua API |
| Đánh giá, rating, mức đông | 0%, bài toán sản phẩm chứ không phải bài toán bản đồ |

### Bốn thứ cần quyết định sớm vì tốn tiền hoặc tốn người

1. **Ảnh vệ tinh độ phân giải cao** — mua hay chấp nhận Sentinel-2 10 m? Chi
   phí lớn nhất của cả dự án.
2. **Traffic thời gian thực** — mua TomTom/HERE hay chấp nhận ETA tĩnh?
3. **Street View** — có đầu tư camera 360 và người chạy tuyến không? Nếu không
   thì bỏ hẳn, đừng làm nửa vời.
4. **Giao thông công cộng** — có tiếp cận được dữ liệu tuyến từ Sở GTVT để tự
   xây GTFS không? Nếu không thì dựng OpenTripPlanner lên cũng không có gì để
   chạy.

Mục 1, 2, 4 là mua hoặc xin dữ liệu. Mục 3 là thuê người đi chụp. Không có mục
nào giải được bằng cách viết thêm code, nên cần quyết trước khi bắt tay.

**Nguồn (đọc 11/2026):**
[Overture Places](https://docs.overturemaps.org/guides/places/) ·
[Overture 9/2026](https://docs.overturemaps.org/blog/2025/09/24/release-notes/) ·
[Foursquare OS Places](https://opensource.foursquare.com/places-notice-txt/) ·
[FSQ giới thiệu](https://simonwillison.net/2024/Nov/20/foursquare-open-source-places/) ·
[Panoramax](https://en.wikipedia.org/wiki/Panoramax) ·
[BeaconDB](https://codeberg.org/beacondb/beacondb) ·
[GTFS Hà Nội](https://datacatalog.worldbank.org/search/dataset/0038236/Hanoi--Vietnam---General-Transit-Feed-Specification--GTFS-) ·
[OpenTripPlanner](https://gtfs.org/resources/producing-data/)

---

## 3. Tiếp nhận file QGIS có sẵn

Hiện kho **chưa có file `.qgs`/`.qgz` nào**. Phần này dùng khi có file thật.

Nguyên tắc: **đừng vẽ lại style.** QGIS Server đọc trực tiếp `.qgs` nên bước
đầu là publish nguyên trạng, rồi mới tối ưu những lớp thật sự cần nhanh.

### Bước 1 — Kiểm kê trước khi làm gì cả

```bash
python scripts/qgis-inventory.py qgis/
python scripts/qgis-inventory.py --self-check   # tự kiểm tra script
```

Script in ra từng lớp: provider, datasource, CRS, và cảnh báo những thứ sẽ làm
project vỡ trên server.

Bước này không bỏ được: **project chạy tốt trên desktop vẫn trắng trơn trên
server Linux**, gần như luôn vì một trong bốn nguyên nhân dưới.

### Bước 2 — Sửa bốn lỗi kinh điển

| Lỗi | Triệu chứng | Cách sửa |
|---|---|---|
| Đường dẫn tuyệt đối (`D:\data\x.shp`) | Lớp trắng, log "layer is not valid" | QGIS Desktop → Project Properties → General → Save paths: relative. Tốt hơn: đẩy dữ liệu vào PostGIS để project trỏ vào DB |
| Mật khẩu hoặc thiếu `service=` trong connection string | WMS trả ảnh trống, không có lỗi rõ | Dùng `~/.pg_service.conf` mount vào container + QGIS auth db qua `QGIS_AUTH_DB_DIR_PATH` và `QGIS_AUTH_PASSWORD_FILE`. **Nguyên nhân phổ biến nhất** |
| Chưa bật publish | `GetCapabilities` không thấy lớp | Project Properties → QGIS Server → bật WMS/WFS, chọn lớp được publish |
| Thiếu font hoặc SVG trong container | Nhãn sai font, ký hiệu thành ô vuông | Mount thư mục SVG + cài font vào image. Nhớ font tiếng Việt có dấu |

### Bước 3 — Phân loại từng lớp

Chọn theo **lớp dùng để làm gì**, không theo định dạng:

| Lớp kiểu này | Đưa vào | Lý do |
|---|---|---|
| Thematic, style phức tạp: rule-based, data-defined, blending, nhãn nhiều lớp | **QGIS Server WMS**, giữ nguyên `.qgs` | Style đã có sẵn; vẽ lại trong MapLibre tốn nhiều ngày và vẫn không giống. WMS chậm nhưng lớp này ít ai pan/zoom liên tục |
| Lớp người dùng pan/zoom nhiều, cần mượt | **Vector tile** | Nhanh hơn WMS cả bậc. Phải vẽ lại style trong MapLibre style JSON nên chỉ làm với lớp thật sự cần |
| Raster lớn, tĩnh: ảnh scan, DEM, ảnh bay | **COG → TiTiler** | `gdal_translate -of COG`. Không cần DB, không cần process |
| Dữ liệu tĩnh, nhiều feature, không sửa nữa | **PMTiles** | `ogr2ogr` → GeoJSON/FlatGeobuf → `tippecanoe` → `pmtiles`. Serve tĩnh, $0 |

Mặc định hợp lý: **mọi thứ vào QGIS Server trước** (chạy được trong một ngày),
rồi đo xem lớp nào chậm gây khó chịu và chỉ chuyển những lớp đó.

### Bước 4 — Đẩy dữ liệu vào PostGIS

```bash
# Shapefile / GeoPackage → PostGIS, reproject sang 3857 cho web
ogr2ogr -f PostgreSQL "PG:service=gis" data/ranh_gioi.shp \
  -nln ranh_gioi -lco GEOMETRY_NAME=geom -lco FID=id \
  -t_srs EPSG:3857 -s_srs EPSG:4326 -nlt PROMOTE_TO_MULTI

# Toàn bộ lớp trong một GeoPackage
ogr2ogr -f PostgreSQL "PG:service=gis" data/duan.gpkg -t_srs EPSG:3857

# Bắt buộc: index không gian. Thiếu cái này là WMS chậm thảm
psql service=gis -c 'CREATE INDEX ON ranh_gioi USING gist (geom);'
```

Sau khi dữ liệu ở PostGIS, mở lại project trong QGIS Desktop và trỏ lớp vào
PostGIS thay vì file. Lúc này cùng một `.qgs` chạy được cả trên desktop và
trong container.

**Lưu ý:** kho `gis` của E-Commune là kho riêng của service `gis`, không service
nào khác được nối vào. Nếu đẩy dữ liệu QGIS vào đó thì phải đi qua service
`gis`, không nối trực tiếp từ container QGIS Server.

### Lưu ý CRS cho dữ liệu Việt Nam

Dữ liệu VN hay dùng **VN-2000** — `EPSG:4756`, hoặc biến thể theo múi như
`EPSG:3405` (UTM 48N) và các hệ TM-3 địa phương. Web cần `EPSG:3857` hoặc
`4326`.

- QGIS Server reproject được on-the-fly cho WMS, không cần đổi dữ liệu.
- Vector tile thì **phải reproject sẵn** sang 3857.
- Độ chính xác chuyển datum phụ thuộc grid của PROJ. Nếu cần độ chính xác cao
  (địa chính) thì kiểm sai số bằng vài điểm mốc đã biết toạ độ, đừng tin mặc
  định.

### Các định dạng QGIS khác

| File | Là gì | Làm gì |
|---|---|---|
| `.qgs` / `.qgz` | Project (XML / zip) | Nguồn chính, publish qua QGIS Server |
| `.qml` | Style của một lớp | Giữ lại, QGIS Server dùng. Không chuyển sang MapLibre tự động được |
| `.sld` | Style chuẩn OGC | Chỉ cần nếu dùng GeoServer — kế hoạch này không dùng |
| `.qlr` | Layer definition | Import vào project rồi xử lý như lớp thường |
| `.qpt` | Template bố cục in | Giữ nguyên, QWC2 in PDF theo layout này |
| `.gpkg` | Dữ liệu, có thể chứa cả style trong bảng `layer_styles` | `ogr2ogr` vào PostGIS |
| `.shp` + `.dbf/.shx/.prj/.cpg` | Shapefile, **phải đủ bộ** | `ogr2ogr` vào PostGIS rồi bỏ shapefile |
| `.model3`, `.py` | Processing model / script | Chạy batch qua `qgis_process`, không liên quan web |
| `.gpkg-wal`, `.gpkg-shm` | Rác SQLite WAL | Xoá được, nhưng đóng QGIS trước cho sạch |

### Không nên làm

- **Đừng** publish QGIS Server làm nền bản đồ — chậm hơn vector tile cả bậc.
  Nền luôn là PMTiles.
- **Đừng** vẽ lại toàn bộ style sang MapLibre ngay từ đầu. Việc nhiều ngày, và
  phần lớn lớp không cần.
- **Đừng** để shapefile làm nguồn chạy thật — không có index tốt, không khoá
  được, giới hạn tên cột 10 ký tự. Import một lần rồi dùng PostGIS.

### Thời gian

Nếu đã có project QGIS sẵn: **1–2 ngày** để kiểm kê, sửa đường dẫn và auth, đẩy
dữ liệu vào PostGIS, publish. Chuyển lớp sang vector tile tính riêng, ~0.5
ngày/lớp tuỳ độ phức tạp của style.
