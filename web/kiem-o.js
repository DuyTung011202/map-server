// Kiểm một nguồn ô bản đồ còn sống không.
//
// Vì sao phải tự kiểm: MapLibre coi ô 404 là "ô rỗng" và KHÔNG bắn event
// 'error'. Proxy trả 404 nghĩa là bản đồ trắng mà không một dòng lỗi trong
// console, và chuỗi nguồn dự phòng cũng không nhảy. Cách duy nhất biết là tự
// gọi rồi tự xem mã trả về.
//
// Bẫy thứ hai: nginx để ô rơi vào SPA fallback thì trả index.html với mã 200.
// MapLibre nhận 200 nên tưởng có ô, giải mã HTML thành ảnh hỏng. Nên phải xem
// cả Content-Type, không chỉ xem mã.
//
// Chạy assert: mở trang với ?self-check

(function () {
  'use strict';

  /** Phân loại phản hồi của một ô. Trả về { muc, nhan } — muc: ok | canh-bao | loi */
  function phanLoaiPhanHoi(status, contentType) {
    var ct = (contentType || '').toLowerCase();

    if (status === 0) return { muc: 'loi', nhan: 'Không gọi được (mạng hoặc CORS)' };
    if (status === 404) return { muc: 'loi', nhan: '404 — MapLibre sẽ im lặng vẽ ô trắng' };

    // 206 là phản hồi ĐÚNG cho một tệp PMTiles: trình duyệt xin một lát bằng
    // header Range. Máy chủ nào trả 200 kèm cả tệp là máy chủ không hiểu
    // Range, và thư viện PMTiles sẽ đọc nhầm vị trí.
    if (status === 200 || status === 206) {
      if (ct.indexOf('text/html') === 0) {
        return { muc: 'loi', nhan: status + ' nhưng là HTML — rơi vào SPA fallback' };
      }
      if (ct.indexOf('image/') === 0 ||
          ct.indexOf('application/x-protobuf') === 0 ||
          ct.indexOf('application/octet-stream') === 0) {
        return { muc: 'ok', nhan: status + ' ' + ct };
      }
      if (!ct) return { muc: 'canh-bao', nhan: status + ' nhưng không có Content-Type' };
      return { muc: 'canh-bao', nhan: status + ' với kiểu lạ: ' + ct };
    }

    if (status >= 500) return { muc: 'loi', nhan: status + ' — lỗi máy chủ' };
    return { muc: 'canh-bao', nhan: 'Mã ' + status };
  }

  /** Gọi thử một ô. Trả Promise<{ muc, nhan, cache, url }> */
  function kiemMotNguon(mau, o) {
    var url = mau
      .replace('{z}', o.z)
      .replace('{x}', o.x)
      .replace('{y}', o.y);

    // Tệp PMTiles có thể vài trăm MB — chỉ xin lát đầu, đúng cách mà thư
    // viện PMTiles vẫn đọc. Xin cả tệp để "kiểm tra" là tự bắn vào chân.
    var dau = {};
    if (url.indexOf('.pmtiles') !== -1) dau.Range = 'bytes=0-16383';

    return fetch(url, { method: 'GET', cache: 'no-store', headers: dau })
      .then(function (r) {
        var kq = phanLoaiPhanHoi(r.status, r.headers.get('content-type'));
        kq.cache = r.headers.get('x-tile-cache') || null;
        kq.url = url;
        return kq;
      })
      .catch(function () {
        var kq = phanLoaiPhanHoi(0, null);
        kq.cache = null;
        kq.url = url;
        return kq;
      });
  }

  window.phanLoaiPhanHoi = phanLoaiPhanHoi;
  window.kiemMotNguon = kiemMotNguon;

  // --- tự kiểm tra ---
  if (location.search.indexOf('self-check') !== -1) {
    var loi = 0;
    function khangDinh(dieuKien, ten) {
      if (!dieuKien) { loi++; console.error('SAI: ' + ten); }
      else { console.log('đúng: ' + ten); }
    }

    khangDinh(phanLoaiPhanHoi(200, 'image/png').muc === 'ok', 'ảnh png là ok');
    khangDinh(phanLoaiPhanHoi(200, 'image/webp').muc === 'ok', 'ảnh webp là ok');
    khangDinh(phanLoaiPhanHoi(200, 'application/x-protobuf').muc === 'ok', 'vector tile là ok');
    khangDinh(phanLoaiPhanHoi(404, null).muc === 'loi', '404 là lỗi');
    khangDinh(phanLoaiPhanHoi(0, null).muc === 'loi', 'không gọi được là lỗi');
    khangDinh(phanLoaiPhanHoi(500, null).muc === 'loi', '500 là lỗi');
    khangDinh(phanLoaiPhanHoi(200, 'text/html; charset=utf-8').muc === 'loi',
      '200 + HTML là lỗi, không phải ok — đây là bẫy SPA fallback');
    khangDinh(phanLoaiPhanHoi(200, null).muc === 'canh-bao', '200 không Content-Type là cảnh báo');
    khangDinh(phanLoaiPhanHoi(304, 'image/png').muc === 'canh-bao', '304 là cảnh báo');
    khangDinh(phanLoaiPhanHoi(206, 'application/octet-stream').muc === 'ok',
      '206 octet-stream là ok — PMTiles đọc bằng Range');
    khangDinh(phanLoaiPhanHoi(206, 'text/html').muc === 'loi',
      '206 kèm HTML vẫn là lỗi');

    console.log(loi === 0 ? 'Tự kiểm tra: tất cả đúng' : 'Tự kiểm tra: ' + loi + ' lỗi');
  }
})();
