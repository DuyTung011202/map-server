# Máy chủ bản đồ dùng chung — Kế hoạch

Cập nhật: 16/11/2026

> **Hướng làm hiện tại (chốt 16/11/2026): dựng trọn vẹn ở kho này, không đụng
> E-Commune.** Mọi phase chỉ phụ thuộc vào thứ nằm trong kho này; chạy được
> bằng `docker compose up -d` trên máy lẻ là coi như xong. Phần cắm vào
> E-Commune — ba cách ở mục 6, bước "Đo trước" nhãn chủ quyền ở mục 4 — **hoãn
> cho tới khi có máy chủ thật**, gom ở mục 8.2. Lý do: những việc đó cần kho
> khác, cần máy chủ có địa chỉ, và cần chủ sản phẩm quyết; chờ chúng thì cả
> phần tự chủ cũng đứng, trong khi phần tự chủ không chờ gì cả.

## Mục tiêu

Một máy chủ bản đồ tự host, nhiều ứng dụng cùng dùng:

```
                Máy chủ bản đồ
                ├─ ô bản đồ: nền phố, vệ tinh, địa hình
                ├─ style JSON (có sẵn lớp chủ quyền)
                ├─ ảnh COG (TiTiler)
                ├─ tìm địa chỉ (Photon) — Phase 4
                └─ web/ : UI demo
                          │
      ┌───────────────────┼───────────────────┐
      ▼                   ▼                   ▼
  E-Commune SPA      Zalo Mini App      Ứng dụng sau này
  (giữ SharedMap)    (Leaflet)          (dùng style là có
                                         chủ quyền sẵn)
```

Nguyên tắc: **không tự viết máy chủ nào.** Toàn bộ là phần mềm mã nguồn mở
đã trưởng thành, ghép bằng `docker-compose`. Phần tự viết chỉ có: style JSON,
một trang UI demo, vài script build dữ liệu.

**Máy chủ phục vụ ô bản đồ, không phục vụ màn hình.** E-Commune vẫn dùng
`SharedMap` của nó (31 tệp, 24 màn, 10 phân hệ). Không nhúng UI demo, không
iframe, không micro-frontend.

---

## 1. Hiện trạng: cái gì đã có

### 1.1 Trong kho này (chạy được, đã kiểm 16/11/2026)

| Thành phần | Trạng thái | Chi tiết |
|---|---|---|
| Ô nền đường phố | **Đã có** | `data/tiles/vietnam.pmtiles` 320 MB, build bằng Planetiler từ `vietnam.osm.pbf` |
| Style máy chủ | **Đã có** | `scripts/dung-style.py` dựng hai bản: `nen-pho.json` (trình duyệt, `pmtiles://`) và `nen-pho-may.json` (TileServer GL). 131 lớp, hết URL ngoài |
| Lớp chủ quyền trong style | **Đã có** | `web/chu-quyen/chu-quyen-dao.json`, 958 đối tượng (922 vùng + 36 nhãn). Nằm cuối style, không công tắc tắt. Đã xác nhận vẽ ra ở **cả bản vector lẫn bản raster** |
| `docker-compose.yml` | **Đã có** | nginx (cổng vào, cache ô) + TileServer GL `v5.7.0` (raster hoá). `http://localhost:8088` |
| Trang UI demo | **Đã có** | `web/`, chạy được trên cả `chay-demo.py` (ô giả) lẫn compose (ô thật) |
| Ô địa hình + độ dốc | **Đã có** | 298 ô terrarium + 219 ô độ dốc, z8–12, phủ cả tỉnh Ninh Bình (`105.5, 19.8, 106.7, 20.8`). Dựng bằng `scripts/dung-o-dia-hinh.py` từ SRTM 1 arcsec (AWS Open Data, bộ skadi). 28 MB |
| Ô ảnh vệ tinh | **Đã có** | 3237 ô, z8–14, 299 MB. Sentinel-2 L2A asset `visual` (RGB 8-bit sẵn), 10 m/pixel, cùng vùng với ô địa hình. Ghép từ 6 cảnh: 5 cảnh ngày 17/01/2025 + 1 cảnh 12/01/2025, mây 0–4.2%. `scripts/dung-o-ve-tinh.py` |
| Ảnh COG tự có, tìm địa chỉ | **Chưa có** | Phase 4 phần COG, Phase 6 |

Đã kiểm chạy thật, không phải suy luận: ô raster 200 `image/png` có hình và có
nhãn; gọi lần hai ra `X-Tile-Cache: HIT`; PMTiles trả `206` kèm `Content-Range`;
đường không tồn tại trả `404` chứ không phải `200` + `text/html`.

### 1.2 Ở kho E-Commune (tham chiếu, ảnh chụp 13/11/2026)

Phần này **không phải việc cần làm bây giờ** — giữ để lúc tích hợp còn biết
đang nối vào cái gì.

