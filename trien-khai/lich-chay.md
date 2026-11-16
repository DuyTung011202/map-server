# Lịch chạy định kỳ

Máy chủ bản đồ chỉ có **một** việc cần chạy lặp: dựng lại ô nền từ OSM mới.
Ô địa hình, ô vệ tinh và nền thế giới đều từ nguồn gần như không đổi (SRTM,
Sentinel-2 một thời điểm, Natural Earth), dựng một lần là xong.

## Trên máy chủ Linux

```cron
# Dựng lại ô nền từ OSM mới, 3 giờ sáng Chủ nhật.
# Giờ thấp điểm vì bước đổi có vài giây nạp lại TileServer GL.
0 3 * * 0 cd /opt/map && /usr/bin/python3 scripts/capnhat-osm.py >> /var/log/capnhat-osm.log 2>&1
```

Hàng tuần là đủ — OSM Việt Nam không đổi nhanh hơn thế, và mỗi lần dựng tải
về hơn 1 GB nguồn.

**Đừng chạy hai lần chồng nhau.** Một lần dựng mất 10–40 phút tuỳ mạng. Nếu
sợ chồng, bọc bằng `flock`:

```cron
0 3 * * 0 /usr/bin/flock -n /tmp/capnhat-osm.lock -c 'cd /opt/map && python3 scripts/capnhat-osm.py' >> /var/log/capnhat-osm.log 2>&1
```

## Trên Windows (máy phát triển)

Tôi **không tự đăng ký** lịch này — nó là thiết lập hệ thống, bạn tự chạy nếu
muốn. Mở PowerShell **quyền quản trị**:

```powershell
$h = New-ScheduledTaskAction -Execute "python" `
     -Argument "scripts\capnhat-osm.py" -WorkingDirectory "D:\Projects\Map"
$k = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3am
Register-ScheduledTask -TaskName "capnhat-o-ban-do" -Action $h -Trigger $k
```

Gỡ: `Unregister-ScheduledTask -TaskName "capnhat-o-ban-do"`.

## Kiểm lịch có chạy thật không

Script tự kiểm sau khi đổi và tự quay lại khi hỏng, nên lịch im lặng **không**
có nghĩa là nó chạy đúng — có thể nó chưa chạy lần nào. Kiểm bằng ngày của ô
đang phục vụ:

```bash
python scripts/capnhat-osm.py --chi-kiem
ls -la data/tiles/vietnam.pmtiles
```

Ngày sửa tệp phải trong vòng một tuần. Nếu cũ hơn, lịch không chạy.
