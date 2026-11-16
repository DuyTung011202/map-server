#!/usr/bin/env bash
# Tải MapLibre GL JS về web/vendor/ — chạy một lần, trên máy CÓ mạng ra ngoài.
#
# Vì sao không dùng CDN: máy chủ nội bộ không có DNS ra ngoài, và cả kiến trúc
# này dựng lên để không phụ thuộc máy chủ của người khác. Nhúng CDN vào trang
# demo là tự phá mất lý do tồn tại của nó.
set -euo pipefail

PHIEN_BAN="${PHIEN_BAN:-5.6.0}"
GOC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DICH="$GOC/web/vendor"

mkdir -p "$DICH"
CDN="https://unpkg.com/maplibre-gl@${PHIEN_BAN}/dist"

echo "Tải MapLibre GL JS ${PHIEN_BAN} về ${DICH}"
curl -fsSL "$CDN/maplibre-gl.js"  -o "$DICH/maplibre-gl.js"
curl -fsSL "$CDN/maplibre-gl.css" -o "$DICH/maplibre-gl.css"

echo "$PHIEN_BAN" > "$DICH/PHIEN-BAN.txt"

# --- PMTiles: đọc ô vector thẳng từ một tệp tĩnh bằng HTTP range request ---
echo "Tải thư viện PMTiles"
curl -fsSL "https://unpkg.com/pmtiles@4.3.0/dist/pmtiles.js" -o "$DICH/pmtiles.js"

# --- Glyph cho nhãn ---
# Lấy ĐỦ 256 dải (0–65535), không chọn lọc nữa.
#
# Trước đây chỉ lấy 6 dải "thật sự cần" cho tiếng Việt. Hỏng thật: ở zoom cao,
# OSM có nhãn chứa ký tự ngoài 6 dải đó (tên tiếng Hàn, tiếng Trung của cơ sở
# nước ngoài), và TileServer GL gặp dải thiếu thì **trả HTTP 500 cho cả ô** —
# không phải chỉ mất chữ. Ô nền biến mất hoàn toàn từ z16.
#
#   ERROR: Font not found: /data/fonts/Noto Sans Italic/49152-49407.pbf
#
# Dải nào không có ký tự thì máy chủ trả tệp rỗng hợp lệ, nên lấy hết là an
# toàn. Dải quan trọng nhất cho tiếng Việt vẫn là 7680–7935 (ạ, ầ, ể, ộ, ỹ...).
# Lấy MỌI dải trước khối CJK: U+0000–U+2FFF, tức 48 dải. Gồm Latin, dấu
# tiếng Việt, Hy Lạp, Kirin, dấu câu, mũi tên, ký hiệu toán, dạng số.
#
# Không lấy từ U+3000 trở lên (Hán, Hàn, Nhật): mỗi dải CJK nặng ~180 KB, lấy
# đủ 256 dải là vendor phình từ 2.8 MB lên ~60 MB. Thay vào đó style ép nhãn
# dùng `name:vi` rồi `name:latin`, KHÔNG dùng `name` thô — xem
# `uu_tien_tieng_viet` trong dung-style.py — nên không ký tự CJK nào tới được
# bộ vẽ.
#
# Vì sao không lấy ít hơn nữa: trước đây chỉ lấy 6 dải, và ở z17 gặp nhãn có
# ký tự ở dải 8448-8703 (dạng số, ký hiệu) -> TileServer GL trả 500 cho CẢ Ô.
# Dải trống thì máy chủ trả tệp nhỏ hợp lệ, nên lấy dư không hại gì.
NGUON_FONT="https://demotiles.maplibre.org/font"
DAI=""
for i in $(seq 0 47); do DAI="$DAI $((i * 256))-$((i * 256 + 255))"; done

# Kiểm từng tệp tải về. Máy chủ hỏng hay trả trang lỗi HTML kèm mã 200 — tải
# xuống thì curl báo thành công, nhưng MapLibre nhận HTML thay vì glyph và chỉ
# kêu "Unimplemented type: 4" ở console. Đã dính một lần, nên kiểm tại đây.
kiem_nhi_phan() {
  local f="$1"
  if [ ! -s "$f" ] || head -c 16 "$f" | grep -qi "<!doctype\|<html"; then
    echo "LỖI: $f là HTML hoặc rỗng, không phải dữ liệu nhị phân." >&2
    rm -f "$f"
    exit 1
  fi
}

for ten in "Noto Sans Regular" "Noto Sans Italic" "Noto Sans Bold"; do
  mkdir -p "$DICH/font/$ten"
  for d in $DAI; do
    f="$DICH/font/$ten/$d.pbf"
    curl -fsSL "$NGUON_FONT/$(printf %s "$ten" | sed 's/ /%20/g')/$d.pbf" -o "$f"
    kiem_nhi_phan "$f"
  done
  echo "  font: $ten ($(ls "$DICH/font/$ten" | wc -l) dải, $(du -sh "$DICH/font/$ten" | cut -f1))"
done

# --- Sprite: biểu tượng của style (sân bay, bệnh viện, mũi tên...) ---
echo "Tải sprite"
mkdir -p "$DICH/sprite"
NGUON_SPRITE="https://openmaptiles.github.io/osm-bright-gl-style/sprite"
for t in ".json" ".png" "@2x.json" "@2x.png"; do
  curl -fsSL "$NGUON_SPRITE$t" -o "$DICH/sprite/sprite$t"
done
kiem_nhi_phan "$DICH/sprite/sprite.png"
kiem_nhi_phan "$DICH/sprite/sprite@2x.png"

du -sh "$DICH"/* 2>/dev/null
echo "Xong. Tất cả nằm trong web/vendor/, không còn gọi ra mạng ngoài."