| Thành phần | Trạng thái | Chi tiết |
|---|---|---|
| Nền vệ tinh | **Đã có, nhưng ở máy khác** | TileServer GL của tỉnh tại `10.40.41.28`, `ninhbinh_satellite.mbtiles`, phủ Ninh Bình tới z17 — nét hơn Sentinel-2 nhiều. Kho này tự dựng bản Sentinel-2 10 m để không phụ thuộc máy đó (mục 1.1) |
| Địa hình 3D | **Đã có** (06/11/2026) | Ô Terrarium tĩnh + ô độ dốc, build bằng `tools/dung-o-dia-hinh.py`. Nguồn **SRTM 30 m** (NASA/USGS), mốc cao độ EGM96, z8–12, bounds `105.80, 20.15, 106.10, 20.38` — chỉ phủ Hoa Lư. Khai trong `phamvi.json` |
| Ranh giới hành chính | **Đã có** | `boundary_catalog`, gán ranh khi khởi tạo xã, vẽ ranh thôn |
| Lớp dữ liệu theo xã | **Đã có** | `map_layers` / `map_layer_data` trong MySQL `core`, trả GeoJSON qua Gateway |
| Chuyển lớp / độ mờ / chú giải | **Đã có** | `SharedMap` + trang `/gis/tong-hop` |
| Lấy dữ liệu OSM | **Đã có** | Overpass API + lịch chạy đêm `OsmAutoScheduler`, nạp vào lớp `REF_*` |
| Kho PostGIS | **Có nhưng không dùng** | Service `gis` (PG18 + PostGIS 3.6, RLS theo xã, máy `10.40.41.30`). `GIS_BACKEND=core` nên đang đứng ngoài. Đợt chuyển hoãn từ 09/10/2026 |
| Goong | **Có, đúng một chỗ** | Nguồn nền do xã tự dán khoá. Không đặt mặc định, không seed khoá |
| Script kiểm kê QGIS | **Đã có** | `scripts/qgis-inventory.py` |
| **Nền đường phố** | **Vẫn đang mượn** | Proxy qua nginx tới `tile.openstreetmap.de` (máy chủ cộng đồng FOSSGIS). Thay được rồi — ô đã có ở mục 1.1, chỉ còn chờ máy chủ để cắm |
| Tìm địa chỉ / dẫn đường | **Chưa có** | Photon, Valhalla, Nominatim: chưa có gì |
| File QGIS | **Chưa có** | Không có `.qgs`/`.qgz` nào trong kho |

Hiện trạng đầy đủ: `docs/62-GIS-HIEN-TRANG.md`.

**Chỗ yếu nhất:** nền đường phố vẫn mượn máy chủ cộng đồng. Tỉnh đã bị OSM
chặn theo IP một lần ([MAP-004]) — cả cơ quan dùng một IP NAT nên nhà cung cấp
coi là máy cào. Cái thay thế đã dựng xong và kiểm xong ở kho này; việc còn lại
thuần là triển khai, không còn là việc build.

---

## 2. Cái gì cần bổ sung

| Việc | Công cụ | Vì sao cần |
|---|---|---|
| ~~Nền đường phố tự chủ~~ | Planetiler → PMTiles → TileServer GL | **XONG 16/11** — xoá phụ thuộc máy chủ cộng đồng |
| ~~Lớp chủ quyền đặt sẵn trong style~~ | `scripts/dung-style.py` | **XONG 16/11** — mục 4 |
| ~~UI demo~~ | Một trang MapLibre | **XONG** — mục 5 |
| Ô địa hình trong kho này | `dung-o-dia-hinh.py` + `phamvi.json` rộng hơn | Hiện ô nằm trong image Docker của frontend E-Commune, kho này không có. Phase 3 dựng lại ở đây, phủ rộng hơn Hoa Lư |
| Đọc ảnh COG | TiTiler, route `/cog/*` | Ảnh vệ tinh riêng, Sentinel-2 |
| Tìm địa chỉ | Photon (+ Goong cho phần khó) | Nhu cầu rõ: nhập địa chỉ hộ dân |
| Dẫn đường | Valhalla | **Chưa chốt nhu cầu** — mục 7 |
| Script cập nhật dữ liệu | `update-osm.sh` + đổi symlink | Vận hành |

---

## 3. Những thứ cố tình không làm

**Martin (PostGIS → vector tile tự động).** Hai lý do:

1. Hệ thống không có global query scope — mỗi truy vấn phải tự viết
   `where: { tenant_id }`. Martin không biết tenant là gì. Ai đoán được URL là
   xem được lớp của xã khác.
2. Kho `gis` là kho riêng của service `gis`, không service nào khác được nối
   vào. Dựng kho PostGIS thứ hai chỉ để serve dữ liệu vốn đã có đường ra qua
   Gateway là nhân đôi hạ tầng.

Lớp theo xã cần nhanh hơn thì tối ưu trong `core`. Đã làm 30/10/2026: thêm chỉ
mục + bảng đếm `map_layer_counts`, trang đầu từ 413 ms xuống 11 ms.

