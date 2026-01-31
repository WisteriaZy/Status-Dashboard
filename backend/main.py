"""
Local Device Status Dashboard - Backend
"""
from fastapi import FastAPI, Cookie, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional

from window_tracker import get_active_window_info, get_open_apps
from device_info import get_device_info, format_uptime
from screenshot import take_screenshot
from media_info import get_media_info
from auth import verify_totp, generate_device_token, register_verified_token, is_token_valid, TOKEN_VALID_DAYS
import google_tasks
import mobile_device

app = FastAPI(title="Local Device Status Dashboard", version="0.1.0")

# 允许前端跨域访问（本地开发用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Cookie 名称
AUTH_COOKIE_NAME = "dashboard_auth"


def check_auth(auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME)) -> bool:
    """检查认证状态"""
    return is_token_valid(auth_token) if auth_token else False


class VerifyRequest(BaseModel):
    code: str


class AddTaskRequest(BaseModel):
    title: str
    notes: str = ""
    tasklist_id: str = "@default"


class DeviceUpdateRequest(BaseModel):
    secret: str
    id: str
    show_name: str
    using: bool
    app_name: str = ""


# ========== 认证 ==========

@app.get("/api/auth/status")
def auth_status(auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME)):
    """检查当前认证状态"""
    valid = is_token_valid(auth_token) if auth_token else False
    return {"authenticated": valid}


@app.post("/api/auth/verify")
def auth_verify(req: VerifyRequest, response: Response):
    """验证 TOTP 码"""
    if not verify_totp(req.code):
        raise HTTPException(status_code=401, detail="验证码错误")

    token = generate_device_token()
    register_verified_token(token)

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=TOKEN_VALID_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
    )

    return {"success": True, "message": f"验证成功，有效期 {TOKEN_VALID_DAYS} 天"}


@app.get("/api/health")
def health_check():
    """健康检查接口（无需认证）"""
    return {"status": "ok", "message": "服务运行中"}


# ========== 设备状态 ==========

@app.get("/api/status")
def get_status(auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME)):
    """获取当前设备状态"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    window = get_active_window_info()
    device = get_device_info()
    open_apps = get_open_apps()
    media = get_media_info()

    return {
        "current_app": {
            "process_name": window["process_name"],
            "name": window["app_name"],
            "title": window["title"],
            "pid": window["pid"],
        },
        "open_apps": open_apps,
        "media": media,
        "device": {
            "cpu_percent": device["cpu_percent"],
            "memory_percent": device["memory_percent"],
            "memory_used_gb": device["memory_used_gb"],
            "memory_total_gb": device["memory_total_gb"],
            "uptime_seconds": device["uptime_seconds"],
            "uptime_formatted": format_uptime(device["uptime_seconds"]),
            "disks": device["disks"],
        },
    }


@app.post("/api/screenshot")
def capture_screenshot(auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME)):
    """获取全屏截图"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    result = take_screenshot(save_to_file=False)
    return result


# ========== 移动设备 ==========

@app.post("/device/set")
def device_set(req: DeviceUpdateRequest):
    """接收移动设备状态推送（AutoX.js 兼容）"""
    if not mobile_device.verify_secret(req.secret):
        raise HTTPException(status_code=401, detail="Invalid secret")

    # 解析电量信息（从 app_name 中提取，如 "[85% +] 微信"）
    battery = None
    charging = None
    app_name = req.app_name

    if app_name.startswith("["):
        try:
            bracket_end = app_name.index("]")
            battery_str = app_name[1:bracket_end]
            app_name = app_name[bracket_end + 1:].strip()

            # 解析电量和充电状态
            if "+" in battery_str:
                charging = True
                battery_str = battery_str.replace("+", "").strip()
            else:
                charging = False

            battery = int(battery_str.replace("%", "").strip())
        except (ValueError, IndexError):
            pass

    mobile_device.update_device(
        device_id=req.id,
        show_name=req.show_name,
        using=req.using,
        app_name=app_name,
        battery=battery,
        charging=charging,
    )

    return {"success": True, "message": "Status updated"}


@app.get("/api/devices")
def get_devices(auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME)):
    """获取所有移动设备状态"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    return {"devices": mobile_device.get_devices()}


# ========== Google Tasks ==========

@app.get("/api/todo/connect")
def todo_connect(auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME)):
    """发起 Google OAuth 授权"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    url = google_tasks.get_auth_url()
    return RedirectResponse(url)


@app.get("/api/todo/callback")
def todo_callback(code: str = "", error: str = ""):
    """Google OAuth 回调"""
    if error:
        return FileResponse(FRONTEND_DIR / "index.html")

    if code:
        google_tasks.handle_callback(code)

    return RedirectResponse("/")


@app.get("/api/todo/status")
def todo_status(auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME)):
    """检查 Google Tasks 连接状态"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    return {"connected": google_tasks.is_connected()}


@app.get("/api/todo/lists")
def todo_lists(auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME)):
    """获取所有任务列表"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    if not google_tasks.is_connected():
        raise HTTPException(status_code=400, detail="未连接 Google Tasks")

    return {"lists": google_tasks.get_task_lists()}


@app.get("/api/todo/tasks")
def todo_tasks(
    tasklist_id: str = "@default",
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """获取任务列表"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    if not google_tasks.is_connected():
        raise HTTPException(status_code=400, detail="未连接 Google Tasks")

    return {"tasks": google_tasks.get_tasks(tasklist_id)}


@app.post("/api/todo/tasks")
def todo_add_task(
    req: AddTaskRequest,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """添加任务"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    if not google_tasks.is_connected():
        raise HTTPException(status_code=400, detail="未连接 Google Tasks")

    result = google_tasks.add_task(req.title, req.notes, req.tasklist_id)
    if not result:
        raise HTTPException(status_code=500, detail="添加失败")

    return {"task": result}


@app.post("/api/todo/tasks/{task_id}/complete")
def todo_complete_task(
    task_id: str,
    tasklist_id: str = "@default",
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """完成任务"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    if not google_tasks.is_connected():
        raise HTTPException(status_code=400, detail="未连接 Google Tasks")

    google_tasks.complete_task(task_id, tasklist_id)
    return {"success": True}


@app.delete("/api/todo/tasks/{task_id}")
def todo_delete_task(
    task_id: str,
    tasklist_id: str = "@default",
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """删除任务"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    if not google_tasks.is_connected():
        raise HTTPException(status_code=400, detail="未连接 Google Tasks")

    google_tasks.delete_task(task_id, tasklist_id)
    return {"success": True}


# ========== 静态文件 & 首页 ==========

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_index():
    """返回前端首页"""
    return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
