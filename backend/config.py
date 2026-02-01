"""
配置管理模块

从 config/config.yaml 加载配置，提供统一的配置访问接口
"""
import yaml
from pathlib import Path
from typing import Any, Optional

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# 全局配置对象
_config: Optional[dict] = None


def _load_config() -> dict:
    """加载配置文件"""
    global _config
    if _config is not None:
        return _config

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_FILE}")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)

    return _config


def get(key: str, default: Any = None) -> Any:
    """
    获取配置值，支持点号分隔的嵌套键

    示例:
        get("server.port")  # 返回 8000
        get("qq_notify.targets.私人.id")  # 返回 1608900366
    """
    config = _load_config()
    keys = key.split(".")
    value = config

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default

    return value


def reload():
    """重新加载配置文件"""
    global _config
    _config = None
    _load_config()


# ========== 便捷访问器 ==========

class ServerConfig:
    """服务配置"""
    @property
    def host(self) -> str:
        return get("server.host", "127.0.0.1")

    @property
    def port(self) -> int:
        return get("server.port", 8000)

    @property
    def mcp_host(self) -> str:
        return get("server.mcp_host", "0.0.0.0")

    @property
    def mcp_port(self) -> int:
        return get("server.mcp_port", 8002)


class AuthConfig:
    """认证配置"""
    @property
    def app_name(self) -> str:
        return get("auth.app_name", "LocalDashboard")

    @property
    def token_valid_days(self) -> int:
        return get("auth.token_valid_days", 7)


class MobileDeviceConfig:
    """移动设备配置"""
    @property
    def timeout_seconds(self) -> int:
        return get("mobile_device.timeout_seconds", 60)


class ReminderConfig:
    """提醒配置"""
    @property
    def check_interval(self) -> int:
        return get("reminder.check_interval", 30)


class QQNotifyConfig:
    """QQ 通知配置"""
    @property
    def ws_url(self) -> str:
        return get("qq_notify.ws_url", "")

    @property
    def token(self) -> str:
        return get("qq_notify.token", "")

    @property
    def targets(self) -> dict:
        return get("qq_notify.targets", {})


# 配置实例
server = ServerConfig()
auth = AuthConfig()
mobile_device = MobileDeviceConfig()
reminder = ReminderConfig()
qq_notify = QQNotifyConfig()
