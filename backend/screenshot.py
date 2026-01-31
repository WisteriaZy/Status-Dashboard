"""
全屏截图功能
"""
import io
import base64
from datetime import datetime
from pathlib import Path
from PIL import ImageGrab


# 截图保存目录
SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"


def take_screenshot(save_to_file: bool = False) -> dict:
    """
    获取全屏截图

    Args:
        save_to_file: 是否保存到文件

    Returns:
        {
            "success": True,
            "timestamp": "2024-01-01 12:00:00",
            "base64": "data:image/png;base64,...",
            "file_path": "screenshots/xxx.png" (如果保存了文件)
        }
    """
    try:
        # 截图
        img = ImageGrab.grab()
        timestamp = datetime.now()

        # 转换为 base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

        result = {
            "success": True,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "base64": f"data:image/png;base64,{b64_data}",
            "width": img.width,
            "height": img.height,
        }

        # 保存到文件（可选）
        if save_to_file:
            SCREENSHOTS_DIR.mkdir(exist_ok=True)
            filename = timestamp.strftime("%Y%m%d_%H%M%S") + ".png"
            file_path = SCREENSHOTS_DIR / filename
            img.save(file_path, "PNG")
            result["file_path"] = str(file_path)

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


if __name__ == "__main__":
    result = take_screenshot(save_to_file=True)
    if result["success"]:
        print(f"截图成功: {result['width']}x{result['height']}")
        if "file_path" in result:
            print(f"保存到: {result['file_path']}")
    else:
        print(f"截图失败: {result['error']}")
