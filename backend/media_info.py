"""
SMTC (System Media Transport Controls) 媒体信息获取
"""
import asyncio
from typing import Optional

try:
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        GlobalSystemMediaTransportControlsSession as Session,
    )
    from winsdk.windows.storage.streams import DataReader, IRandomAccessStreamReference
    WINSDK_AVAILABLE = True
except ImportError:
    WINSDK_AVAILABLE = False


# 目标应用（只读取这个应用的媒体信息）
TARGET_APP_ID = "splayer"


async def _get_thumbnail_base64(thumbnail_ref: IRandomAccessStreamReference) -> Optional[str]:
    """获取缩略图并转换为 base64"""
    try:
        import base64
        stream = await thumbnail_ref.open_read_async()
        size = stream.size
        reader = DataReader(stream)
        await reader.load_async(size)
        buffer = reader.read_buffer(size)
        # 转换为 bytes
        data = bytes(buffer)
        return f"data:image/png;base64,{base64.b64encode(data).decode()}"
    except Exception:
        return None


async def _get_media_info_async() -> dict:
    """异步获取媒体信息"""
    if not WINSDK_AVAILABLE:
        return {"available": False, "error": "winsdk 未安装"}

    try:
        manager = await SessionManager.request_async()
        sessions = manager.get_sessions()

        # 遍历所有会话，找到目标应用
        for session in sessions:
            app_id = session.source_app_user_model_id or ""

            # 检查是否是目标应用
            if TARGET_APP_ID.lower() not in app_id.lower():
                continue

            # 获取媒体属性
            info = await session.try_get_media_properties_async()
            if not info:
                continue

            # 获取播放状态
            playback = session.get_playback_info()
            status_map = {
                0: "closed",
                1: "opened",
                2: "changing",
                3: "stopped",
                4: "playing",
                5: "paused",
            }
            playback_status = status_map.get(playback.playback_status, "unknown")

            # 获取封面图
            thumbnail = None
            if info.thumbnail:
                thumbnail = await _get_thumbnail_base64(info.thumbnail)

            return {
                "available": True,
                "app_id": app_id,
                "title": info.title or "",
                "artist": info.artist or "",
                "album": info.album_title or "",
                "album_artist": info.album_artist or "",
                "track_number": info.track_number,
                "playback_status": playback_status,
                "thumbnail": thumbnail,
            }

        # 未找到目标应用的会话
        return {
            "available": False,
            "error": f"未找到 {TARGET_APP_ID} 的媒体会话",
        }

    except Exception as e:
        return {
            "available": False,
            "error": str(e),
        }


def get_media_info() -> dict:
    """同步包装器：获取媒体信息"""
    return asyncio.run(_get_media_info_async())


if __name__ == "__main__":
    info = get_media_info()
    if info["available"]:
        print(f"正在播放: {info['title']}")
        print(f"艺术家: {info['artist']}")
        print(f"专辑: {info['album']}")
        print(f"状态: {info['playback_status']}")
        print(f"封面: {'有' if info['thumbnail'] else '无'}")
    else:
        print(f"无法获取: {info.get('error', '未知错误')}")
