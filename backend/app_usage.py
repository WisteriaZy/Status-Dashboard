"""
应用使用时间统计模块

只统计活动窗口的应用使用时间
支持小时级统计（用于热力图）
"""
import json
import threading
import time
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional

from window_tracker import get_active_window_info

# 数据文件
DATA_DIR = Path(__file__).parent.parent / "data"
USAGE_FILE = DATA_DIR / "app_usage.json"

# 采样间隔（秒）
SAMPLE_INTERVAL = 5

# 全局状态
_tracker_thread: Optional[threading.Thread] = None
_tracker_running = False

# 内存中的今日使用数据
# 结构: {process_name: {"total": int, "hours": {"HH": int}}}
_today_usage: dict[str, dict] = {}
_today_date: Optional[str] = None


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_usage() -> dict:
    """加载使用时间数据"""
    _ensure_data_dir()
    if USAGE_FILE.exists():
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            # 迁移旧版数据格式
            if data.get("version", 1) == 1:
                data = _migrate_v1_to_v2(data)
            return data
        except (json.JSONDecodeError, IOError):
            pass
    return {"daily": {}, "version": 2}


def _migrate_v1_to_v2(data: dict) -> dict:
    """将 v1 数据格式迁移到 v2（添加小时级统计）"""
    new_data = {"daily": {}, "version": 2}

    for date_str, apps in data.get("daily", {}).items():
        new_data["daily"][date_str] = {}
        for process_name, seconds in apps.items():
            if isinstance(seconds, int):
                # v1 格式：直接是秒数
                new_data["daily"][date_str][process_name] = {
                    "total": seconds,
                    "hours": {}  # 历史数据无小时分布
                }
            else:
                # 已经是 v2 格式
                new_data["daily"][date_str][process_name] = seconds

    return new_data


def _save_usage(data: dict):
    """保存使用时间数据"""
    _ensure_data_dir()
    USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_today_str() -> str:
    """获取今天的日期字符串"""
    return date.today().isoformat()


def _get_current_hour() -> str:
    """获取当前小时字符串（00-23）"""
    return datetime.now().strftime("%H")


def _init_today():
    """初始化今日数据"""
    global _today_usage, _today_date

    today = _get_today_str()

    # 如果日期变了，保存昨天的数据并重新加载
    if _today_date != today:
        if _today_date is not None:
            _flush_to_disk()

        # 加载今日数据
        data = _load_usage()
        _today_usage = data.get("daily", {}).get(today, {})
        _today_date = today


def _flush_to_disk():
    """将内存数据写入磁盘"""
    global _today_usage, _today_date

    if not _today_date:
        return

    data = _load_usage()
    if "daily" not in data:
        data["daily"] = {}

    data["daily"][_today_date] = _today_usage
    data["version"] = 2
    _save_usage(data)


def _tracker_loop():
    """使用时间追踪循环"""
    global _tracker_running

    print("[USAGE] 使用时间追踪器开始运行")

    last_flush = time.time()

    while _tracker_running:
        try:
            _init_today()

            # 获取当前活动窗口
            window = get_active_window_info()
            process_name = window.get("process_name", "")

            if process_name:
                current_hour = _get_current_hour()

                # 初始化应用数据结构
                if process_name not in _today_usage:
                    _today_usage[process_name] = {"total": 0, "hours": {}}

                app_data = _today_usage[process_name]

                # 累加总时间
                app_data["total"] += SAMPLE_INTERVAL

                # 累加小时时间
                if current_hour not in app_data["hours"]:
                    app_data["hours"][current_hour] = 0
                app_data["hours"][current_hour] += SAMPLE_INTERVAL

            # 每 60 秒写入磁盘一次
            if time.time() - last_flush >= 60:
                _flush_to_disk()
                last_flush = time.time()

        except Exception as e:
            print(f"[USAGE] 追踪出错: {e}")

        time.sleep(SAMPLE_INTERVAL)

    # 退出时保存
    _flush_to_disk()
    print("[USAGE] 使用时间追踪器已停止")


def start_tracker():
    """启动使用时间追踪器"""
    global _tracker_thread, _tracker_running

    if _tracker_running:
        return

    _tracker_running = True
    _tracker_thread = threading.Thread(target=_tracker_loop, daemon=True)
    _tracker_thread.start()
    print("[USAGE] 使用时间追踪器已启动")


def stop_tracker():
    """停止使用时间追踪器"""
    global _tracker_running
    _tracker_running = False


def get_today_usage() -> dict[str, int]:
    """获取今日使用时间（秒）- 兼容旧接口"""
    _init_today()
    result = {}
    for process_name, data in _today_usage.items():
        if isinstance(data, dict):
            result[process_name] = data.get("total", 0)
        else:
            result[process_name] = data  # v1 兼容
    return result


def get_today_usage_detail() -> dict[str, dict]:
    """获取今日使用时间详情（含小时分布）"""
    _init_today()
    return dict(_today_usage)


def get_usage_by_date(date_str: str) -> dict[str, int]:
    """获取指定日期的使用时间（总计）"""
    if date_str == _get_today_str():
        return get_today_usage()

    data = _load_usage()
    day_data = data.get("daily", {}).get(date_str, {})

    result = {}
    for process_name, app_data in day_data.items():
        if isinstance(app_data, dict):
            result[process_name] = app_data.get("total", 0)
        else:
            result[process_name] = app_data  # v1 兼容
    return result


