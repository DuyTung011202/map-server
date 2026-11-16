// Cấu hình UI demo. Đổi nguồn ô bản đồ thì sửa đúng tệp này, không sửa index.html.
//
// Mặc định là đường cùng gốc (/tiles/...) vì đó là cách E-Commune đang dùng:
// trình duyệt chỉ gọi tới chính trang web, máy chủ bản đồ nằm sau nginx.
// Chạy demo độc lập thì điền URL đầy đủ của máy chủ bản đồ.

window.CAUHINH = {
  // Vị trí mở đầu: Hoa Lư, Ninh Bình — vùng duy nhất hiện có ô địa hình.
  tam: { lon: 105.93, lat: 20.25, zoom: 11 },

  // Ô dùng để kiểm nguồn sống hay chết (xem kiem-o.js). Nằm trong Ninh Bình.
  oKiemTra: { z: 12, x: 3253, y: 1812 },

  nguon: {
    nenPho: {
      ten: 'Nền đường phố',
      // Style vector do máy chủ phát. Lớp chủ quyền nằm SẴN trong style này
      // (xem scripts/dung-style.py), nên ứng dụng nào dùng nó là có sẵn.
      style: '/style/nen-pho.json',
      // Một tệp PMTiles duy nhất, trình duyệt đọc từng lát bằng HTTP Range.
      mau: '/tiles/vietnam.pmtiles',
      // Giấy phép của schema OpenMapTiles BẮT BUỘC ghi công thấy được.
      // Đừng rút gọn dòng này.
      ghiCong: '© OpenMapTiles © OpenStreetMap contributors',
    },
    veTinh: {
      ten: 'Ảnh vệ tinh',
      mau: '/tiles/ve-tinh/{z}/{x}/{y}.png',
      // Giấy phép Copernicus bắt buộc ghi công thấy được. Đừng rút gọn.
      ghiCong: 'Chứa dữ liệu Copernicus Sentinel-2 đã xử lý (2025) — ESA',
      zoomToiDa: 14,
      ghiChu: 'Sentinel-2 L2A, 10 m/pixel, phủ cả tỉnh Ninh Bình tới z14. ' +
              'Ảnh của tỉnh (10.40.41.28) nét hơn nhưng chưa nối vào máy chủ này.',
    },
    diaHinh: {
      ten: 'Địa hình 3D',
      mau: '/tiles/dia-hinh/{z}/{x}/{y}.png',
      // Phạm vi, zoom, mã hoá và ghi công đều đọc từ phamvi.json lúc chạy,
      // không ghi cứng ở đây. Mở rộng vùng ô thì không phải sửa frontend.
      phamVi: '/tiles/dia-hinh/phamvi.json',
      ghiChu: 'Chỉ phủ vùng Hoa Lư. Ra ngoài phạm vi là ô phẳng.',
    },
    doDoc: {
      ten: 'Độ dốc',
      mau: '/tiles/do-doc/{z}/{x}/{y}.png',
    },
  },

  // Lớp chủ quyền Hoàng Sa, Trường Sa KHÔNG khai ở đây.
  // Nó nằm sẵn trong style nền phố, do scripts/dung-style.py đặt vào từ
  // web/chu-quyen/chu-quyen-dao.json. Ứng dụng nào dùng style của máy chủ là
  // có sẵn, không cần một dòng mã client — đó là cả lý do tách máy chủ riêng.
  // Trang demo chỉ KIỂM style có đủ lớp không, không tự thêm.
};
