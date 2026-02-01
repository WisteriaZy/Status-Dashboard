"""
本地 TODO 系统
"""
import json
import uuid
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List

# Windows 通知 (优先使用 winotify，备选 win10toast)
NOTIFY_BACKEND = None
try:
    from winotify import Notification
    NOTIFY_BACKEND = "winotify"
except ImportError:
    try:
        from win10toast import ToastNotifier
        NOTIFY_BACKEND = "win10toast"
    except ImportError:
        pass

# 数据文件
DATA_DIR = Path(__file__).parent.parent / "data"
TODOS_FILE = DATA_DIR / "todos.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_todos() -> dict:
    """加载 TODO 数据"""
    _ensure_data_dir()
    if TODOS_FILE.exists():
        try:
            return json.loads(TODOS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {"todos": [], "version": 1}


def _save_todos(data: dict):
    """保存 TODO 数据"""
    _ensure_data_dir()
    TODOS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_todos(include_completed: bool = False) -> List[dict]:
    """获取所有 TODO"""
    data = _load_todos()
    todos = data.get("todos", [])

    if not include_completed:
        todos = [t for t in todos if not t.get("completed")]

    # 排序：重要优先，然后按创建时间
    todos.sort(key=lambda t: (not t.get("important", False), t.get("created_at", "")))

    return todos


def get_todo(todo_id: str) -> Optional[dict]:
    """获取单个 TODO"""
    data = _load_todos()
    for todo in data.get("todos", []):
        if todo["id"] == todo_id:
            return todo
    return None


def add_todo(
    title: str,
    parent_id: Optional[str] = None,
    important: bool = False,
    remind: Optional[dict] = None,
    remind_tag: Optional[str] = None,
    notes: str = "",
) -> dict:
    """
    添加 TODO

    Args:
        title: 标题
        parent_id: 父任务 ID（子任务）
        important: 是否重要
        remind: 提醒配置 dict，支持以下类型：
            - {"type": "once", "at": "2025-01-31T14:30:00"}
            - {"type": "daily", "hours": [9, 14, 18]}
            - {"type": "weekly", "weekdays": [1, 3, 5], "hour": 9}
            - {"type": "monthly", "days": [1, 15], "hour": 9}
        remind_tag: 提醒目标 tag，如 "私人"
        notes: 备注

    Returns:
        新建的 TODO
    """
    data = _load_todos()

    todo = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "notes": notes,
        "completed": False,
        "important": important,
        "parent_id": parent_id,
        "remind": remind,
        "remind_tag": remind_tag,
        "last_reminded_at": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    data["todos"].append(todo)
    _save_todos(data)

    return todo


def update_todo(todo_id: str, **kwargs) -> Optional[dict]:
    """更新 TODO（支持新增字段）"""
    data = _load_todos()

    # 允许更新的字段白名单
    allowed_fields = {
        "title", "notes", "completed", "important", "parent_id",
        "remind", "remind_tag", "last_reminded_at",
        # 兼容旧字段
        "remind_at", "reminded", "completed_at",
    }

    for todo in data["todos"]:
        if todo["id"] == todo_id:
            for key, value in kwargs.items():
                if key in allowed_fields:
                    todo[key] = value

            # 如果更新了 remind，自动重置 last_reminded_at 以便重新触发提醒
            if "remind" in kwargs:
                todo["last_reminded_at"] = None
                todo["reminded"] = False  # 兼容旧字段

            todo["updated_at"] = datetime.now().isoformat()
            _save_todos(data)
            return todo

    return None


def complete_todo(todo_id: str) -> bool:
    """完成 TODO"""
    result = update_todo(todo_id, completed=True, completed_at=datetime.now().isoformat())
    return result is not None


def delete_todo(todo_id: str) -> bool:
    """删除 TODO（包括子任务）"""
    data = _load_todos()

    # 找到要删除的 TODO 和其子任务
    ids_to_delete = {todo_id}

    # 递归查找子任务
    def find_children(parent_id):
        for todo in data["todos"]:
            if todo.get("parent_id") == parent_id:
                ids_to_delete.add(todo["id"])
                find_children(todo["id"])

    find_children(todo_id)

    original_count = len(data["todos"])
    data["todos"] = [t for t in data["todos"] if t["id"] not in ids_to_delete]

    if len(data["todos"]) < original_count:
        _save_todos(data)
        return True

    return False


def toggle_important(todo_id: str) -> Optional[dict]:
    """切换重要状态"""
    todo = get_todo(todo_id)
    if todo:
        return update_todo(todo_id, important=not todo.get("important", False))
    return None


def _parse_naive_dt(s: str) -> Optional[datetime]:
    """解析 ISO 时间字符串，统一返回无时区的 datetime"""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        # 如果带时区，转为本地时间后去掉 tzinfo
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except (ValueError, AttributeError):
        return None


def _is_same_hour_window(dt1: datetime, dt2: datetime) -> bool:
    """判断两个时间是否在同一个小时窗口内"""
    return (dt1.year == dt2.year and dt1.month == dt2.month and
            dt1.day == dt2.day and dt1.hour == dt2.hour)


def _should_remind(todo: dict, now: datetime) -> bool:
    """
    判断任务是否应该触发提醒

    支持新格式 remind 对象，也兼容旧格式 remind_at 字段
    """
    # 已完成的任务不提醒
    if todo.get("completed"):
        return False

    # 获取上次提醒时间
    last_reminded = todo.get("last_reminded_at")
    last_reminded_dt = _parse_naive_dt(last_reminded) if last_reminded else None

    # 优先检查新格式 remind 对象
    remind = todo.get("remind")
    if remind and isinstance(remind, dict):
        remind_type = remind.get("type")

        if remind_type == "once":
            # 一次性提醒：at <= now 且未提醒过
            at = remind.get("at")
            if at:
                remind_time = _parse_naive_dt(at)
                if remind_time and remind_time <= now and last_reminded_dt is None:
                    return True

        elif remind_type == "daily":
            # 每天提醒：当前小时在 hours 中，且今天该小时还没提醒过
            hours = remind.get("hours", [])
            if now.hour in hours:
                if last_reminded_dt is None or not _is_same_hour_window(last_reminded_dt, now):
                    return True

        elif remind_type == "weekly":
            # 每周提醒：当前 weekday 在 weekdays 中，当前小时 == hour，且今天该小时还没提醒过
            # weekday: 1=周一, 7=周日
            weekdays = remind.get("weekdays", [])
            hour = remind.get("hour")
            current_weekday = now.isoweekday()  # 1-7
            if current_weekday in weekdays and now.hour == hour:
                if last_reminded_dt is None or not _is_same_hour_window(last_reminded_dt, now):
                    return True

        elif remind_type == "monthly":
            # 每月提醒：当前 day 在 days 中，当前小时 == hour，且今天该小时还没提醒过
            days = remind.get("days", [])
            hour = remind.get("hour")
            if now.day in days and now.hour == hour:
                if last_reminded_dt is None or not _is_same_hour_window(last_reminded_dt, now):
                    return True

    # 兼容旧格式 remind_at 字段（当作 once 处理）
    remind_at = todo.get("remind_at")
    if remind_at:
        # 检查旧格式的 reminded 字段
        if todo.get("reminded"):
            return False
        remind_time = _parse_naive_dt(remind_at)
        if remind_time and remind_time <= now:
            return True

    return False


def get_pending_reminders() -> List[dict]:
    """获取待发送的提醒"""
    now = datetime.now()
    data = _load_todos()
    pending = []

    for todo in data["todos"]:
        if _should_remind(todo, now):
            pending.append(todo)

    return pending


def mark_reminded(todo_id: str):
    """标记为已提醒（设置 last_reminded_at）"""
    now = datetime.now().isoformat()

    data = _load_todos()
    for todo in data["todos"]:
        if todo["id"] == todo_id:
            todo["last_reminded_at"] = now
            # 兼容旧格式：同时设置 reminded = True
            if "reminded" in todo:
                todo["reminded"] = True
            todo["updated_at"] = now
            _save_todos(data)
            return



# ========== Windows 通知 ==========

def show_windows_notification(title: str, message: str):
    """显示 Windows 系统通知"""
    if NOTIFY_BACKEND == "winotify":
        try:
            toast = Notification(
                app_id="Dashboard",
                title=title,
                msg=message,
            )
            toast.show()
        except Exception as e:
            print(f"[NOTIFY] winotify 失败: {e}")
    elif NOTIFY_BACKEND == "win10toast":
        try:
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=10, threaded=True)
        except Exception as e:
            print(f"[NOTIFY] win10toast 失败: {e}")
    else:
        print(f"[NOTIFY] (通知不可用) {title}: {message}")


