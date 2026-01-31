"""
Google Tasks API 集成
"""
import json
from pathlib import Path
from typing import Optional

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# 配置路径
CONFIG_DIR = Path(__file__).parent.parent / "config"
CLIENT_SECRET_FILE = CONFIG_DIR / "google_client.json"
TOKEN_FILE = CONFIG_DIR / "google_token.json"

SCOPES = ["https://www.googleapis.com/auth/tasks"]
REDIRECT_URI = "https://status.wisteriazy.moe/api/todo/callback"


def get_auth_url() -> str:
    """生成 OAuth 授权 URL"""
    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_FILE),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    return auth_url


def handle_callback(code: str) -> bool:
    """处理 OAuth 回调，保存 token"""
    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_FILE),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials

    # 保存 token
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    return True


def _get_credentials() -> Optional[Credentials]:
    """获取有效的凭据"""
    if not TOKEN_FILE.exists():
        return None

    token_data = json.loads(TOKEN_FILE.read_text())
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data.get("scopes"),
    )

    # 刷新过期 token
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # 更新保存的 token
        token_data["token"] = creds.token
        TOKEN_FILE.write_text(json.dumps(token_data, indent=2))

    return creds


def _get_service():
    """获取 Tasks API 服务"""
    creds = _get_credentials()
    if not creds:
        return None
    return build("tasks", "v1", credentials=creds)


def is_connected() -> bool:
    """检查是否已连接 Google Tasks"""
    return _get_credentials() is not None


def get_task_lists() -> list:
    """获取所有任务列表"""
    service = _get_service()
    if not service:
        return []

    result = service.tasklists().list(maxResults=100).execute()
    return [
        {"id": tl["id"], "title": tl["title"]}
        for tl in result.get("items", [])
    ]


def get_tasks(tasklist_id: str = "@default") -> list:
    """获取指定列表的任务"""
    service = _get_service()
    if not service:
        return []

    result = service.tasks().list(
        tasklist=tasklist_id,
        maxResults=100,
        showCompleted=False,
        showHidden=False,
    ).execute()

    tasks = []
    for task in result.get("items", []):
        tasks.append({
            "id": task["id"],
            "title": task.get("title", ""),
            "notes": task.get("notes", ""),
            "status": task.get("status", ""),
            "due": task.get("due", ""),
        })

    return tasks


def complete_task(task_id: str, tasklist_id: str = "@default") -> bool:
    """完成一个任务"""
    service = _get_service()
    if not service:
        return False

    service.tasks().patch(
        tasklist=tasklist_id,
        task=task_id,
        body={"status": "completed"},
    ).execute()
    return True


def delete_task(task_id: str, tasklist_id: str = "@default") -> bool:
    """删除一个任务"""
    service = _get_service()
    if not service:
        return False

    service.tasks().delete(tasklist=tasklist_id, task=task_id).execute()
    return True


def add_task(title: str, notes: str = "", tasklist_id: str = "@default") -> Optional[dict]:
    """添加一个任务"""
    service = _get_service()
    if not service:
        return None

    body = {"title": title}
    if notes:
        body["notes"] = notes

    result = service.tasks().insert(tasklist=tasklist_id, body=body).execute()
    return {
        "id": result["id"],
        "title": result.get("title", ""),
        "status": result.get("status", ""),
    }