**Caddy và TLS.** Máy chủ bản đồ nằm sau nginx của E-Commune, trình duyệt
không gọi trực tiếp. Không cần chứng chỉ, không cần reverse proxy thứ hai.

**PostGIS mới.** Đã có kho `gis`. Không dựng thêm.

**Bản đồ thứ hai trong `code/frontend`.** `web/index.html`, `/globe` CesiumJS,
`/qwc` QWC2 thuộc dự án máy chủ bản đồ, không thuộc frontend E-Commune. WMS của
QGIS Server đưa vào `SharedMap` như một nguồn raster thì được.

CesiumJS đang chờ chủ sản phẩm chốt sửa luật
(`docs/plans/2026-11-06-gis-3d-cesium-phuong-an.md` §3.1). `projection: 'globe'`
thì dùng được — đó là phép chiếu của `SharedMap`, không phải bản đồ riêng.

**QGIS Server làm nền bản đồ.** WMS chậm hơn vector tile cả bậc. Chỉ dùng cho
lớp phân tích, thematic.

---

## 4. Lớp chủ quyền: chuyển từ việc của client sang việc của server

Đây là lợi ích lớn nhất của việc tách máy chủ riêng, lớn hơn chuyện ô nền.

**Vấn đề hiện tại.** Ô nền OSM của máy chủ nước ngoài ghi "三沙市 Sansha" trên
Hoàng Sa và vẽ đường ranh yêu sách quanh Trường Sa ([MAP-009]). Nên có luật:
lớp chủ quyền Hoàng Sa, Trường Sa luôn bật trên mọi nền, không có công tắc tắt
(`.agents/rules/20-giao-dien.md:66-78`).

Cách giữ hiện nay là **mỗi client một bản sao, rồi so từng byte**. Cổng
`tools/check-chu-quyen-mini-app.mjs` so hai đường dẫn ghi cứng
(`code/frontend/src/components/map` và `code/zalo-mini-app/src`): `chu-quyen-dao.json`
phải giống từng byte, hai mảng vùng che phải giống, nhãn và toạ độ phải giống,
mọi `L.map(` phải gọi `ganChuQuyen()`.

Hai client = 2 bản sao + 1 cổng kiểm tra. Mục tiêu nhiều ứng dụng nghĩa là N
bản sao, N nhánh cổng, mỗi app mới là một dịp lệch dữ liệu.

**Cách làm mới.** Đặt sẵn lớp chủ quyền **bên trong style JSON do máy chủ phục
vụ**. Ứng dụng nào dùng style của máy chủ là có chủ quyền sẵn, không cần viết
dòng mã nào. Cổng kiểm tra co lại thành: kiểm style của máy chủ có đủ lớp.

Kèm thêm một endpoint tĩnh phát `chu-quyen-dao.json` + vùng che cho client
không dùng được style (Mini App dùng Leaflet). Một nguồn dữ liệu, không bản sao.

**Tên đảo chỉ lấy từ `tools/chu-quyen/ten.json`.** Không lấy từ OSM, kể cả OSM
tự build.

**Đã làm xong phần này (16/11/2026).** `web/chu-quyen/chu-quyen-dao.json` có
trong kho, `dung-style.py` đặt lớp vào cuối cả hai bản style, và đã xác nhận
bằng mắt: bản vector hiện đủ tên Hoàng Sa (Phú Lâm, Linh Côn, Tri Tôn, Bạch
Quy...) và Trường Sa (Song Tử Tây, Thị Tứ, Ba Bình, Nam Yết, Sinh Tồn, An Bang,
Tư Chính...); bản raster do TileServer GL vẽ cũng ra đúng các nhãn đó. Ô nền
Planetiler tự build **không** thấy nhãn "Sansha" hay ranh yêu sách.

### Rủi ro phải đo — nhưng chỉ khi tích hợp, không chặn gì bây giờ

> Hoãn theo hướng làm chốt 16/11/2026: việc này cần kho E-Commune và một xã
> thật để khai `map_basemaps`, nên nó thuộc mục 8.2 chứ không nằm trên đường
> găng nữa.

Khi E-Commune dùng style vector của máy chủ, **lớp chủ quyền sẽ vẽ hai lần**:

- `tronNenVector()` đổi tiền tố mọi lớp của style ngoài thành `nen-*`
  (`mapTileSources.ts:248,278`) → lớp trong style thành `nen-chu-quyen-*`
- Lớp client vẫn giữ tên `chu-quyen-*`, và luật cấm gỡ lớp client

Vùng che trùng khít thì vô hại (cùng dữ liệu). Nhưng **nhãn tên đảo có thể hiện
đôi**. Không suy luận được, phải mở lên xem.

Cách đo, nửa ngày, làm lúc bắt đầu tích hợp:

1. Lấy style hiện tại, đổi tiền tố lớp chủ quyền thành `nen-chu-quyen-*`
2. Khai vào `map_basemaps` cho một xã (mục 6, cách 3)
3. Mở màn bản đồ, xem nhãn có đôi không

