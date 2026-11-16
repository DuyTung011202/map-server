// Bảng "trạng thái nguồn ô" và các cảnh báo của trang.
//
// Đây là phần quan trọng nhất của trang demo, dù nhìn chỉ là mấy dòng chữ:
// PLAN.md mục 5 gọi trang này là "bộ kiểm tra chạy được" của máy chủ. Mọi
// kết luận "máy chủ chạy đúng" đều đọc từ bảng này, nên một cảnh báo oan ở
// đây tai hại ngang một lỗi thật bị giấu.

(function () {
  'use strict';

  var bang = document.getElementById('trang-thai');
  var dongDaCo = {};

  /** Đặt hoặc cập nhật một dòng trạng thái. `kq` = { muc, nhan, cache }. */
  function dat(khoa, ten, kq) {
    var el = dongDaCo[khoa];
    if (!el) {
      el = document.createElement('div');
      bang.appendChild(el);
      dongDaCo[khoa] = el;
    }
    el.className = 'muc ' + kq.muc;
    el.innerHTML =
      '<span class="den"></span><span class="noi-dung">' +
      '<span class="ten"></span><span class="nhan"></span></span>';
    el.querySelector('.ten').textContent = ten;
    el.querySelector('.nhan').textContent =
      kq.nhan + (kq.cache ? ' · cache: ' + kq.cache : '');
  }

  /** Tải một tệp JSON, báo trạng thái, trả null nếu hỏng thay vì ném. */
  function taiJSON(url, ten, moTa) {
    return fetch(url, { cache: 'no-store' })
      .then(function (r) {
        var ct = (r.headers.get('content-type') || '').toLowerCase();
        if (!r.ok) throw new Error('mã ' + r.status);
        // Nginx để rơi vào SPA fallback thì trả index.html mã 200: chặn ở đây.
        if (ct.indexOf('json') === -1) throw new Error('không phải JSON: ' + ct);
        return r.json();
      })
      .then(function (du) {
        dat(url, ten, { muc: 'ok', nhan: moTa(du) });
        return du;
      })
      .catch(function (e) {
        dat(url, ten, { muc: 'loi', nhan: e.message });
        return null;
      });
  }

  // ----------------------------------------------------------- chủ quyền
  // Luật của dự án: lớp chủ quyền Hoàng Sa, Trường Sa luôn bật trên mọi nền,
  // không có công tắc tắt. Trang này KHÔNG tự vẽ đảo và KHÔNG tự đặt tên —
  // dữ liệu chỉ đến từ endpoint của máy chủ. Thiếu thì phải kêu to, vì một
  // bản đồ nền OSM không có lớp này là bản đồ sai.
  function canhBaoChuQuyen(chiTiet) {
    var el = document.getElementById('canh-bao-chu-quyen');
    el.style.display = 'block';
    el.innerHTML = '<strong>Chưa có lớp chủ quyền.</strong> ' + chiTiet;
  }

  // Trang KHÔNG tự thêm lớp chủ quyền. Lớp đó phải nằm sẵn trong style do
  // máy chủ phát (scripts/dung-style.py), vì đó mới là thứ mọi ứng dụng khác
  // dùng chung. Trang chỉ KIỂM xem style có đủ lớp không — đây chính là cổng
  // kiểm tra thay cho việc so từng byte giữa N bản sao ở N ứng dụng.
  function kiemChuQuyen(nen, duongStyle) {
    if (!nen) return;  // style hỏng: đã cảnh báo ở chỗ khác

    var lop = nen.layers.filter(function (l) {
      return l.id.indexOf('chu-quyen') === 0;
    });

    if (!lop.length) {
      canhBaoChuQuyen('Style <code>' + duongStyle + '</code> không có lớp nào ' +
        'tên <code>chu-quyen-*</code>. Ô nền OSM ghi sai tên và vẽ sai ranh ở ' +
        'Hoàng Sa, Trường Sa — xem PLAN.md mục 4.');
      return dat('chu-quyen', 'Lớp chủ quyền trong style',
        { muc: 'loi', nhan: 'Không có — style chưa dùng được cho ứng dụng thật' });
    }

    // Có công tắc tắt là sai luật, kể cả khi đang bật.
    var tatDuoc = lop.filter(function (l) {
      return l.layout && 'visibility' in l.layout;
    });
    if (tatDuoc.length) {
      return dat('chu-quyen', 'Lớp chủ quyền trong style', {
        muc: 'loi',
        nhan: 'Có công tắc tắt ở: ' + tatDuoc.map(function (l) { return l.id; }).join(', '),
      });
    }

    // Phải nằm ở cuối, nếu không lớp nền vẽ đè lên.
    var cuoi = nen.layers.length - 1;
    var thapNhat = nen.layers.indexOf(lop[0]);
    var duoiCung = thapNhat + lop.length - 1 === cuoi;

    dat('chu-quyen', 'Lớp chủ quyền trong style', {
      muc: duoiCung ? 'ok' : 'canh-bao',
      nhan: lop.length + ' lớp' + (duoiCung ? ' ở trên cùng' : ' NHƯNG bị lớp khác đè'),
    });
  }

  // --------------------------------------------------------- kiểm nguồn ô
  function kiemCacNguon() {
    var C = window.CAUHINH;
    // Gọi thử hai lần: lần hai để xem cache của nginx có ăn không.
    ['nenPho', 'veTinh', 'diaHinh', 'doDoc'].forEach(function (khoa) {
      var n = C.nguon[khoa];
      window.kiemMotNguon(n.mau, C.oKiemTra).then(function (kq) {
        dat(khoa, n.ten, kq);
        if (kq.muc !== 'ok') return null;
        return window.kiemMotNguon(n.mau, C.oKiemTra).then(function (lan2) {
          dat(khoa, n.ten, lan2);
        });
      });
    });
  }

  // ------------------------------------------- mô tả, chú giải, ghi công
  function moTaPhamVi(pv) {
    var el = document.getElementById('ghi-chu-dia-hinh');
    if (!pv) {
      el.textContent = 'Không đọc được phamvi.json — không rõ vùng nào có dữ liệu.';
      return;
    }
    var b = pv.bounds || [];
    el.textContent =
      (b.length === 4 ? b.map(function (v) { return (+v).toFixed(2); }).join(', ') + ' · ' : '') +
      'z' + pv.minzoom + '–' + pv.maxzoom +
      (pv.ngay_dung ? ' · dựng ' + pv.ngay_dung : '') +
      (pv.moc_do_cao ? ' · mốc ' + pv.moc_do_cao : '');
  }

  function dungChuGiai(pv) {
    var el = document.getElementById('chu-giai');
    var bac = pv && pv.do_doc && pv.do_doc.lop;
    if (!Array.isArray(bac)) return;
    bac.forEach(function (b) {
      var d = document.createElement('div');
      d.className = 'bac';
      var o = document.createElement('span');
      o.className = 'o-mau';
      o.style.background = b.mau;
      var t = document.createElement('span');
      t.textContent = b.nhan;
      d.appendChild(o);
      d.appendChild(t);
      el.appendChild(d);
    });
  }

  function datGhiCong(pv) {
    var N = window.CAUHINH.nguon;
    var phan = [N.nenPho.ghiCong, N.veTinh.ghiCong];
    // Ghi công địa hình lấy từ phamvi.json, không ghi cứng trong trang —
    // đổi nguồn DEM thì không ai phải nhớ sửa chỗ này.
    if (pv && pv.nguon) phan.push('Địa hình: ' + pv.nguon);
    document.getElementById('ghi-cong').textContent = phan.filter(Boolean).join(' · ');
  }

  window.TRANGTHAI = {
    dat: dat,
    taiJSON: taiJSON,
    canhBaoChuQuyen: canhBaoChuQuyen,
    kiemChuQuyen: kiemChuQuyen,
    kiemCacNguon: kiemCacNguon,
    moTaPhamVi: moTaPhamVi,
    dungChuGiai: dungChuGiai,
    datGhiCong: datGhiCong,
  };
})();
