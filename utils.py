"""
工具函数 — 文件大小格式化、唯一文件名、主色提取、尺寸调整、缩略图生成
"""
import os
import subprocess
import sys
import numpy as np
from PIL import Image
from collections import Counter


def format_size(size_in_bytes: int) -> str:
    """将字节数格式化为人类可读的字符串（如 '1.23 MB'）"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"


def get_unique_filename(filepath: str) -> str:
    """如果文件已存在，添加 _1, _2 ... 后缀使文件名唯一"""
    if not os.path.exists(filepath):
        return filepath
    base, ext = os.path.splitext(filepath)
    counter = 1
    new_path = filepath
    while os.path.exists(new_path):
        new_path = f"{base}_{counter}{ext}"
        counter += 1
    return new_path


def get_dominant_color(image: Image.Image) -> tuple:
    """
    获取图片中占比最高的颜色。
    先将图片缩小到 64x64 进行采样以提高性能，
    然后将颜色量化到 16 级（减少颜色数），统计出现次数最多的颜色。
    """
    small = image.copy()
    small = small.convert("RGB")
    small.thumbnail((64, 64))

    pixels = np.array(small).reshape(-1, 3)

    # 量化到 16 级 (每通道 16 bins → 4096 种颜色)
    quantized = (pixels // 16) * 16 + 8
    pixel_tuples = [tuple(p) for p in quantized]
    counter = Counter(pixel_tuples)
    dominant = counter.most_common(1)[0][0]

    return dominant


def resize_with_padding(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    等比缩放图片到 target_w x target_h，
    如果比例不匹配，用图片主色填充空白区域。
    """
    if target_w <= 0 or target_h <= 0:
        return image

    orig_w, orig_h = image.size
    if orig_w == target_w and orig_h == target_h:
        return image

    rgb_image = image.convert("RGB") if image.mode != "RGB" else image

    ratio = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * ratio)
    new_h = int(orig_h * ratio)

    resized = rgb_image.resize((new_w, new_h), Image.LANCZOS)

    dominant_color = get_dominant_color(rgb_image)

    canvas = Image.new("RGB", (target_w, target_h), dominant_color)

    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))

    if image.mode == "RGBA":
        alpha_canvas = Image.new("RGBA", (target_w, target_h), dominant_color + (255,))
        resized_rgba = image.resize((new_w, new_h), Image.LANCZOS)
        alpha_canvas.paste(resized_rgba, (offset_x, offset_y), resized_rgba)
        return alpha_canvas

    return canvas


def generate_thumbnail(image_path: str, size: int = 48) -> Image.Image | None:
    """
    为文件列表生成缩略图。
    返回 PIL Image 对象或 None（文件无法读取时）。
    """
    try:
        img = Image.open(image_path)
        img.thumbnail((size, size), Image.LANCZOS)
        # 确保有 alpha 通道以支持透明背景
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        return img
    except Exception:
        return None


def open_folder_in_explorer(folder_path: str):
    """跨平台打开文件夹"""
    try:
        folder_path = os.path.normpath(folder_path)
        if sys.platform == "win32":
            os.startfile(folder_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
    except Exception:
        pass


def calc_compression_ratio(original_bytes: int, compressed_bytes: int) -> str:
    """计算压缩率，返回人类可读的字符串"""
    if original_bytes <= 0:
        return "N/A"
    ratio = (1 - compressed_bytes / original_bytes) * 100
    if ratio < 0:
        return f"+{abs(ratio):.1f}%"
    return f"-{ratio:.1f}%"
