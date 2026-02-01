"""
QQ Bot 通知模块 (NapCat WebSocket)
"""
import json
import asyncio
import sys
from typing import Optional

import config

# 从配置文件读取
def _get_ws_url() -> str:
    return config.qq_notify.ws_url

def _get_token() -> str:
    return config.qq_notify.token

def _get_targets() -> dict:
    return config.qq_notify.targets


async def _send_message(target_type: str, target_id: int, message: str) -> bool:
    """通过 WebSocket 发送消息"""
    try:
        import websockets

        ws_url = _get_ws_url()
        token = _get_token()

        async with websockets.connect(
            ws_url,
            extra_headers={"Authorization": f"Bearer {token}"} if token else None,
        ) as ws:
            # 短暂等待并丢弃连接后的 lifecycle 事件
            try:
                while True:
                    init_msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    data = json.loads(init_msg)
                    if data.get("post_type") == "meta_event":
                        continue
                    break
            except asyncio.TimeoutError:
                pass  # 没有更多初始消息，继续发送

            if target_type == "private":
                action = "send_private_msg"
                params = {"user_id": target_id, "message": message}
            else:
                action = "send_group_msg"
                params = {"group_id": target_id, "message": message}

            payload = {
                "action": action,
                "params": params,
                "echo": "send_msg",
            }

            await ws.send(json.dumps(payload))

            # 等待 API 响应（跳过推送事件）
            while True:
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                result = json.loads(response)
                if result.get("echo") == "send_msg":
                    return result.get("status") == "ok"

    except asyncio.TimeoutError:
        # 超时但消息可能已发送成功（没收到回执）
        print("[QQ] 等待响应超时")
        return False
    except Exception as e:
        print(f"[QQ] 发送失败: {e}")
        return False


def _run_async(coro):
    """安全运行异步函数（兼容 Windows）"""
    # Windows 上需要使用 WindowsSelectorEventLoopPolicy 或者新创建事件循环
    if sys.platform == 'win32':
        # 如果当前已有运行中的事件循环，创建新循环
        try:
            loop = asyncio.get_running_loop()
            # 在已有循环中运行（如在 FastAPI 上下文中）
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=10)
        except RuntimeError:
            # 没有运行中的循环，直接用 asyncio.run
            return asyncio.run(coro)
    else:
        return asyncio.run(coro)


def send_notify(tag: str, message: str) -> bool:
    """
    发送通知到指定 tag 对应的目标

    Args:
        tag: 目标标签，如 "私人"、"公共"
        message: 消息内容

    Returns:
        是否发送成功
    """
    targets = _get_targets()
    target = targets.get(tag)
    if not target:
        print(f"[QQ] 未知 tag: {tag}")
        return False

    return _run_async(_send_message(target["type"], target["id"], message))


def send_private(user_id: int, message: str) -> bool:
    """直接发送私聊消息"""
    return _run_async(_send_message("private", user_id, message))


def send_group(group_id: int, message: str) -> bool:
    """直接发送群消息"""
    return _run_async(_send_message("group", group_id, message))


if __name__ == "__main__":
    # 测试
    print("发送测试消息...")
    success = send_notify("私人", "这是来自 Dashboard 的测试消息")
    print(f"发送结果: {'成功' if success else '失败'}")
