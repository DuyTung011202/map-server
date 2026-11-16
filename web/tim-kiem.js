// Tìm nhanh điểm trên bản đồ, từ chính dữ liệu POI trong ô vector.
//
// PHẠM VI — đọc trước khi dùng:
//
// Đây KHÔNG phải geocoder. Nó chỉ thấy những gì MapLibre đã tải về, tức là
// POI trong khung nhìn hiện tại ở mức zoom hiện tại. Gõ "Bệnh viện Chợ Rẫy"
// lúc đang xem Hà Nội thì không ra gì, và đó là đúng chứ không phải lỗi.
//
// Tìm địa chỉ bất kỳ ở bất kỳ đâu cần Photon (PLAN.md Phase 6) chạy phía máy
// chủ. Khi có Photon thì tệp này vẫn dùng được: nó lo phần khớp tên và nhóm,
// chỉ cần đổi nguồn dữ liệu đầu vào.
//
// Chạy assert: mở trang với ?self-check, kết quả ở console.

(function () {
  'use strict';

  // Bảng dấu tiếng Việt. Không dùng String.normalize('NFD') vì nó tách cả
  // chữ 'đ' thành 'd' + gạch ngang ở một số trình duyệt rồi lại không ghép
  // đúng — mà 'đ' là chữ hay gõ sai dấu nhất khi tìm kiếm.
  var DAU = {
    a: 'àáạảãâầấậẩẫăằắặẳẵ', e: 'èéẹẻẽêềếệểễ', i: 'ìíịỉĩ',
    o: 'òóọỏõôồốộổỗơờớợởỡ', u: 'ùúụủũưừứựửữ', y: 'ỳýỵỷỹ', d: 'đ'
  };

  var BANG_BO_DAU = (function () {
    var m = {};
    Object.keys(DAU).forEach(function (khong_dau) {
      DAU[khong_dau].split('').forEach(function (co_dau) { m[co_dau] = khong_dau; });
    });
    return m;
  })();

  /** Bỏ dấu và hạ chữ thường, để gõ "ca phe" ra "Cà Phê". */
  function boDau(s) {
    return String(s == null ? '' : s).toLowerCase()
      .replace(/[^\x00-\x7f]/g, function (c) { return BANG_BO_DAU[c] || c; });
  }

  /** Khớp theo TỪ, không phải khớp chuỗi con. */
  function khopTen(ten, tuKhoa) {
    var t = boDau(ten);
    var tu = boDau(tuKhoa).split(/\s+/).filter(Boolean);
    if (!tu.length) return false;
    // Mọi từ trong truy vấn đều phải xuất hiện. "pho co" khớp "Phố Cổ"
    // nhưng không khớp "Phở Thìn", vì "co" không có trong "pho thin".
    return tu.every(function (x) { return t.indexOf(x) !== -1; });
  }

  // Nhóm nhanh, đặt theo thói quen tra cứu chứ không theo schema. Giá trị là
  // `class` của OpenMapTiles — phải khớp với MAU_POI trong dung-style.py, nếu
  // không thì nút lọc ra một nhóm mà badge lại tô màu nhóm khác.
  var NHOM = [
    { ma: 'an-uong', ten: 'Ăn uống', lop: ['restaurant', 'fast_food', 'cafe', 'bar', 'ice_cream', 'bakery'] },
    { ma: 'y-te', ten: 'Y tế', lop: ['pharmacy', 'hospital', 'doctors', 'clinic', 'dentist'] },
    { ma: 'mua-sam', ten: 'Mua sắm', lop: ['shop', 'grocery', 'supermarket', 'convenience', 'clothing_store', 'department_store'] },
    { ma: 'ngan-hang', ten: 'Ngân hàng', lop: ['bank', 'atm'] },
    { ma: 'xang-dau', ten: 'Xăng dầu', lop: ['fuel'] },
    { ma: 'giao-duc', ten: 'Trường học', lop: ['school', 'college', 'kindergarten', 'library'] },
    { ma: 'giao-thong', ten: 'Giao thông', lop: ['bus', 'railway', 'aerodrome', 'ferry_terminal'] },
    { ma: 'luu-tru', ten: 'Lưu trú', lop: ['lodging', 'hotel'] }
  ];

  function timNhom(ma) {
    for (var i = 0; i < NHOM.length; i++) if (NHOM[i].ma === ma) return NHOM[i];
    return null;
  }

  /** Lấy tên hiển thị, ưu tiên tiếng Việt — cùng thứ tự với style. */
  function tenCuaDiem(p) {
    return p['name:vi'] || p['name:latin'] || p.name || '';
  }

  /**
   * Lọc danh sách đối tượng thô thành kết quả đã sắp xếp, bỏ trùng.
   *
   * Tách khỏi MapLibre để assert được mà không cần bản đồ thật.
   */
  function locKetQua(dsThô, tuKhoa, maNhom, gioiHan) {
    var nhom = maNhom ? timNhom(maNhom) : null;
    var thay = {};
    var ra = [];

    for (var i = 0; i < dsThô.length; i++) {
      var f = dsThô[i];
      var p = f.properties || {};
      var ten = tenCuaDiem(p);
      if (!ten) continue;
      if (nhom && nhom.lop.indexOf(p.class) === -1) continue;
      if (tuKhoa && !khopTen(ten, tuKhoa)) continue;

      // Một POI có thể nằm ở nhiều ô nên lặp lại. Khoá theo tên + toạ độ
      // làm tròn, vì cùng một điểm ở hai ô có toạ độ lệch vài chữ số cuối.
      var toa = (f.geometry && f.geometry.coordinates) || [0, 0];
      var khoa = ten + '|' + toa[0].toFixed(4) + '|' + toa[1].toFixed(4);
      if (thay[khoa]) continue;
      thay[khoa] = true;

      ra.push({ ten: ten, lop: p.class || '', hang: Number(p.rank) || 999, toaDo: toa });
    }

    // Hạng nhỏ là quan trọng hơn trong schema OpenMapTiles.
    ra.sort(function (a, b) {
      return a.hang - b.hang || a.ten.localeCompare(b.ten, 'vi');
    });
    return ra.slice(0, gioiHan || 20);
  }

  /** Hỏi MapLibre lấy POI đang nạp, rồi lọc. */
  function timTrongKhungNhin(map, tuKhoa, maNhom, gioiHan) {
    if (!map) return [];
    var tho = [];
    ['poi', 'place'].forEach(function (lop) {
      try {
        tho = tho.concat(map.querySourceFeatures('openmaptiles', { sourceLayer: lop }));
      } catch (e) { /* nguồn chưa sẵn sàng */ }
    });
    return locKetQua(tho, tuKhoa, maNhom, gioiHan);
  }

  window.TIMKIEM = {
    boDau: boDau,
    khopTen: khopTen,
    locKetQua: locKetQua,
    timTrongKhungNhin: timTrongKhungNhin,
    NHOM: NHOM
  };

  // --- tự kiểm tra ---
  if (location.search.indexOf('self-check') !== -1) {
    var loi = 0;
    function kd(dk, ten) {
      if (!dk) { loi++; console.error('SAI: ' + ten); } else { console.log('đúng: ' + ten); }
    }

    kd(boDau('Cà Phê Trung Nguyên') === 'ca phe trung nguyen', 'bỏ dấu tiếng Việt');
    kd(boDau('Đường Đê La Thành') === 'duong de la thanh', 'bỏ dấu chữ đ hoa và thường');
    kd(boDau('Ngõ Huyện') === 'ngo huyen', 'bỏ dấu nguyên âm có mũ');

    kd(khopTen('Cà Phê Giảng', 'ca phe'), 'gõ không dấu vẫn tìm ra tên có dấu');
    kd(khopTen('Phố Cổ', 'pho co'), 'khớp nhiều từ');
    kd(!khopTen('Phở Thìn', 'pho co'), 'không khớp khi thiếu một từ');
    kd(khopTen('Bệnh viện Việt Đức', 'viet duc'), 'khớp từ ở giữa tên');
    kd(!khopTen('Bất cứ gì', ''), 'truy vấn rỗng thì không khớp gì');

    var gia = [
      { properties: { 'name:vi': 'Phở Bát Đàn', class: 'restaurant', rank: 5 },
        geometry: { coordinates: [105.85, 21.03] } },
      { properties: { 'name:vi': 'Phở Bát Đàn', class: 'restaurant', rank: 5 },
        geometry: { coordinates: [105.850001, 21.030001] } },
      { properties: { 'name:vi': 'Vietcombank', class: 'bank', rank: 2 },
        geometry: { coordinates: [105.86, 21.02] } },
      { properties: { class: 'cafe', rank: 1 }, geometry: { coordinates: [105.87, 21.01] } }
    ];

    kd(locKetQua(gia, '', null, 20).length === 2,
      'bỏ trùng theo tên + toạ độ, và bỏ điểm không có tên');
    kd(locKetQua(gia, '', null, 20)[0].ten === 'Vietcombank',
      'sắp theo hạng, hạng nhỏ lên trước');
    kd(locKetQua(gia, 'pho', null, 20).length === 1, 'lọc theo từ khoá');
    kd(locKetQua(gia, '', 'ngan-hang', 20).length === 1, 'lọc theo nhóm');
    kd(locKetQua(gia, '', 'an-uong', 20).length === 1, 'nhóm ăn uống lấy đúng nhà hàng');
    kd(locKetQua(gia, '', null, 1).length === 1, 'tôn trọng giới hạn số kết quả');

    console.log(loi === 0 ? 'Tìm kiếm — tự kiểm tra: tất cả đúng'
                          : 'Tìm kiếm — tự kiểm tra: ' + loi + ' lỗi');
  }
})();