Nếu đôi thì cách sửa nằm ở phía E-Commune và **do chủ sản phẩm quyết**. Không
tự tắt lớp nào.

---

## 5. UI demo

Nằm trong dự án máy chủ bản đồ, thư mục `web/`. Không đặt trong
`code/frontend` — ở đó nó là bản đồ thứ hai và vướng cổng kiểm tra.

| | |
|---|---|
| **Làm gì** | Trưng các lớp máy chủ có; chuyển nền phố ⇄ vệ tinh ⇄ địa hình; thử tìm địa chỉ; hiện ghi công nguồn dữ liệu; trang giới thiệu cho đơn vị khác xem |
| **Không làm gì** | Không nghiệp vụ: không đọc dữ liệu theo xã, không cần đăng nhập E-Commune, không vẽ/sửa dữ liệu |

Giá trị kèm theo: nó là **bộ kiểm tra chạy được** của máy chủ. Demo lên đúng
nghĩa là style + ô + lớp chủ quyền đều đúng. Đây là cách duy nhất biết style
ổn trước khi cắm vào 24 màn của E-Commune.

---

## 6. Ba cách cắm vào E-Commune mà không sửa mã — HOÃN

> **Không làm bây giờ.** Cả ba cách đều cần máy chủ bản đồ có địa chỉ thật và
> cần sửa cấu hình ở kho E-Commune. Giữ nguyên mục này làm bản thiết kế sẵn:
> lúc có máy chủ thì đọc lại, không phải nghĩ lại. Xem mục 8.2.
>
> Phần đã sẵn sàng về phía máy chủ: `/tiles/nen/{z}/{x}/{y}.png` (raster, có
> cache, đã kiểm `X-Tile-Cache: HIT`) cho **cách 1**, và `/style/nen-pho.json`
> + `/tiles/vietnam.pmtiles` cho **cách 3**.

`mapTileSources.ts` đã viết sẵn để đổi nguồn nền không cần build lại frontend.
Đọc phần chú thích đầu tệp đó trước khi làm gì.

**Cách 1 — đổi upstream nginx.** Rẻ nhất, không đụng frontend.

```nginx
# deploy/compose/frontend-nginx.conf:274 — đổi đúng một dòng
set $tile_upstream "https://10.40.41.28";   # thay cho tile.openstreetmap.de
proxy_pass $tile_upstream/styles/osm-vn/$1/$2/$3.png;
```

TileServer GL raster hoá style vector thành `/styles/<tên>/{z}/{x}/{y}.png`,
client không biết gì đã đổi. Rollback bằng cách đổi lại một dòng.

**Giữ `proxy_pass` qua biến** (đã có `resolver`). Viết dạng tĩnh thì nginx phân
giải DNS lúc nạp cấu hình — máy chủ không có DNS ra ngoài là nginx không khởi
động được, tức cả trang web chết chỉ vì bản đồ nền.

**Cách 2 — biến môi trường lúc build.**

```
VITE_MAP_STREET_TILES=https://map.noi-bo/styles/osm-vn/{z}/{x}/{y}.png
VITE_MAP_SATELLITE_TILES=...        # nhiều mẫu, cách nhau bằng |
```

`mapTileSources.ts:52,165,184`. Dùng khi một tỉnh có máy chủ ảnh riêng.

**Cách 3 — một dòng trong `map_basemaps`, không deploy gì.** Bảng này
(`core/prisma/schema.prisma:3832`) đã hỗ trợ `format='STYLE'`: style vector
MapLibre tải lúc chạy. Xã khai trên màn "Nguồn bản đồ nền", nguồn đó đứng đầu
chuỗi dự phòng, lỗi thì tự rơi về chuỗi cũ.

Đây là cách thử máy chủ mới trên **một xã** trước khi đổi cho cả tỉnh.

Style cần khoá hoặc host ngoài thì đã có proxy ở Gateway
(`apps/api-gateway/src/modules/gis/basemap-proxy.*`): nó viết lại mọi URL https
trong style về đường cùng gốc, gắn khoá phía máy chủ, chỉ cho host anh em dưới
cùng miền cha (`hostChoPhep`). Thêm host mới thì sửa ở đó. Không đưa khoá xuống
trình duyệt.

---

## 7. Năm lỗi phải tránh

**0. `proxy_pass` có biến thì nginx CẦN `resolver`.** Đã dính thật ngày
16/11/2026: `trien-khai/nginx.conf` viết
`proxy_pass http://$o_raster:8080/styles/nen-pho/$1/$2/$3.png;` và nginx trả
**502** kèm `no resolver defined to resolve o-raster`. Sửa bằng
`resolver 127.0.0.11 valid=30s ipv6=off;` (DNS nội bộ của Docker).

