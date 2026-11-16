// Giao diện tìm nhanh: ô gõ tên, nút nhóm, danh sách kết quả.
//
// Phần LÕI (bỏ dấu, khớp tên, lọc, sắp xếp) nằm ở tim-kiem.js và có assert
// riêng. Tệp này chỉ lo DOM và bản đồ — tách ra để phần lõi kiểm được mà
// không cần dựng cả trang.

(function () {
  'use strict';

  var nhomDangChon = null;
  var danhDau = null;

  function noi(map) {
    var o = document.getElementById('tim-o');
    var hopNhom = document.getElementById('tim-nhom');

    window.TIMKIEM.NHOM.forEach(function (n) {
      var b = document.createElement('button');
      b.textContent = n.ten;
      b.setAttribute('aria-pressed', 'false');
      b.addEventListener('click', function () {
        nhomDangChon = nhomDangChon === n.ma ? null : n.ma;
        hopNhom.querySelectorAll('button').forEach(function (x) {
          x.setAttribute('aria-pressed', String(x === b && nhomDangChon === n.ma));
        });
        chay(map);
      });
      hopNhom.appendChild(b);
    });

    var hen = null;
    o.addEventListener('input', function () {
      clearTimeout(hen);
      hen = setTimeout(function () { chay(map); }, 180);
    });

    // Kéo bản đồ thì kết quả cũ không còn đúng vùng nữa.
    map.on('moveend', function () {
      if (o.value.trim() || nhomDangChon) chay(map);
    });
  }

  function chay(map) {
    var o = document.getElementById('tim-o');
    var hop = document.getElementById('tim-ket-qua');
    var tuKhoa = o.value.trim();
    hop.innerHTML = '';

    if (!tuKhoa && !nhomDangChon) return;

    var ds = window.TIMKIEM.timTrongKhungNhin(map, tuKhoa, nhomDangChon, 20);
    if (!ds.length) {
      var p = document.createElement('p');
      p.id = 'tim-ghi-chu';
      p.textContent = 'Không có điểm nào khớp trong vùng đang xem. ' +
        'Thử phóng to hoặc di chuyển bản đồ — chỉ tìm trong dữ liệu đã tải.';
      hop.appendChild(p);
      return;
    }

    ds.forEach(function (d) {
      var b = document.createElement('button');
      b.appendChild(document.createTextNode(d.ten));
      var s = document.createElement('span');
      s.className = 'lop';
      s.textContent = d.lop || 'địa điểm';
      b.appendChild(s);
      b.addEventListener('click', function () { bayToi(map, d); });
      hop.appendChild(b);
    });
  }

  function bayToi(map, d) {
    if (danhDau) danhDau.remove();
    // Dùng Marker chứ không thêm lớp vào style: thêm lớp là phải tự lo nó
    // nằm dưới lớp chủ quyền, mà việc đó không có lý do gì phải gánh ở đây.
    danhDau = new maplibregl.Marker({ color: '#e5534b' })
      .setLngLat(d.toaDo)
      .setPopup(new maplibregl.Popup({ offset: 24 }).setText(d.ten))
      .addTo(map);
    map.easeTo({ center: d.toaDo, zoom: Math.max(map.getZoom(), 16), duration: 700 });
    danhDau.togglePopup();
  }

  window.TIMNHANH = { noi: noi };
})();
