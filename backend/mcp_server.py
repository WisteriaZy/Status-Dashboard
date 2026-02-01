"""
MCP Server for Dashboard TODO 系统
让 AstrBot 的 LLM 通过 MCP 协议来管理任务

使用 Streamable HTTP 传输模式，监听端口 8001
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional
import local_todo

# 创建 MCP Server
mcp = FastMCP(
    name="dashboard-todo",
    instructions="Dashboard TODO 任务管理。可以创建、查看、完成、删除任务，支持设置提醒。",
    host="0.0.0.0",
    port=8002,
    stateless_http=True,
)


@mcp.tool()
def list_tasks(include_completed: bool = False) -> list[dict]:
    """
    列出所有任务

    Args:
        include_completed: 是否包含已完成的任务，默认 False

    Returns:
        任务列表，每个任务包含 id, title, notes, completed, important, remind 等字段
    """
    todos = local_todo.get_todos(include_completed=include_completed)
    # 简化返回，只保留关键字段
    result = []
    for t in todos:
        result.append({
            "id": t["id"],
            "title": t["title"],
            "notes": t.get("notes", ""),
            "completed": t.get("completed", False),
            "important": t.get("important", False),
            "remind": t.get("remind"),
            "remind_tag": t.get("remind_tag"),
            "created_at": t.get("created_at"),
        })
    return result


@mcp.tool()
def add_task(
    title: str,
    important: bool = False,
    notes: str = "",
    remind: Optional[dict] = None,
    remind_tag: str = "私人"
) -> dict:
    """
    创建新任务

    Args:
        title: 任务标题
        important: 是否重要，默认 False
        notes: 备注内容
        remind: 提醒配置，支持以下格式：
            - {"type": "once", "at": "2026-01-31T14:30"} 一次性提醒
            - {"type": "daily", "hours": [9, 14, 18]} 每天在指定小时提醒
            - {"type": "weekly", "weekdays": [1, 3, 5], "hour": 9} 每周指定天的指定小时提醒（1=周一, 7=周日）
            - {"type": "monthly", "days": [1, 15], "hour": 9} 每月指定日期的指定小时提醒
        remind_tag: 提醒发送目标 tag，默认 "私人"

    Returns:
        创建的任务信息
    """
    todo = local_todo.add_todo(
        title=title,
        important=important,
        notes=notes,
        remind=remind,
        remind_tag=remind_tag,
    )
    return {
        "id": todo["id"],
        "title": todo["title"],
        "notes": todo.get("notes", ""),
        "important": todo.get("important", False),
        "remind": todo.get("remind"),
        "remind_tag": todo.get("remind_tag"),
        "created_at": todo.get("created_at"),
    }


@mcp.tool()
def complete_task(task_id: str) -> dict:
    """
    完成指定任务

    Args:
        task_id: 任务 ID

    Returns:
        操作结果，包含 success 和 message 字段
    """
    success = local_todo.complete_todo(task_id)
    if success:
        return {"success": True, "message": f"任务 {task_id} 已完成"}
    else:
        return {"success": False, "message": f"未找到任务 {task_id}"}


@mcp.tool()
def delete_task(task_id: str) -> dict:
    """
    删除指定任务

    Args:
        task_id: 任务 ID

    Returns:
        操作结果，包含 success 和 message 字段
    """
    success = local_todo.delete_todo(task_id)
    if success:
        return {"success": True, "message": f"任务 {task_id} 已删除"}
    else:
        return {"success": False, "message": f"未找到任务 {task_id}"}


@mcp.tool()
def update_task(
    task_id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    important: Optional[bool] = None,
    remind: Optional[dict] = None,
    remind_tag: Optional[str] = None
) -> dict:
    """
    更新指定任务的信息

    Args:
        task_id: 任务 ID
        title: 新标题（可选）
        notes: 新备注（可选）
        important: 是否重要（可选）
        remind: 新提醒配置（可选），格式同 add_task
        remind_tag: 新提醒目标 tag（可选）

    Returns:
        更新后的任务信息，或错误信息
    """
    # 构建更新参数
    kwargs = {}
    if title is not None:
        kwargs["title"] = title
    if notes is not None:
        kwargs["notes"] = notes
    if important is not None:
        kwargs["important"] = important
    if remind is not None:
        kwargs["remind"] = remind
    if remind_tag is not None:
        kwargs["remind_tag"] = remind_tag

    if not kwargs:
        return {"success": False, "message": "没有提供要更新的字段"}

    todo = local_todo.update_todo(task_id, **kwargs)
    if todo:
        return {
            "success": True,
            "task": {
                "id": todo["id"],
                "title": todo["title"],
                "notes": todo.get("notes", ""),
                "important": todo.get("important", False),
                "remind": todo.get("remind"),
                "remind_tag": todo.get("remind_tag"),
            }
        }
    else:
        return {"success": False, "message": f"未找到任务 {task_id}"}


if __name__ == "__main__":
    print("=" * 50)
    print("Dashboard TODO MCP Server")
    print("=" * 50)
    print("传输模式: Streamable HTTP")
    print("端口: 8002")
    print("MCP 端点: http://localhost:8002/mcp")
    print("=" * 50)

    # 使用 streamable-http 模式启动
    mcp.run(transport="streamable-http")