# ========== 提醒检查器 ==========

_reminder_thread = None
_reminder_running = False


def _reminder_loop():
    """提醒检查循环"""
    global _reminder_running
    import time
    import traceback

    # 延迟导入避免循环依赖
    from qq_notify import send_notify

    print("[REMIND] 提醒循环线程开始运行")

    while _reminder_running:
        try:
            pending = get_pending_reminders()
            if pending:
                print(f"[REMIND] 发现 {len(pending)} 个待提醒任务")

            for todo in pending:
                title = todo["title"]
                tag = todo.get("remind_tag", "私人")

                # Windows 通知
                show_windows_notification("任务提醒", title)

                # QQ 通知
                if tag:
                    send_notify(tag, f"📋 任务提醒：{title}")

                # 标记已提醒
                mark_reminded(todo["id"])

                print(f"[REMIND] 已发送提醒: {title}")

        except Exception as e:
            print(f"[REMIND] 检查提醒出错: {e}")
            traceback.print_exc()

        # 每 30 秒检查一次
        time.sleep(30)

    print("[REMIND] 提醒循环线程已退出")


def start_reminder_checker():
    """启动提醒检查器"""
    global _reminder_thread, _reminder_running

    if _reminder_running:
        return

    _reminder_running = True
    _reminder_thread = threading.Thread(target=_reminder_loop, daemon=True)
    _reminder_thread.start()
    print("[REMIND] 提醒检查器已启动")


def stop_reminder_checker():
    """停止提醒检查器"""
    global _reminder_running
    _reminder_running = False


# 模块加载时不自动启动，由 main.py 手动调用
# start_reminder_checker()


if __name__ == "__main__":
    # 测试
    print("添加测试 TODO...")
    todo = add_todo("测试任务", important=True)
    print(f"添加成功: {todo}")

    print("\n所有 TODO:")
    for t in get_todos():
        print(f"  [{t['id']}] {t['title']} {'⭐' if t['important'] else ''}")
