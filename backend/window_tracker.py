"""
Windows 活动窗口信息采集
"""
import json
from pathlib import Path

import win32gui
import win32process
import psutil


# 配置文件路径
CONFIG_DIR = Path(__file__).parent
APP_NAMES_FILE = CONFIG_DIR / "app_names.json"


def _load_app_names() -> dict:
    """加载进程名映射表"""
    if APP_NAMES_FILE.exists():
        try:
            with open(APP_NAMES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


# 进程名 → 易读名称 映射表（从 JSON 加载）
APP_NAME_MAP = _load_app_names()

# 需要排除的进程（系统进程、后台服务等）
EXCLUDED_PROCESSES = {
    "TextInputHost.exe",
    "ApplicationFrameHost.exe",
    "SystemSettings.exe",
    "ShellExperienceHost.exe",
    "StartMenuExperienceHost.exe",
    "SearchHost.exe",
    "LockApp.exe",
}


def reload_app_names():
    """重新加载映射表（热更新用）"""
    global APP_NAME_MAP
    APP_NAME_MAP = _load_app_names()


def get_app_name(process_name: str) -> str:
    """获取进程的易读名称"""
    return APP_NAME_MAP.get(process_name, process_name.replace(".exe", ""))


def get_active_window_info() -> dict:
    """
    获取当前活动窗口信息

    Returns:
        {
            "process_name": "chrome.exe",
            "app_name": "Chrome",
            "title": "窗口标题",
            "pid": 1234
        }
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return _empty_result()

        # 获取窗口标题
        title = win32gui.GetWindowText(hwnd)

        # 获取进程ID
        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        # 获取进程名
        try:
            process = psutil.Process(pid)
            process_name = process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "unknown"

        # 映射为易读名称
        app_name = get_app_name(process_name)

        return {
            "process_name": process_name,
            "app_name": app_name,
            "title": title,
            "pid": pid,
        }
    except Exception:
        return _empty_result()


def get_open_apps() -> list:
    """
    获取当前打开的应用程序列表（类似任务管理器"应用"部分）

    Returns:
        [
            {
                "process_name": "chrome.exe",
                "app_name": "Chrome",
                "title": "主窗口标题",
                "pid": 1234
            },
            ...
        ]
    """
    apps = {}  # 用 pid 去重

    def enum_callback(hwnd, _):
        # 只处理可见窗口
        if not win32gui.IsWindowVisible(hwnd):
            return True

        # 获取窗口标题
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True

        # 获取进程信息
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            process_name = process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            return True

        # 排除系统进程
        if process_name in EXCLUDED_PROCESSES:
            return True

        # 用 pid 去重，保留第一个（通常是主窗口）
        if pid not in apps:
            app_name = get_app_name(process_name)
            apps[pid] = {
                "process_name": process_name,
                "app_name": app_name,
                "title": title,
                "pid": pid,
            }

        return True

    win32gui.EnumWindows(enum_callback, None)

    # 按应用名排序
    return sorted(apps.values(), key=lambda x: x["app_name"].lower())


def _empty_result() -> dict:
    return {
        "process_name": "",
        "app_name": "无",
        "title": "",
        "pid": 0,
    }


if __name__ == "__main__":
    # 测试
    print("=== 当前活动窗口 ===")
    info = get_active_window_info()
    print(f"[{info['app_name']}] {info['title']}")

    print("\n=== 打开的应用 ===")
    for app in get_open_apps():
        print(f"[{app['app_name']}] {app['title']}")
