#!/usr/bin/env python3
"""Dựng lại ô nền từ OSM mới và đổi sang bản mới mà không mất phục vụ.

    python scripts/capnhat-osm.py               # dựng + kiểm + đổi
    python scripts/capnhat-osm.py --chi-kiem    # chỉ kiểm tệp đang chạy
    python scripts/capnhat-osm.py --chi-dung    # dựng ra bản .moi, KHÔNG đổi
    python scripts/capnhat-osm.py --chi-doi     # đổi bản .moi có sẵn, không dựng lại
    python scripts/capnhat-osm.py --quay-lai    # trả về bản .cu
    python scripts/capnhat-osm.py --self-check  # assert, không đụng tệp nào

Chạy định kỳ (hàng tuần là đủ: OSM Việt Nam không đổi nhanh đến mức cần hơn).

VÌ SAO ĐỔI TÊN TỆP CHỨ KHÔNG ĐỔI SYMLINK, khác với PLAN.md mục 10:

  1. Kho này đang nằm trên Windows, và symlink Windows không đi qua bind mount
     của Docker Desktop một cách đáng tin. Đổi tên thì hệ nào cũng như nhau.
  2. TileServer GL MỞ tệp lúc khởi động và giữ nguyên. Đổi symlink dưới chân
     nó cũng không làm nó đọc bản mới — vẫn phải nạp lại dịch vụ. Mà đã phải
     nạp lại thì symlink không mua thêm được gì.

Nên "blue/green" ở đây là: dựng ra `.moi`, KIỂM, đổi tên, nạp lại, kiểm lần
nữa qua chính máy chủ; hỏng ở bất cứ bước nào thì tự trả về bản `.cu`.

BẪY ĐÃ TÍNH: nginx cache ô raster 7 ngày. Đổi dữ liệu mà không xoá cache thì
cả tuần sau người dùng vẫn xem bản đồ cũ, trong khi mọi thứ đều báo thành
công. Xoá cache là một bước BẮT BUỘC của việc đổi, không phải việc dọn dẹp.
"""

import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
TILES = GOC / "data" / "tiles"
DANG_CHAY = TILES / "vietnam.pmtiles"
BAN_MOI = TILES / "vietnam.moi.pmtiles"
BAN_CU = TILES / "vietnam.cu.pmtiles"
PLANETILER = GOC / "data" / "planetiler.jar"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAY_CHU = "http://127.0.0.1:8088"
O_KIEM = (12, 3253, 1812)   # Hoa Lư — cùng ô mà cauhinh.js dùng để thử nguồn
RAM = "6g"

# Ngưỡng co lại chấp nhận được. OSM có thể mất dữ liệu thật (ai đó xoá nhầm
# một vùng), nên tệp mới nhỏ hơn hẳn là dấu hiệu phải dừng, không phải chuyện
# bình thường.
TI_LE_TOI_THIEU = 0.80


# ------------------------------------------------------------ đọc PMTiles
def doc_header(duong: Path) -> dict:
    """Đọc 127 byte đầu của PMTiles v3.

    Bố cục lấy từ đặc tả v3 và đã đối chiếu với tệp thật đang chạy.
    """
    with duong.open("rb") as f:
        d = f.read(127)
    if len(d) < 127 or d[:7] != b"PMTiles":
        raise ValueError(f"{duong.name}: không phải tệp PMTiles")
    if d[7] != 3:
        raise ValueError(f"{duong.name}: PMTiles phiên bản {d[7]}, cần 3")
    b = struct.unpack_from("<iiii", d, 102)
    return {
        "so_o": struct.unpack_from("<Q", d, 72)[0],
        "so_muc": struct.unpack_from("<Q", d, 80)[0],
        "kieu_o": d[99],
        "minzoom": d[100],
        "maxzoom": d[101],
        "bounds": [v / 1e7 for v in b],
        "kich_thuoc": duong.stat().st_size,
    }


def mo_ta(h: dict) -> str:
    return (f"{h['kich_thuoc'] / 1e6:.0f} MB · {h['so_o']:,} ô · "
            f"z{h['minzoom']}–{h['maxzoom']} · "
            f"bounds {', '.join(f'{v:.2f}' for v in h['bounds'])}")


