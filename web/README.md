# UI demo của máy chủ bản đồ

Một trang tĩnh, không build step, không framework, không phụ thuộc mạng ngoài.

Mục đích chính **không phải** để trưng cho người xem, mà là **bộ kiểm tra chạy
được** của máy chủ: demo lên đúng nghĩa là style, ô bản đồ và lớp chủ quyền
đều đúng. Đây là cách biết style ổn trước khi cắm vào 24 màn của E-Commune.

## Chạy

```bash
bash scripts/tai-vendor.sh      # một lần: MapLibre, PMTiles, font, sprite
python scripts/dung-style.py    # dựng web/style/nen-pho.json từ style gốc
python scripts/chay-demo.py     # http://localhost:8080
```

Nền đường phố cần tệp `data/tiles/vietnam.pmtiles`. Build bằng Planetiler:

```bash
java -Xmx6g -jar data/planetiler.jar --download --area=vietnam \
  --output=data/tiles/vietnam.pmtiles --download-dir=data/osm
```

Một tệp duy nhất, trình duyệt đọc từng lát bằng HTTP Range. Không cần tile
server cho nền phố.

`chay-demo.py` **chỉ dùng khi phát triển**: nó phục vụ `web/` và tự sinh ô bản
đồ giả tại chỗ, không gọi mạng ngoài, không lấy ô của ai. Ô địa hình được mã
hoá terrarium thật nên `setTerrain` và hillshade kiểm được đầy đủ.

Nó cố tình **không** giả lập `/chu-quyen/chu-quyen-dao.json`: thiếu lớp chủ
quyền thì trang phải hiện cảnh báo đỏ, và đó là thứ cần nhìn thấy khi chạy thử.

Chạy thật thì ô ở đường cùng gốc (`/tiles/...`), hai cách:

- Đặt `web/` sau cùng nginx với máy chủ bản đồ.
- Hoặc sửa `cauhinh.js`, điền URL đầy đủ của máy chủ bản đồ. Lúc đó máy chủ
  phải cho CORS từ origin của demo.

## Sửa gì ở đâu

| Việc | Tệp |
|---|---|
| Đổi URL nguồn ô, vị trí mở đầu, ô dùng để kiểm tra | `cauhinh.js` |
| Logic phân loại phản hồi của ô | `kiem-o.js` |
| Giao diện, lớp, công tắc | `index.html` |

`index.html` không ghi cứng URL nào — tất cả đọc từ `cauhinh.js`.

## Tự kiểm tra

```bash
python scripts/chay-demo.py --self-check   # bộ sinh ô giả
```

```
http://localhost:8080/?self-check          # logic của trang, kết quả ở console
```

Phía trang: assert cho `phanLoaiPhanHoi()` trong `kiem-o.js`. Trường hợp quan
trọng nhất được kiểm là **HTTP 200 kèm `text/html` phải bị tính là lỗi**, vì
đó là bẫy nginx để ô rơi vào SPA fallback rồi trả `index.html`.

Phía bộ sinh ô: kiểm mã hoá terrarium giải ngược ra đúng độ cao, và **độ cao
phải liên tục giữa hai pixel kề**. Assert thứ hai bắt một lỗi dễ mắc ở cả
pipeline thật: resize ảnh terrain đã mã hoá làm bilinear nội suy riêng từng
kênh R/G/B, vỡ mã ở biên byte, ra mặt đất bậc thang. Luôn nội suy độ cao
*trước*, mã hoá *sau*.

## Trang này cố tình không làm

- Không đọc dữ liệu theo xã, không đăng nhập, không vẽ hay sửa dữ liệu.
- Không gọi `map.setStyle()`. Đổi nền bằng bật/tắt `visibility` của lớp. Lý do:
  `setStyle` reset toàn bộ source và layer, tức là xoá luôn lớp chủ quyền.
- Không tự thêm lớp chủ quyền, không tự vẽ đảo, không tự đặt tên đảo. Lớp đó
  nằm **sẵn trong style** do `scripts/dung-style.py` đặt vào. Trang chỉ **kiểm**
  style có đủ lớp không, có nằm trên cùng không, có công tắc tắt nào không.
  Thiếu thì hiện cảnh báo đỏ chứ không im lặng vẽ bản đồ thiếu lớp.

  Đây là điểm chính của cả kiến trúc: ứng dụng nào dùng style của máy chủ là có
  chủ quyền sẵn, không cần một dòng mã client. Cổng kiểm tra co từ "so N bản
  sao ở N ứng dụng" về "kiểm style của máy chủ có đủ lớp".
- Không nhúng CDN. Máy chủ nội bộ không có DNS ra ngoài.

## Ba cái bẫy đã dính khi dựng trang này

Ghi lại vì cả ba đều cho ra **bản đồ trắng trơn mà mọi request vẫn xanh**:

1. **Font tải về là trang HTML kèm mã 200.** `fonts.openmaptiles.org` trả trang
   lỗi 2.7 KB cho mọi dải glyph, `curl -f` coi là thành công. MapLibre chỉ kêu
   `Unimplemented type: 4`. `tai-vendor.sh` giờ kiểm từng tệp, thấy `<!doctype`
   là dừng.
2. **MapLibre đòi URL sprite phải tuyệt đối** khi style được đưa vào dạng đối
   tượng. `/vendor/sprite/sprite` bị từ chối và **cả style không nạp**. Ứng dụng
   nào đưa *đường dẫn* style cho MapLibre thì không gặp lỗi này.
3. **⛔ Đừng chuẩn hoá `glyphs` bằng `new URL()`** — nó mã hoá `{}` thành `%7B`,
   MapLibre báo thiếu token `{fontstack}`. Chỉ sprite cần tuyệt đối.

Dòng "Hình vẽ ra trong khung nhìn" trong bảng trạng thái sinh ra từ đợt này:
HTTP 200 chỉ nói tệp có, không nói style và ô có khớp nhau không.

## Trạng thái nguồn ô

Bảng bên trái gọi thử từng nguồn hai lần rồi báo mã trả về, Content-Type và
`X-Tile-Cache`.

Phải tự gọi vì **MapLibre coi ô 404 là ô rỗng và không bắn event `error`** —
proxy trả 404 nghĩa là bản đồ trắng mà không một dòng lỗi trong console, và
chuỗi nguồn dự phòng cũng không nhảy. Lần gọi thứ hai nên thấy
`X-Tile-Cache: HIT`.

## Còn thiếu

| Thiếu | Khi nào có |
|---|---|
| Lớp chủ quyền | Cần `web/chu-quyen/chu-quyen-dao.json` rồi chạy lại `dung-style.py` |
| Ô địa hình ngoài Hoa Lư | `phamvi.json` khai bounds `105.80, 20.15, 106.10, 20.38`, z8–12. Ngoài vùng đó MapLibre không gọi ô (có `bounds` trong source) nên mặt đất phẳng, không phải lỗi |
| Font cho nhãn tên đảo | Tải glyph PBF vào `web/vendor/font/` — xem `scripts/tai-vendor.sh` |
| Ô tìm địa chỉ | Phase 6, khi có Photon |
| Trang giới thiệu | Sau, khi có đơn vị thứ hai dùng máy chủ |

Đoạn ghép lớp chủ quyền trong `index.html` giả định `chu-quyen-dao.json` là
GeoJSON FeatureCollection, nhãn ở thuộc tính `ten` hoặc `name`. Nếu tệp thật
có cấu trúc khác, trang sẽ in ra các khoá ở gốc để biết cần chuyển đổi gì —
không tự đoán schema.