Vẫn nên viết qua biến, chứ đừng chuyển sang dạng tĩnh để né: dạng tĩnh phân
giải DNS lúc **nạp cấu hình**, nên dịch vụ ô chưa lên là cả nginx không khởi
động được. Đây cũng chính là điều mục 6 cách 1 dặn cho nginx của E-Commune —
chỉ là lần này nó cắn ở phía máy chủ bản đồ.

**1. Trình duyệt chỉ được gọi tới chính trang web.** Ứng viên đầu tiên luôn là
`/tiles/...` cùng gốc, máy chủ bản đồ nằm sau nginx. Gọi thẳng là lặp lại
[MAP-004].

**2. MapLibre coi ô 404 là ô rỗng và KHÔNG bắn event `error`.** Chuỗi dự phòng
sẽ không nhảy. Proxy trả 404 nghĩa là bản đồ trắng mà không một dòng lỗi. Kiểm
sau mỗi lần đổi:

```bash
curl -I <origin>/tiles/nen/12/3252/1812.png   # phải 200
curl -I <origin>/tiles/nen/12/3252/1812.png   # lần hai phải có X-Tile-Cache: HIT
```

**3. `/tiles/dia-hinh/` phải giữ `=404` thật.** Hiện là `try_files $uri =404`
với `^~` (`frontend-nginx.conf:466`). Chuyển sang proxy mà để rơi vào SPA
fallback là nhận `index.html` mã 200 — MapLibre giải mã HTML thành ô hỏng, còn
`SharedMap` tưởng có phạm vi. `taiPhamViDiaHinh()` đã kiểm cả `Content-Type`
nhưng đừng dựa vào đó.

**4. Không gọi `setStyle`.** Style vector phải đặt lúc tạo map —
`mapTileSources.ts:83` tải trước style rồi `SharedMap` dựng đồng bộ.
`map.setStyle()` reset toàn bộ source và layer, tức là **mất lớp chủ quyền**.

---

## 8. Các phase

### 8.1 Làm ở kho này — không phụ thuộc ai

| Phase | Việc | Thời gian | Trạng thái |
|---|---|---|---|
| **1a** | `docker-compose` + Planetiler → PMTiles VN → TileServer GL raster hoá | 1–1.5 ngày | **XONG** 16/11/2026 |
| **1b** | Lớp chủ quyền trong style JSON | 0.5–1 ngày | **XONG** 16/11/2026 |
| **1c** | UI demo | 0.5–1 ngày | **XONG** 16/11/2026 |
| **3** | Dựng ô địa hình + độ dốc **trong kho này**, phủ cả tỉnh, phục vụ qua compose | 1 ngày | **XONG** 16/11/2026 |
| **5** | `capnhat-osm.py` + blue/green đổi tên tệp | 1 ngày | **XONG** 16/11/2026 |
| **4** | TiTiler + route `/cog/*` | 0.5 ngày | **Hoãn** — kho chưa có ảnh COG nào, dựng dịch vụ không ai gọi |
| **6** | Photon (tìm địa chỉ), Goong làm lớp phụ | 1–1.5 ngày | Tiếp theo. Ước 1–1.5 ngày có vẻ THIẾU: Photon cần chỉ mục dựng sẵn, bản chính thức chỉ có cả hành tinh |
| **7** | Nền thế giới + tên nước + Việt Nam nổi bật | 0.5 ngày | **XONG** 16/11/2026 |
| **8** | Ô tới z16, badge POI kiểu bản đồ thương mại | 0.5 ngày | **XONG** 16/11/2026 |

**Còn lại: 3.5–4 ngày.** Không mục nào chờ kho khác, chờ máy chủ, hay chờ người
khác quyết.

Thứ tự này đổi so với bản 13/11: Phase 3 lên trước Phase 5 vì nó là thứ **duy
nhất** còn thiếu để trang demo xanh hết — hiện bốn chấm đỏ (`địa hình`,
`độ dốc`, `vệ tinh`, `phạm vi`) đều là ô máy chủ này chưa phục vụ. Phase 2 cũ
(cắm vào E-Commune) ra khỏi bảng, xuống 8.2.

### 8.2 Hoãn tới khi có máy chủ thật

Không ước lượng thời gian, vì chúng chặn bởi thứ ngoài tầm tay.

| Việc | Chặn bởi |
|---|---|
| Đo nhãn chủ quyền có hiện đôi không (mục 4) | Cần kho E-Commune + một xã thật |
| Cắm vào E-Commune theo cách 1 / 3 (mục 6) | Cần máy chủ có địa chỉ; cần chủ sản phẩm duyệt |
| Đưa ô địa hình ra khỏi ảnh Docker của frontend | Cùng lý do; nhưng Phase 3 ở trên đã làm cho kho này tự có ô, nên khi tích hợp chỉ còn là trỏ URL |
| `--public_url` / `allowedHosts` cho TileServer GL | Chưa biết tên miền thật. Chạy nội bộ sau nginx thì chưa gấp |
| Valhalla (dẫn đường) | Chủ sản phẩm xác nhận có nhu cầu |
| QGIS Server + QWC2 | Có file `.qgs` thật |