def kiem_header(h: dict, cu: dict | None) -> list[str]:
    """Trả danh sách lý do KHÔNG được đem ra phục vụ. Rỗng là đạt."""
    loi = []
    if h["kieu_o"] != 1:
        loi.append(f"kiểu ô {h['kieu_o']}, cần 1 (MVT vector)")
    if h["so_o"] < 1000:
        loi.append(f"chỉ có {h['so_o']} ô — gần như rỗng")

    lon1, lat1, lon2, lat2 = h["bounds"]
    # Phải trùm được đất liền Việt Nam. KHÔNG đòi tới 117°Đ: ô nền OSM không
    # vươn hết Trường Sa, mà cũng không cần — lớp chủ quyền nằm trong style
    # dưới dạng geojson, không phụ thuộc ô nền. Xem PLAN.md mục 4.
    if not (lon1 <= 103.0 and lon2 >= 109.0 and lat1 <= 9.0 and lat2 >= 23.0):
        loi.append(f"bounds {h['bounds']} không trùm hết đất liền Việt Nam")

    if cu:
        if h["maxzoom"] < cu["maxzoom"]:
            loi.append(f"maxzoom tụt {cu['maxzoom']} -> {h['maxzoom']}")
        for khoa, ten in (("kich_thuoc", "dung lượng"), ("so_o", "số ô")):
            if h[khoa] < cu[khoa] * TI_LE_TOI_THIEU:
                loi.append(f"{ten} co còn {h[khoa] / cu[khoa]:.0%} so với bản đang chạy")
    return loi


# ------------------------------------------------------------- các bước
def chay(lenh: list[str], ten: str) -> None:
    print(f"  {ten} ...", flush=True)
    if subprocess.run(lenh, cwd=GOC).returncode != 0:
        sys.exit(f"Hỏng ở bước {ten}")


def dung_ban_moi() -> None:
    if not PLANETILER.is_file():
        sys.exit(f"Thiếu {PLANETILER.relative_to(GOC)}")
    BAN_MOI.unlink(missing_ok=True)
    chay(lenh_planetiler(), "Planetiler dựng bản mới")


def lenh_planetiler() -> list[str]:
    """Lệnh dựng. Tách ra để assert kiểm được, vì một cờ thiếu là hỏng cả việc.

    `--refresh-sources` là BẮT BUỘC: `--download` chỉ tải tệp còn THIẾU, nó
    không tải bản mới hơn của tệp đã có (`refresh_sources=false` là mặc định).
    Thiếu cờ này thì script cập nhật hàng tuần sẽ dựng lại y nguyên dữ liệu cũ
    và báo thành công mãi mãi — đã kiểm chứng: lần chạy đầu dùng lại
    `vietnam.osm.pbf` của ba ngày trước mà không nói gì.
    """
    return ["java", f"-Xmx{RAM}", "-jar", str(PLANETILER),
            "--download", "--refresh-sources", "--area=vietnam",
            # Mặc định 30 giây là quá ngắn cho nguồn phụ trên GitHub: đã ném
            # TimeoutException ngay ở bước HỎI KÍCH THƯỚC tệp, chưa tải byte
            # nào. Hỏng ở đây thì không đụng gì tới bản đang chạy, nhưng việc
            # cập nhật coi như trượt tuần đó.
            "--http-timeout=120s", "--http-retries=5",
            f"--output={BAN_MOI}", f"--download-dir={GOC / 'data' / 'osm'}",
            "--force"]


def cho_san_sang(giay: int = 90) -> bool:
    """Đợi TileServer GL vẽ được ô đầu tiên sau khi nạp lại.

    Nó mất vài giây để mở tệp PMTiles và dựng style. Kiểm ngay sau `restart`
    thì gặp 502 và tưởng là tệp mới hỏng — đã dính thật một lần, và lần đó
    bản mới hoàn toàn lành vẫn bị quay lại.
    """
    z, x, y = O_KIEM
    for _ in range(giay):
        ma, kieu, n = lay(f"/tiles/nen/{z}/{x}/{y}.png")
        if ma == 200 and kieu.startswith("image/png"):
            return True
        time.sleep(1)
    return False


def nap_lai_may_chu() -> None:
    """Nạp lại dịch vụ ô raster và XOÁ cache — thiếu bước xoá là coi như chưa đổi."""
    chay(["docker", "compose", "restart", "o-raster"], "nạp lại TileServer GL")
    # Xoá cache TRƯỚC khi chờ: nếu không, chính lượt gọi để chờ sẵn sàng lại
    # nạp ô cũ vào cache rồi ta xoá mất, hoặc tệ hơn là ta xoá xong thì ô cũ
    # đã kịp quay lại cache.
    chay(["docker", "compose", "exec", "-T", "web",
          "find", "/var/cache/nginx", "-type", "f", "-delete"],
         "xoá cache ô raster của nginx")
    print("  đợi TileServer GL sẵn sàng ...", flush=True)
    if not cho_san_sang():
        print("  CẢNH BÁO: quá lâu mà chưa vẽ được ô nào")


