// Dựng bản đồ và nối công tắc lớp phủ.
//
// Mọi cấu hình đọc từ cauhinh.js và phamvi.json — tệp này KHÔNG ghi cứng
// URL hay toạ độ nào.

(function () {
  'use strict';

  var C = window.CAUHINH;
  var N = C.nguon;
  var TT = window.TRANGTHAI;
  var map = null;

  // Danh sách id các lớp thuộc nền phố, để bật/tắt cả cụm khi đổi nền.
  var lopNenPho = [];

  // PMTiles: một tệp tĩnh, trình duyệt đọc từng lát bằng HTTP Range.
  // Không cần tile server cho nền phố.
  maplibregl.addProtocol('pmtiles', new pmtiles.Protocol().tile);

  // ------------------------------------------------- tải trước rồi mới dựng
  // Hai thứ phải có TRƯỚC khi tạo map:
  //   - style nền phố: đặt lúc tạo map, không bao giờ setStyle (setStyle
  //     reset toàn bộ source/layer, tức là xoá luôn lớp chủ quyền).
  //   - phamvi.json: bounds và minzoom/maxzoom là thuộc tính của source,
  //     gắn lúc tạo chứ không gắn được sau. Có bounds thì MapLibre không gọi
  //     ô ngoài vùng, nên không sinh ra một rừng 404 không ai nhìn ra.
  Promise.all([
    TT.taiJSON(N.nenPho.style, 'Style nền phố', function (s) {
      return 'v' + s.version + ' · ' + s.layers.length + ' lớp';
    }),
    TT.taiJSON(N.diaHinh.phamVi, 'Phạm vi ô địa hình', function (pv) {
      return 'z' + pv.minzoom + '–' + pv.maxzoom + ' · ' + (pv.nguon || 'không rõ nguồn');
    }),
  ]).then(function (kq) { dungBanDo(kq[0], kq[1]); });

  function dungBanDo(nen, pv) {
    var dh = { type: 'raster-dem', tiles: [N.diaHinh.mau], tileSize: 256,
               encoding: (pv && pv.ma_hoa) || 'terrarium' };
    var dd = { type: 'raster', tiles: [N.doDoc.mau], tileSize: 256 };
    if (pv && Array.isArray(pv.bounds) && pv.bounds.length === 4) {
      dh.bounds = dd.bounds = pv.bounds;
    }
    if (pv && typeof pv.minzoom === 'number') dh.minzoom = dd.minzoom = pv.minzoom;
    if (pv && typeof pv.maxzoom === 'number') dh.maxzoom = dd.maxzoom = pv.maxzoom;

    // Style nền phố là nền móng; vệ tinh, độ dốc, địa hình chèn thêm vào.
    var style = nen || {
      version: 8, sources: {}, layers: [],
      glyphs: '/vendor/font/{fontstack}/{range}.pbf',
    };
    if (!nen) {
      TT.canhBaoChuQuyen('Không tải được style nền phố. Chạy ' +
        '<code>python scripts/dung-style.py</code> rồi tải lại.');
    }
    lopNenPho = style.layers.map(function (l) { return l.id; });

    // MapLibre đòi URL sprite phải TUYỆT ĐỐI khi style được đưa vào dạng đối
    // tượng; '/vendor/sprite/sprite' bị từ chối và cả style không nạp được —
    // bản đồ trắng trơn, lỗi chỉ nằm ở console.
    //
    // Style trên máy chủ cố tình giữ đường cùng gốc để dùng được ở nhiều
    // origin. Ứng dụng nào đưa ĐƯỜNG DẪN style cho MapLibre (style: '<url>')
    // thì MapLibre tự phân giải, không cần đoạn này. Trang demo phải tự tải
    // style về để chèn thêm lớp địa hình nên mới phải tự đổi.
    // Chỉ sprite. ⛔ Đừng đụng vào `glyphs`: new URL() mã hoá dấu ngoặc nhọn
    // thành %7Bfontstack%7D và MapLibre báo "url must include a {fontstack}
    // token". Đường cùng gốc của glyphs thì MapLibre chấp nhận.
    if (style.sprite) style.sprite = new URL(style.sprite, location.href).href;

    style.sources['ve-tinh'] = {
      type: 'raster', tiles: [N.veTinh.mau], tileSize: 256,
      maxzoom: N.veTinh.zoomToiDa || 17,
    };
    style.sources['do-doc'] = dd;
    style.sources['dia-hinh'] = dh;

    // Vệ tinh nằm DƯỚI cùng: bật nó thì tắt cả cụm lớp nền phố, nên không
    // cần chen vào giữa. Chèn ở vị trí 0, ngay trên background.
    style.layers.unshift({
      id: 've-tinh', type: 'raster', source: 've-tinh',
      layout: { visibility: 'none' },
    });

    // Lớp phủ chèn TRƯỚC lớp chủ quyền, không bao giờ lên trên nó.
    var viTri = style.layers.findIndex(function (l) {
      return l.id.indexOf('chu-quyen') === 0;
    });
    if (viTri < 0) viTri = style.layers.length;
    style.layers.splice(viTri, 0,
      { id: 'do-doc', type: 'raster', source: 'do-doc',
        layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.7 } },
      { id: 'bong-dia-hinh', type: 'hillshade', source: 'dia-hinh',
        layout: { visibility: 'none' },
        paint: {
          'hillshade-exaggeration': 0.6,
          'hillshade-shadow-color': '#473B24',
          'hillshade-highlight-color': '#ffffff',
          'hillshade-accent-color': '#888888',
        } });

    map = new maplibregl.Map({
      container: 'bando',
      style: style,
      center: [C.tam.lon, C.tam.lat],
      zoom: C.tam.zoom,
      maxPitch: 75,
      attributionControl: false,
    });
    // Đưa map ra ngoài closure. Hai lý do, cả hai đều thật:
    //   - gỡ lỗi: không có nó thì không hỏi được MapLibre đang nghĩ khung
    //     nhìn rộng bao nhiêu, mà đó là thứ sai thì bản đồ trống một mảng.
    //   - máy chủ này để TRANG KHÁC nhúng; trang nhúng cần chạm tới map.
    window.BANDO = map;

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.addControl(new maplibregl.ScaleControl(), 'bottom-left');
    map.on('error', function (e) {
      // Để soi cho tiện, nhưng đừng trông vào: ô 404 không bao giờ tới đây.
      console.warn('[MapLibre]', (e && e.error && e.error.message) || e);
    });

    map.on('idle', demHinhVeRa);

    window.TIMNHANH.noi(map);
    noiCongTac(pv);
    TT.moTaPhamVi(pv);
    TT.dungChuGiai(pv);
    TT.datGhiCong(pv);
    TT.kiemChuQuyen(nen, N.nenPho.style);
    TT.kiemCacNguon();
  }

  // HTTP 200 chỉ nói "tệp có". Nó KHÔNG nói style và ô có khớp nhau không:
  // sai tên source-layer, sai zoom, sai phạm vi đều cho ra bản đồ trắng mà
  // mọi request vẫn xanh. Chỉ có đếm hình vẽ ra mới biết.
  function demHinhVeRa() {
    var ds = map.queryRenderedFeatures();
    var theoLop = {};
    ds.forEach(function (f) {
      var k = f.sourceLayer || f.source;
      theoLop[k] = (theoLop[k] || 0) + 1;
    });
    var ten = Object.keys(theoLop).sort(function (a, b) {
      return theoLop[b] - theoLop[a];
    });

    // Nền vệ tinh là ô RASTER: queryRenderedFeatures không đếm được nó, và
    // bật nó thì cả cụm lớp vector tắt. Lúc đó 0 đối tượng là ĐÚNG, không
    // phải style hỏng — báo đỏ ở đây là báo oan, mà trang này chính là chỗ
    // người ta nhìn để tin máy chủ chạy đúng.
    var dangVeTinh = map.getLayer('ve-tinh')
      && map.getLayoutProperty('ve-tinh', 'visibility') === 'visible';
    if (dangVeTinh) {
      return TT.dat('ve', 'Hình vẽ ra trong khung nhìn', {
        muc: 'ok',
        nhan: 'Nền vệ tinh (raster) đang bật — lớp vector tắt, không đếm được',
      });
    }

    TT.dat('ve', 'Hình vẽ ra trong khung nhìn', ds.length ? {
      muc: 'ok',
      nhan: ds.length + ' đối tượng · ' + ten.slice(0, 4).join(', '),
    } : {
      muc: 'loi',
      nhan: 'KHÔNG có gì — ô về được nhưng style không khớp dữ liệu',
    });
  }

  // ------------------------------------------------------ công tắc lớp phủ
  function hien(idLop, bat) {
    if (map && map.getLayer(idLop)) {
      map.setLayoutProperty(idLop, 'visibility', bat ? 'visible' : 'none');
    }
  }

  function noiCongTac(pv) {
    // Đổi nền bằng bật/tắt visibility. KHÔNG dùng map.setStyle(): nó reset
    // toàn bộ source và layer, tức là xoá luôn lớp chủ quyền.
    document.querySelectorAll('input[name=nen]').forEach(function (r) {
      r.addEventListener('change', function () {
        var pho = r.value === 'nenPho';
        // Nền phố là cả một cụm lớp của style, không phải một lớp raster.
        lopNenPho.forEach(function (id) { hien(id, pho); });
        hien('ve-tinh', !pho);
      });
    });

    document.getElementById('bat-dia-hinh').addEventListener('change', function () {
      hien('bong-dia-hinh', this.checked);
      map.setTerrain(this.checked ? { source: 'dia-hinh', exaggeration: 1.3 } : null);
      if (this.checked) {
        if (map.getPitch() < 30) map.easeTo({ pitch: 55, duration: 700 });
        // Ô địa hình chỉ phủ một vùng. Ở ngoài vùng thì bật lên không thấy gì,
        // nên kéo tầm nhìn về đúng vùng có dữ liệu.
        if (pv && Array.isArray(pv.bounds) && !trongPhamVi(pv.bounds)) {
          map.fitBounds([[pv.bounds[0], pv.bounds[1]], [pv.bounds[2], pv.bounds[3]]],
            { padding: 40, duration: 900 });
        }
      }
    });

    document.getElementById('bat-do-doc').addEventListener('change', function () {
      hien('do-doc', this.checked);
      document.getElementById('chu-giai').style.display = this.checked ? 'block' : 'none';
    });

    document.getElementById('do-mo').addEventListener('input', function () {
      var v = this.value / 100;
      if (map.getLayer('do-doc')) map.setPaintProperty('do-doc', 'raster-opacity', v);
      if (map.getLayer('bong-dia-hinh')) {
        map.setPaintProperty('bong-dia-hinh', 'hillshade-exaggeration', v * 0.9);
      }
    });
  }

  function trongPhamVi(b) {
    var c = map.getCenter();
    return c.lng >= b[0] && c.lng <= b[2] && c.lat >= b[1] && c.lat <= b[3];
  }
})();