### Vì sao Phase 1a đứng đầu

Nền đường phố tự chủ xoá phụ thuộc máy chủ cộng đồng — rủi ro đã xảy ra thật
một lần. Giờ ô và style đã có, phần còn lại thuần là triển khai.

### Vì sao Valhalla chờ chốt

18 phân hệ hiện tại **không có màn nào cần dẫn đường hay isochrone**. Dựng
Valhalla rồi không ai gọi là lãng phí. Tìm địa chỉ thì khác — có nhu cầu rõ
(nhập địa chỉ hộ dân), nên Phase 6 làm bình thường.

### Vì sao nhà 3D chưa làm

`fill-extrusion` bị chặn vì **thiếu dữ liệu chiều cao nhà**, không phải thiếu
mã. OSM Việt Nam gần như không có tag `building:height` hay `building:levels`.

---

## 9. Ranh giới dữ liệu

**Luật một dòng: máy chủ bản đồ chỉ chứa dữ liệu dùng chung, không có cột
`tenant_id`.**

| Thuộc máy chủ bản đồ | Ở lại `core` / service `gis` |
|---|---|
| Ô nền đường phố (PMTiles) | `map_layers`, `map_layer_data` |
| Ô nền vệ tinh | `boundary_catalog`, ranh giới xã/thôn |
| Ô địa hình + độ dốc | `map_layer_registry`, `map_approval_requests` |
| Ảnh COG, Sentinel-2 | `map_basemaps` (nguồn nền của từng xã) |
| Photon, Valhalla | `map_entity_links`, `map_entity_types` |
| POI toàn cầu nếu nhập | Lịch sử thay đổi, lô nạp, từ điển dữ liệu |
| Style JSON, font, sprite, dữ liệu chủ quyền | Mọi thứ còn lại có `tenant_id` |

---

## 10. Hạ tầng và dữ liệu

### Kích cỡ máy

| Phạm vi | RAM | Disk | Thời gian build |
|---|---|---|---|
| Việt Nam | 16 GB | 200 GB NVMe | Planetiler ~5 phút, Valhalla ~20 phút |
| Đông Nam Á | 32 GB | 600 GB NVMe | 1–2 giờ |

NVMe là bắt buộc. Valhalla đọc ghi ngẫu nhiên nhiều, chạy trên HDD chậm cả bậc.

Disk hết trước RAM: mỗi lần build lại cần chỗ cho cả file cũ và mới
(blue/green) nên tính disk gấp đôi dung lượng ô.

### Nguồn dữ liệu

| Loại | Nguồn | Dung lượng | Giấy phép |
|---|---|---|---|
| OSM | Geofabrik `vietnam-latest.osm.pbf` | ~300 MB | ODbL |
| DEM 30 m | Ô đang chạy dùng **SRTM 30 m** (NASA/USGS, phạm vi công cộng). Mở rộng vùng thì cân nhắc Copernicus DEM GLO-30 (AWS Open Data) — mới hơn, phủ tốt hơn ở vùng dốc | vài GB | SRTM: phạm vi công cộng · Copernicus: free, phải ghi công |
| Vệ tinh | Sentinel-2 L2A, `s3://sentinel-cogs` | Không cần tải, TiTiler đọc trực tiếp | Free |
| Hành chính VN | OSM boundary hoặc GADM | < 100 MB | ODbL / GADM |
| POI toàn cầu | Overture Places + Foursquare OS Places | GeoParquet, lọc theo VN còn nhỏ | Apache 2.0 / CDLA — dùng thương mại được |
| Nền raster dự phòng | EOX Sentinel-2 cloudless WMTS | cache theo nhu cầu | **CC BY-NC-SA — kiểm tra trước nếu dùng thương mại** |

### Cây thư mục

```
Map/
├─ docker-compose.yml        nginx + TileServer GL
├─ trien-khai/
│  ├─ nginx.conf             cổng vào, cache ô raster
│  └─ tileserver.json        cấu hình TileServer GL
├─ data/
│  ├─ osm/       vietnam.osm.pbf + nguồn phụ của Planetiler
│  ├─ tiles/     vietnam.pmtiles          ĐÃ CÓ
│  ├─ terrain/   terrain.pmtiles          Phase 3
│  └─ cog/       ảnh COG tự có            Phase 4
├─ web/
│  ├─ index.html, cauhinh.js, kiem-o.js, phamvi.json
│  ├─ style-goc.json         style gốc OSM Bright, không sửa tay
│  ├─ style/                 ra từ dung-style.py, không sửa tay
│  ├─ chu-quyen/             chu-quyen-dao.json
│  └─ vendor/                MapLibre, PMTiles, font, sprite
├─ qgis/         *.qgs (khi có)
└─ scripts/      dung-style.py, chay-demo.py, tai-vendor.sh,
                 qgis-inventory.py, update-osm.sh (Phase 5)
```

