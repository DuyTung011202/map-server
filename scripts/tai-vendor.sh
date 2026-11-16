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
# Chỉ lấy các dải thật sự cần, không lôi cả bộ font về:
#   0-255     Latin cơ bản
#   256-511   Latin mở rộng A (ă, đ, ơ, ư)
#   512-767   Latin mở rộng B
#   768-1023  dấu kết hợp
#   7680-7935 Latin mở rộng bổ sung — ĐÂY là dải chứa hầu hết chữ tiếng Việt
#             có dấu (ạ, ầ, ể, ộ, ỹ...). Thiếu dải này là nhãn tiếng Việt vỡ.
#   8192-8447 dấu câu chung
NGUON_FONT="https://demotiles.maplibre.org/font"
DAI="0-255 256-511 512-767 768-1023 7680-7935 8192-8447"

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
