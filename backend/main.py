"""
Local Device Status Dashboard - Backend
"""
from contextlib import asynccontextmanager
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
import local_todo
import mobile_device


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：启动提醒检查器
    local_todo.start_reminder_checker()
    yield
    # 关闭时：停止提醒检查器
    local_todo.stop_reminder_checker()


app = FastAPI(title="Local Device Status Dashboard", version="0.1.0", lifespan=lifespan)

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
    parent_id: Optional[str] = None
    important: bool = False
    remind: Optional[dict] = None
    remind_tag: Optional[str] = None
    notes: str = ""


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    important: Optional[bool] = None
    remind: Optional[dict] = None
    remind_tag: Optional[str] = None


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


# ========== 本地 TODO ==========

@app.get("/api/todo/tasks")
def todo_tasks(
    include_completed: bool = False,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """获取所有 TODO"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    return {"tasks": local_todo.get_todos(include_completed)}


@app.post("/api/todo/tasks")
def todo_add_task(
    req: AddTaskRequest,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """添加 TODO"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    todo = local_todo.add_todo(
        title=req.title,
        parent_id=req.parent_id,
        important=req.important,
        remind=req.remind,
        remind_tag=req.remind_tag,
        notes=req.notes,
    )
    return {"task": todo}


@app.get("/api/todo/tasks/{task_id}")
def todo_get_task(
    task_id: str,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """获取单个 TODO"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    todo = local_todo.get_todo(task_id)
    if not todo:
        raise HTTPException(status_code=404, detail="TODO 不存在")

    return {"task": todo}


@app.patch("/api/todo/tasks/{task_id}")
def todo_update_task(
    task_id: str,
    req: UpdateTaskRequest,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """更新 TODO"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    updates = req.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="无更新内容")

    todo = local_todo.update_todo(task_id, **updates)
    if not todo:
        raise HTTPException(status_code=404, detail="TODO 不存在")

    return {"task": todo}


@app.post("/api/todo/tasks/{task_id}/complete")
def todo_complete_task(
    task_id: str,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """完成 TODO"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    if not local_todo.complete_todo(task_id):
        raise HTTPException(status_code=404, detail="TODO 不存在")

    return {"success": True}


@app.post("/api/todo/tasks/{task_id}/toggle-important")
def todo_toggle_important(
    task_id: str,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """切换重要状态"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    todo = local_todo.toggle_important(task_id)
    if not todo:
        raise HTTPException(status_code=404, detail="TODO 不存在")

    return {"task": todo}


@app.delete("/api/todo/tasks/{task_id}")
def todo_delete_task(
    task_id: str,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
):
    """删除 TODO"""
    if not check_auth(auth_token):
        raise HTTPException(status_code=401, detail="未认证")

    if not local_todo.delete_todo(task_id):
        raise HTTPException(status_code=404, detail="TODO 不存在")

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