### Lệnh build chính

```bash
# Tải OSM
wget -P data/osm https://download.geofabrik.de/asia/vietnam-latest.osm.pbf

# Vector tile
docker run -v $PWD/data:/data ghcr.io/onthegomap/planetiler \
  --download --area=vietnam --output=/data/tiles/vietnam.pmtiles

# DEM → terrain-RGB (nếu mở rộng vùng địa hình)
gdalbuildvrt dem.vrt data/dem/*.tif
rio rgbify -b -10000 -i 0.1 dem.vrt data/terrain/terrain.mbtiles
pmtiles convert data/terrain/terrain.mbtiles data/terrain/terrain.pmtiles
```

### Vận hành

- `scripts/capnhat-osm.py` chạy cron hàng tuần: Planetiler `--download` dựng
  lại cả tệp. Chưa dùng replication diff của `osmium` — dựng lại cả nước mất
  vài phút, chưa đáng để thêm một cơ chế nữa.
- Blue/green: dựng ra `vietnam.moi.pmtiles`, **kiểm header** (kiểu ô, số ô,
  bounds, maxzoom, co bao nhiêu so với bản đang chạy), đổi tên, nạp lại
  TileServer GL, **xoá cache nginx**, rồi kiểm lại qua chính máy chủ. Hỏng ở
  bất cứ bước nào thì tự trả về `vietnam.cu.pmtiles`.
- **Đổi tên tệp, không đổi symlink** — khác bản kế hoạch 13/11. Hai lý do:
  symlink Windows không qua được bind mount của Docker Desktop một cách đáng
  tin; và TileServer GL mở tệp lúc khởi động nên đằng nào cũng phải nạp lại
  dịch vụ, symlink không mua thêm được gì.
- File tĩnh build lại được nên không cần backup.
- **Sao lưu kho `gis` phải dùng tài khoản `gis_backup` (BYPASSRLS).** Tài khoản
  khác ra bản dump rỗng mà trông như trọn vẹn.

---

## 11. Rủi ro

1. **Ảnh vệ tinh độ phân giải cao không có bản free.** Dưới 1 m là hàng thương
   mại (Maxar, Airbus, Planet). Sentinel-2 free nhưng 10 m/pixel — nhìn thấy
   khu phố, không thấy mái nhà. Đây là chi phí lớn nhất của dự án, không phải
   chi phí máy chủ.
2. **Làm style là việc design, không phải việc code.** Dễ ngốn thời gian nhất.
   Lấy style OpenMapTiles hoặc Protomaps có sẵn, chỉ sửa màu và font, thêm lớp
   chủ quyền.
3. **Nominatim quy mô planet rất nặng** — ~4 ngày build, 1 TB+, 64 GB RAM. Dùng
   Photon trước, chỉ thêm Nominatim khi xác định thiếu thật.
4. **Goong tự động vô hiệu hoá API key nếu request tăng đột biến.** Một đợt
   traffic thật hoặc một bug vòng lặp có thể làm mất chức năng tìm địa chỉ giữa
   giờ làm, không báo trước. Đây là lý do Photon phải là lớp chính, Goong là lớp
   phụ. Nên có cảnh báo khi tỉ lệ lỗi Goong tăng.
5. **Chưa đọc được ToS của Goong** (chỉ đọc được tài liệu API và bảng giá).
   Goong đang dùng trong production một chỗ. Nếu định lưu POI Goong trả về
   thành lớp riêng trong DB thì phải xác nhận điều khoản trước — các dịch vụ
   map hosted thường cấm lưu lâu dài kết quả geocoding.

---

## 12. Câu hỏi còn mở

**Không câu hỏi nào dưới đây chặn phần 8.1.** Đó là điểm của hướng làm hiện
tại: phần tự chủ chạy tiếp được trong lúc chờ trả lời.

| Câu hỏi | Ai quyết | Chặn gì |
|---|---|---|
| Nhãn chủ quyền có hiện đôi không? | Đo lúc tích hợp, rồi chủ sản phẩm | Mục 8.2, không chặn 8.1 |
| Máy chủ bản đồ sẽ đặt ở đâu, tên miền gì? | Chủ sản phẩm / hạ tầng | Cả mục 8.2 |
| Ô địa hình phủ tới đâu — cả tỉnh hay cả nước? | Người dùng kho này | Dung lượng Phase 3, không chặn việc bắt đầu |
| Có thật cần dẫn đường, hay chỉ cần tìm địa chỉ? | Chủ sản phẩm | Valhalla |
| Ảnh vệ tinh: mua hay chấp nhận Sentinel-2 10 m? | Chủ sản phẩm | Chi phí lớn nhất |
| Có tiếp cận được file QGIS thật không? | Chủ sản phẩm | QGIS Server |
| Có cần POI Overture không, ai dùng, màn nào? | Chủ sản phẩm | Phase 4 phần POI |

---

## 14. Nhúng vào trang web khác — ràng buộc chốt 16/11/2026