def lay(duong: str, header: dict | None = None) -> tuple[int, str, int]:
    """Gọi máy chủ, trả (mã, content-type, số byte). Không ném lỗi khi 4xx/5xx."""
    req = urllib.request.Request(MAY_CHU + duong, headers=header or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.headers.get("Content-Type", ""), len(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), 0


def kiem_qua_may_chu() -> list[str]:
    """Kiểm qua chính đường mà ứng dụng sẽ đi. Đây mới là bằng chứng thật."""
    loi = []

    z, x, y = O_KIEM
    ma, kieu, n = lay(f"/tiles/nen/{z}/{x}/{y}.png")
    if ma != 200 or not kieu.startswith("image/png"):
        loi.append(f"ô raster trả {ma} {kieu}")
    elif n < 2000:
        # 200 mà ảnh bé tí nghĩa là ô trắng: style và ô không khớp nhau nữa.
        loi.append(f"ô raster chỉ {n} byte — gần như trắng")

    ma, kieu, _ = lay("/tiles/vietnam.pmtiles", {"Range": "bytes=0-126"})
    if ma != 206:
        loi.append(f"PMTiles không trả 206 cho Range (trả {ma})")

    # HTTP 200 kèm text/html là bẫy SPA fallback — phải tính là lỗi, kể cả khi
    # mã là 200. CLAUDE.md.
    if "text/html" in kieu:
        loi.append("PMTiles trả text/html — rơi vào SPA fallback")
    return loi


def doi_sang_ban_moi() -> None:
    BAN_CU.unlink(missing_ok=True)
    DANG_CHAY.replace(BAN_CU)
    BAN_MOI.replace(DANG_CHAY)
    print(f"  đã đổi: {BAN_MOI.name} -> {DANG_CHAY.name}, "
          f"giữ bản cũ ở {BAN_CU.name}")


def quay_lai() -> None:
    if not BAN_CU.is_file():
        sys.exit(f"Không có {BAN_CU.name} để quay lại.")
    hong = TILES / "vietnam.hong.pmtiles"
    hong.unlink(missing_ok=True)
    if DANG_CHAY.is_file():
        DANG_CHAY.replace(hong)
    BAN_CU.replace(DANG_CHAY)
    print(f"  đã quay lại bản cũ; bản nghi hỏng để ở {hong.name}")
    nap_lai_may_chu()


# ----------------------------------------------------------------- chính
def cap_nhat(chi_dung: bool = False, chi_doi: bool = False) -> None:
    cu = doc_header(DANG_CHAY) if DANG_CHAY.is_file() else None
    if cu:
        print(f"Đang chạy: {mo_ta(cu)}")

    if chi_doi:
        # Dựng lại mất vài phút. Khi lần đổi trước hỏng vì lý do KHÔNG nằm ở
        # tệp (dịch vụ chưa kịp lên, hết đĩa...) thì dựng lại là phí.
        if not BAN_MOI.is_file():
            sys.exit(f"Không có {BAN_MOI.name} để đổi. Bỏ --chi-doi để dựng.")
        print(f"--chi-doi: dùng {BAN_MOI.name} có sẵn, không dựng lại")
    else:
        print("Dựng bản mới:")
        dung_ban_moi()
    moi = doc_header(BAN_MOI)
    print(f"Bản mới:   {mo_ta(moi)}")

    loi = kiem_header(moi, cu)
    if loi:
        print("\nBản mới KHÔNG đạt, giữ nguyên bản đang chạy:")
        for l in loi:
            print(f"  - {l}")
        sys.exit(1)
    print("Kiểm header: đạt")

    if chi_dung:
        print(f"\n--chi-dung: để nguyên {BAN_MOI.name}, chưa đổi.")
        return

    print("Đổi sang bản mới:")
    doi_sang_ban_moi()
    nap_lai_may_chu()

    loi = kiem_qua_may_chu()
    if loi:
        print("\nKiểm sau khi đổi KHÔNG đạt — quay lại bản cũ:")
        for l in loi:
            print(f"  - {l}")
        quay_lai()
        sys.exit(1)

    print("Kiểm qua máy chủ: đạt")
    print(f"\nXong. Quay lại bằng: python scripts/capnhat-osm.py --quay-lai")


# -------------------------------------------------------------- tự kiểm tra
def tu_kiem_tra() -> int:
    loi = 0

    def kd(dk, ten):
        nonlocal loi
        if dk:
            print(f"đúng: {ten}")
        else:
            loi += 1
            print(f"SAI: {ten}")

    # Mẫu một tệp lành, viết thẳng ra đây chứ không đọc từ đĩa: bản sao kho
    # vừa clone về CHƯA có data/, mà self-check thì phải chạy được ở mọi nơi.
    that = {"so_o": 415762, "so_muc": 123435, "kieu_o": 1,
            "minzoom": 0, "maxzoom": 14,
            "bounds": [102.0959, 7.3822, 114.6423, 23.4021],
            "kich_thuoc": 319530512}
    kd(kiem_header(that, None) == [], "một tệp lành thì đạt mọi điều kiện")
    kd(kiem_header(that, that) == [], "so chính nó với chính nó thì không báo lỗi")

    # Các kiểu hỏng phải BẮT được. Đây là lý do tồn tại của cả tệp này: đổi
    # nhầm sang một tệp hỏng thì bản đồ trắng mà mọi request vẫn 200.
    nho = dict(that, kich_thuoc=int(that["kich_thuoc"] * 0.5))
    kd(any("dung lượng" in l for l in kiem_header(nho, that)),
       "bắt được tệp co còn một nửa")

    it_o = dict(that, so_o=100)
    kd(kiem_header(it_o, that) != [], "bắt được tệp gần như rỗng")

    tut = dict(that, maxzoom=that["maxzoom"] - 2)
    kd(any("maxzoom" in l for l in kiem_header(tut, that)), "bắt được maxzoom tụt")

    raster = dict(that, kieu_o=2)
    kd(any("kiểu ô" in l for l in kiem_header(raster, that)),
       "bắt được tệp raster đem dùng làm nguồn vector")

    hep = dict(that, bounds=[105.0, 20.0, 106.0, 21.0])
    kd(any("bounds" in l for l in kiem_header(hep, that)),
       "bắt được tệp chỉ phủ một tỉnh mà tưởng là cả nước")

    # Ngược lại: KHÔNG được đòi ô nền vươn tới Trường Sa. Lớp chủ quyền nằm
    # trong style, không nằm trong ô nền — đòi ở đây là chặn nhầm bản tốt.
    kd(kiem_header(that, None) == [] and that["bounds"][2] < 117.0,
       "không đòi ô nền phủ tới Trường Sa (lớp chủ quyền ở style)")

    # Thiếu --refresh-sources là script này vô dụng: dựng lại dữ liệu cũ và
    # báo thành công. Không nhìn ra được từ kết quả, nên phải assert ở đây.
    lenh = lenh_planetiler()
    kd("--refresh-sources" in lenh, "lệnh dựng có --refresh-sources")
    kd("--download" in lenh and "--force" in lenh, "lệnh dựng có --download và --force")
    kd(any(str(BAN_MOI) in x for x in lenh), "dựng ra bản .moi, không ghi đè bản đang chạy")

    # Tệp không phải PMTiles thì phải ném lỗi rõ ràng, không đọc bừa.
    gia = GOC / "web" / "phamvi.json"
    try:
        doc_header(gia)
        kd(False, "từ chối tệp không phải PMTiles")
    except ValueError:
        kd(True, "từ chối tệp không phải PMTiles")

    # Có tệp thật thì kiểm luôn; không có cũng không sao — kho vừa clone về
    # chưa dựng ô bao giờ.
    if DANG_CHAY.is_file():
        thuc = doc_header(DANG_CHAY)
        kd(thuc["kieu_o"] == 1 and thuc["so_o"] > 100000,
           f"đọc được header tệp đang chạy ({mo_ta(thuc)})")
        kd(kiem_header(thuc, None) == [], "tệp đang chạy đạt mọi điều kiện")
    else:
        print(f"bỏ qua: chưa có {DANG_CHAY.name}, chỉ kiểm phần logic")

    print("Tự kiểm tra: tất cả đúng" if loi == 0 else f"Tự kiểm tra: {loi} lỗi")
    return loi


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(1 if tu_kiem_tra() else 0)
    if "--quay-lai" in sys.argv:
        quay_lai()
        sys.exit(0)
    if "--chi-kiem" in sys.argv:
        h = doc_header(DANG_CHAY)
        print(f"Đang chạy: {mo_ta(h)}")
        l = kiem_header(h, None) + kiem_qua_may_chu()
        for x in l:
            print(f"  - {x}")
        print("Đạt" if not l else "KHÔNG đạt")
        sys.exit(1 if l else 0)

    cap_nhat(chi_dung="--chi-dung" in sys.argv, chi_doi="--chi-doi" in sys.argv)