def get_usage_by_date_detail(date_str: str) -> dict[str, dict]:
    """获取指定日期的使用时间详情（含小时分布）"""
    if date_str == _get_today_str():
        return get_today_usage_detail()

    data = _load_usage()
    day_data = data.get("daily", {}).get(date_str, {})

    # 确保格式统一
    result = {}
    for process_name, app_data in day_data.items():
        if isinstance(app_data, dict):
            result[process_name] = app_data
        else:
            result[process_name] = {"total": app_data, "hours": {}}
    return result


def get_usage_range(start_date: str, end_date: str) -> dict[str, dict[str, int]]:
    """获取日期范围内的使用时间"""
    data = _load_usage()
    daily = data.get("daily", {})

    result = {}
    for date_str in daily:
        if start_date <= date_str <= end_date:
            result[date_str] = get_usage_by_date(date_str)

    # 如果包含今天，使用内存中的数据
    today = _get_today_str()
    if start_date <= today <= end_date:
        result[today] = get_today_usage()

    return result


def get_week_summary() -> dict:
    """获取最近 7 天的使用统计摘要"""
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]

    daily_totals = []
    all_apps = set()

    for date_str in dates:
        usage = get_usage_by_date(date_str)
        total = sum(usage.values())
        daily_totals.append({
            "date": date_str,
            "total": total,
            "formatted": format_duration(total),
        })
        all_apps.update(usage.keys())

    # 计算每个应用的周总计
    app_totals = {}
    for process_name in all_apps:
        total = 0
        for date_str in dates:
            usage = get_usage_by_date(date_str)
            total += usage.get(process_name, 0)
        app_totals[process_name] = total

    # 排序应用
    sorted_apps = sorted(app_totals.items(), key=lambda x: -x[1])

    return {
        "dates": dates,
        "daily_totals": daily_totals,
        "apps": [
            {
                "process_name": name,
                "total": total,
                "formatted": format_duration(total),
            }
            for name, total in sorted_apps
        ],
        "week_total": sum(d["total"] for d in daily_totals),
        "week_total_formatted": format_duration(sum(d["total"] for d in daily_totals)),
    }


def get_month_summary() -> dict:
    """获取最近 30 天的使用统计摘要"""
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]

    daily_totals = []
    all_apps = set()

    for date_str in dates:
        usage = get_usage_by_date(date_str)
        total = sum(usage.values())
        daily_totals.append({
            "date": date_str,
            "total": total,
            "formatted": format_duration(total),
        })
        all_apps.update(usage.keys())

    # 计算每个应用的月总计
    app_totals = {}
    for process_name in all_apps:
        total = 0
        for date_str in dates:
            usage = get_usage_by_date(date_str)
            total += usage.get(process_name, 0)
        app_totals[process_name] = total

    # 排序应用
    sorted_apps = sorted(app_totals.items(), key=lambda x: -x[1])

    return {
        "dates": dates,
        "daily_totals": daily_totals,
        "apps": [
            {
                "process_name": name,
                "total": total,
                "formatted": format_duration(total),
            }
            for name, total in sorted_apps
        ],
        "month_total": sum(d["total"] for d in daily_totals),
        "month_total_formatted": format_duration(sum(d["total"] for d in daily_totals)),
    }


def get_app_detail(process_name: str, days: int = 30) -> dict:
    """获取指定应用的详细使用数据（用于热力图）"""
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    # 构建热力图数据：每天每小时的使用时间
    heatmap = []  # [{date, hour, seconds}]
    daily_data = []

    for date_str in dates:
        detail = get_usage_by_date_detail(date_str)
        app_data = detail.get(process_name, {"total": 0, "hours": {}})

        daily_data.append({
            "date": date_str,
            "total": app_data.get("total", 0),
            "formatted": format_duration(app_data.get("total", 0)),
        })

        hours = app_data.get("hours", {})
        for hour in range(24):
            hour_str = f"{hour:02d}"
            seconds = hours.get(hour_str, 0)
            heatmap.append({
                "date": date_str,
                "hour": hour,
                "seconds": seconds,
            })

    total = sum(d["total"] for d in daily_data)

    return {
        "process_name": process_name,
        "days": days,
        "dates": dates,
        "daily": daily_data,
        "heatmap": heatmap,
        "total": total,
        "total_formatted": format_duration(total),
    }


def get_app_usage_today(process_name: str) -> int:
    """获取指定应用今日使用时间（秒）"""
    _init_today()
    app_data = _today_usage.get(process_name, {})
    if isinstance(app_data, dict):
        return app_data.get("total", 0)
    return app_data


def format_duration(seconds: int) -> str:
    """格式化时长显示"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分钟"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}小时{minutes}分钟"
        return f"{hours}小时"


def get_available_dates() -> list[str]:
    """获取有数据的日期列表"""
    data = _load_usage()
    dates = list(data.get("daily", {}).keys())

    # 添加今天
    today = _get_today_str()
    if today not in dates and _today_usage:
        dates.append(today)

    dates.sort(reverse=True)
    return dates


if __name__ == "__main__":
    # 测试
    print("启动使用时间追踪测试...")
    start_tracker()

    try:
        while True:
            time.sleep(10)
            usage = get_today_usage()
            print(f"\n今日使用时间:")
            for app, seconds in sorted(usage.items(), key=lambda x: -x[1])[:5]:
                print(f"  {app}: {format_duration(seconds)}")
    except KeyboardInterrupt:
        stop_tracker()
        print("\n已停止")