**Đây là sản phẩm dùng thật, và mục đích chính là để TRANG KHÁC nhúng vào.**
Không phải bản thử nghiệm. Mức "chạy được" không phải mức cần đạt.

Nhúng vào trang lạ kéo theo một loạt ràng buộc mà bản demo nội bộ không có.
Cái khó là **gần hết chúng đều hỏng âm thầm**: `curl` vẫn 200, ảnh vẫn đúng,
nhưng trình duyệt ở trang nhúng lại từ chối — và không ai nhìn từ phía máy
chủ mà thấy được.

### 14.1 Đã sửa (16/11/2026)

| Lỗi | Vì sao nguy |
|---|---|
| `/tiles/nen/` trả **hai** header `Access-Control-Allow-Origin` (nginx thêm một, TileServer GL thêm một) | Trình duyệt coi header CORS trùng là không hợp lệ và CHẶN. `curl` thấy 200 bình thường |
| Preflight `OPTIONS` trả **405** | `pmtiles.js` đọc ô bằng header `Range`; `Range` không nằm trong danh sách header an toàn sẵn nên trình duyệt hỏi trước bằng `OPTIONS`. Bị 405 là nó bỏ luôn request thật → trang nhúng trắng bản đồ |
| Không có endpoint sức khoẻ | Bên nhúng và bộ giám sát không có cách biết máy chủ sống mà không tải cả tệp ô. Nay có `/suc-khoe` |

### 14.2 Còn phải làm

| Việc | Vì sao |
|---|---|
| **HTTPS** | **Chặn cứng.** Trang nhúng chạy `https://` mà gọi ô qua `http://` thì trình duyệt chặn thẳng (mixed content) — không có cách nào lách. Điều này **phủ định mục 3 "Caddy và TLS: không cần"**: lý lẽ ở đó chỉ đúng khi máy chủ nằm sau nginx của E-Commune và không ai gọi trực tiếp. Nhúng vào trang lạ thì phải có tên miền và chứng chỉ thật |
| Hợp đồng URL ổn định + đánh phiên bản | Đổi đường dẫn là mọi trang đã nhúng gãy cùng lúc, mà ta không biết ai đang nhúng |
| Trang nhúng `/nhung/` nhận tham số URL | Cho bên chỉ cần một `<iframe>`, không muốn viết JS |
| Đoạn mã nhúng cho MapLibre **và Leaflet** | Leaflet không đọc được style vector → phải có đường riêng kèm lớp chủ quyền, chính là ca Zalo Mini App ở mục 4 |
| Ghi công không gỡ được | Giấy phép OpenMapTiles và Copernicus bắt buộc hiện thấy. Bên nhúng không được phép tắt |
| Chống lạm dụng (giới hạn tần suất, hoặc danh sách nguồn cho phép) | Traffic đến từ nguồn lạ. Đây chính là cách tỉnh bị OSM chặn IP ở [MAP-004], chỉ đảo vai |
| TileJSON cho bên nhúng dò | Cách chuẩn để công cụ khác tự nhận zoom, bounds, ghi công |
| Tài liệu công khai | Không có thì mỗi bên nhúng một kiểu, và lúc đổi gì cũng không báo được ai |

### 14.3 Luật

**Mỗi trang nhúng là một nơi có thể hiện bản đồ thiếu lớp chủ quyền.** Mục 4
viết khi mới có hai client; giờ số client là không giới hạn và ta không kiểm
soát được chúng. Vì vậy lớp chủ quyền **phải** đi kèm dữ liệu — nằm trong
style, nằm trong đoạn mã nhúng, nằm trong trang `/nhung/` — chứ không phải
là thứ bên nhúng tự thêm.

---

## 13. Việc dọn tài liệu

- Tệp này chưa được git theo dõi. Kho này cũng chưa được git theo dõi — đáng
  làm trước Phase 3, vì từ đây trở đi có dữ liệu build ra và cần biết cái gì
  là nguồn, cái gì là sản phẩm.
- Chuyển tệp này sang `docs/plans/...` theo quy ước `40-quy-trinh.md` **chỉ khi
  nhập lại vào kho E-Commune**. Đang tách riêng thì để nguyên ở gốc kho.
- Mọi dẫn chứng `file:line` trong tệp này trỏ sang kho E-Commune, là dẫn chứng
  xuyên kho và sẽ lệch dần. Mục 1.2 là ảnh chụp ngày **13/11/2026** và từ giờ
  **không cập nhật nữa** cho tới lúc tích hợp — đừng tin nó là hiện trạng.
- Mục 1.1 thì ngược lại: nó nói về chính kho này, kiểm lại được bằng
  `docker compose up -d` và hai lệnh `--self-check`. Cập nhật nó khi đổi mã.
- Phần khảo sát Goong, so sánh với Google Maps, và hướng dẫn tiếp nhận file
  QGIS đã tách sang `KHAO-SAT.md` — đó là tham chiếu, không phải việc cần làm.
