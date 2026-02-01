"""
TOTP 两步验证模块
"""
import secrets
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

import pyotp
import qrcode

import config


# 配置
CONFIG_DIR = Path(__file__).parent.parent / "config"
SECRET_FILE = CONFIG_DIR / "totp_secret.txt"
QR_CODE_FILE = CONFIG_DIR / "totp_qrcode.png"

# 从配置读取
def _get_app_name() -> str:
    return config.auth.app_name

def _get_token_valid_days() -> int:
    return config.auth.token_valid_days

# 导出供其他模块使用（兼容旧代码）
TOKEN_VALID_DAYS = 7  # 默认值，实际使用 _get_token_valid_days()

# 已验证设备的 token 存储（内存中，重启后失效需重新验证）
# 格式: {token_hash: expire_time}
_verified_tokens: dict[str, datetime] = {}


def _ensure_config_dir():
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_or_create_secret() -> str:
    """获取或创建 TOTP 密钥"""
    _ensure_config_dir()

    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()

    # 生成新密钥
    secret = pyotp.random_base32()
    SECRET_FILE.write_text(secret)

    # 生成二维码
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name="local", issuer_name=_get_app_name())

    qr = qrcode.make(uri)
    qr.save(QR_CODE_FILE)

    print(f"[AUTH] 已生成 TOTP 密钥和二维码")
    print(f"[AUTH] 二维码位置: {QR_CODE_FILE}")

    return secret


def verify_totp(code: str) -> bool:
    """验证 TOTP 码"""
    secret = get_or_create_secret()
    totp = pyotp.TOTP(secret)
    # valid_window=1 允许前后 30 秒的误差
    return totp.verify(code, valid_window=1)


def generate_device_token() -> str:
    """生成设备验证 token"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """对 token 进行哈希"""
    return hashlib.sha256(token.encode()).hexdigest()


def register_verified_token(token: str):
    """注册已验证的 token"""
    token_hash = hash_token(token)
    expire_time = datetime.now() + timedelta(days=_get_token_valid_days())
    _verified_tokens[token_hash] = expire_time


def is_token_valid(token: str) -> bool:
    """检查 token 是否有效"""
    if not token:
        return False

    token_hash = hash_token(token)
    expire_time = _verified_tokens.get(token_hash)

    if not expire_time:
        return False

    if datetime.now() > expire_time:
        # 过期，删除
        del _verified_tokens[token_hash]
        return False

    return True


def get_token_expire_days(token: str) -> int:
    """获取 token 剩余有效天数"""
    if not token:
        return 0

    token_hash = hash_token(token)
    expire_time = _verified_tokens.get(token_hash)

    if not expire_time:
        return 0

    remaining = expire_time - datetime.now()
    return max(0, remaining.days)


# 启动时确保密钥存在
get_or_create_secret()


if __name__ == "__main__":
    # 测试
    print(f"密钥文件: {SECRET_FILE}")
    print(f"二维码文件: {QR_CODE_FILE}")

    code = input("输入验证码: ")
    if verify_totp(code):
        print("验证成功!")
        token = generate_device_token()
        register_verified_token(token)
        print(f"Token: {token}")
        print(f"有效: {is_token_valid(token)}")
    else:
        print("验证失败!")
