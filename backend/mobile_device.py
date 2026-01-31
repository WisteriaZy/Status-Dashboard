"""
移动设备状态管理
"""
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# 配置
CONFIG_DIR = Path(__file__).parent.parent / "config"
SECRET_FILE = CONFIG_DIR / "device_secret.txt"

# 设备状态存储（内存）
# 格式: {device_id: {show_name, using, app_name, battery, charging, last_update}}
_devices: dict[str, dict] = {}

# 设备超时时间（秒），超过此时间视为离线
DEVICE_TIMEOUT = 60


def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_or_create_secret() -> str:
    """获取或创建设备推送密钥"""
    _ensure_config_dir()

    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()

    # 生成新密钥
    secret = secrets.token_urlsafe(32)
    SECRET_FILE.write_text(secret)
    print(f"[DEVICE] 已生成设备密钥: {secret}")
    print(f"[DEVICE] 密钥文件: {SECRET_FILE}")
    return secret


def verify_secret(secret: str) -> bool:
    """验证设备密钥"""
    return secret == get_or_create_secret()


def update_device(
    device_id: str,
    show_name: str,
    using: bool,
    app_name: str = "",
    battery: Optional[int] = None,
    charging: Optional[bool] = None,
):
    """更新设备状态"""
    _devices[device_id] = {
        "show_name": show_name,
        "using": using,
        "app_name": app_name,
        "battery": battery,
        "charging": charging,
        "last_update": datetime.now(),
    }


def get_devices() -> list:
    """获取所有设备状态"""
    now = datetime.now()
    result = []

    for device_id, info in _devices.items():
        # 检查是否超时
        elapsed = (now - info["last_update"]).total_seconds()
        online = elapsed < DEVICE_TIMEOUT

        result.append({
            "id": device_id,
            "show_name": info["show_name"],
            "using": info["using"] if online else False,
            "app_name": info["app_name"] if online else "",
            "battery": info["battery"],
            "charging": info["charging"],
            "online": online,
            "last_update": info["last_update"].strftime("%H:%M:%S"),
        })

    return result


def get_device(device_id: str) -> Optional[dict]:
    """获取单个设备状态"""
    if device_id not in _devices:
        return None

    info = _devices[device_id]
    now = datetime.now()
    elapsed = (now - info["last_update"]).total_seconds()
    online = elapsed < DEVICE_TIMEOUT

    return {
        "id": device_id,
        "show_name": info["show_name"],
        "using": info["using"] if online else False,
        "app_name": info["app_name"] if online else "",
        "battery": info["battery"],
        "charging": info["charging"],
        "online": online,
        "last_update": info["last_update"].strftime("%H:%M:%S"),
    }


# 启动时确保密钥存在
get_or_create_secret()
