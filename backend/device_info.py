"""
设备信息采集（CPU、内存、磁盘、运行时间）
"""
import psutil
import time


# 系统启动时间（秒级时间戳）
_boot_time = psutil.boot_time()


def get_device_info() -> dict:
    """
    获取设备基础信息

    Returns:
        {
            "cpu_percent": 25.5,
            "memory_percent": 60.2,
            "memory_used_gb": 9.6,
            "memory_total_gb": 16.0,
            "uptime_seconds": 3600,
            "disks": [...]
        }
    """
    # CPU 使用率（非阻塞，取上次调用间隔的平均值）
    cpu_percent = psutil.cpu_percent(interval=None)

    # 内存信息
    mem = psutil.virtual_memory()
    memory_percent = mem.percent
    memory_used_gb = round(mem.used / (1024**3), 1)
    memory_total_gb = round(mem.total / (1024**3), 1)

    # 运行时间
    uptime_seconds = int(time.time() - _boot_time)

    # 磁盘信息
    disks = get_disk_info()

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "memory_used_gb": memory_used_gb,
        "memory_total_gb": memory_total_gb,
        "uptime_seconds": uptime_seconds,
        "disks": disks,
    }


def get_disk_info() -> list:
    """
    获取所有磁盘分区信息

    Returns:
        [
            {
                "device": "C:",
                "mountpoint": "C:\\",
                "fstype": "NTFS",
                "total_gb": 500.0,
                "used_gb": 200.0,
                "free_gb": 300.0,
                "percent": 40.0
            },
            ...
        ]
    """
    import re

    disks = []
    seen_devices = set()

    for partition in psutil.disk_partitions():
        # 跳过光驱和无文件系统的分区
        if "cdrom" in partition.opts or partition.fstype == "":
            continue

        # 只保留标准盘符挂载点（如 C:\, D:\）
        if not re.match(r"^[A-Z]:\\$", partition.mountpoint):
            continue

        # 去重（同一盘符可能有多个挂载点）
        device = partition.device.rstrip("\\")
        if device in seen_devices:
            continue
        seen_devices.add(device)

        try:
            usage = psutil.disk_usage(partition.mountpoint)
            # 跳过容量异常的分区（如虚拟文件系统）
            if usage.total > 1024 * 1024 * 1024 * 1024 * 100:  # > 100 TB
                continue

            disks.append({
                "device": device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "percent": usage.percent,
            })
        except (PermissionError, OSError):
            continue

    return disks


def format_uptime(seconds: int) -> str:
    """将秒数格式化为易读字符串"""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}分钟")

    return "".join(parts)


if __name__ == "__main__":
    info = get_device_info()
    print(f"CPU: {info['cpu_percent']}%")
    print(f"内存: {info['memory_used_gb']}/{info['memory_total_gb']} GB ({info['memory_percent']}%)")
    print(f"运行时间: {format_uptime(info['uptime_seconds'])}")
    print("\n磁盘:")
    for disk in info['disks']:
        print(f"  {disk['device']} ({disk['fstype']}): {disk['used_gb']}/{disk['total_gb']} GB ({disk['percent']}%)")
