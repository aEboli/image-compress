"""
图片压缩引擎 — 支持多格式、尺寸调整、主色补白、二分质量搜索、直接质量控制
"""
import os
import io
import shutil
from PIL import Image
from utils import resize_with_padding, get_unique_filename, format_size

# 支持的图片扩展名
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif", ".gif"}

# 格式 → 扩展名映射
FORMAT_EXT_MAP = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "GIF": ".gif",
}

# 支持质量参数的格式
QUALITY_FORMATS = {"JPEG", "WEBP"}


class CompressResult:
    """压缩结果数据类"""
    __slots__ = ("status", "detail", "original_size", "output_size", "output_path")

    def __init__(self, status: str, detail: str = "",
                 original_size: int = 0, output_size: int = 0,
                 output_path: str = ""):
        self.status = status          # SUCCESS / SKIPPED / SKIPPED_COPIED / ERROR
        self.detail = detail
        self.original_size = original_size
        self.output_size = output_size
        self.output_path = output_path


class Compressor:
    """图片压缩器"""

    def __init__(self):
        self.stop_requested = False

    def request_stop(self):
        """安全请求中断压缩"""
        self.stop_requested = True

    def reset(self):
        """重置停止标志"""
        self.stop_requested = False

    # ── 文件夹扫描 ────────────────────────────────────────────

    @staticmethod
    def scan_folder(folder_path: str, recursive: bool = True) -> list[str]:
        """扫描文件夹获取所有图片路径"""
        images = []
        if recursive:
            for root, _, files in os.walk(folder_path):
                for f in files:
                    if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                        images.append(os.path.join(root, f))
        else:
            for f in os.listdir(folder_path):
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                    images.append(os.path.join(folder_path, f))
        return images

    # ── 单张图片压缩 ──────────────────────────────────────────

    def compress_image(
        self,
        input_path: str,
        output_folder: str,
        target_size_mb: float,
        min_size_mb: float = 0,
        output_format: str = "Original",
        renaming_rules: dict | None = None,
        resize_options: dict | None = None,
        quality: int | None = None,
    ) -> CompressResult:
        """
        压缩单张图片。

        Args:
            quality: 直接指定质量(1-100)。若为 None 则使用二分搜索(有目标大小时)或默认85。

        Returns:
            CompressResult 对象
        """
        if renaming_rules is None:
            renaming_rules = {}
        if resize_options is None:
            resize_options = {}

        prefix = renaming_rules.get("prefix", "")
        suffix = renaming_rules.get("suffix", "")
        rename_skipped = renaming_rules.get("rename_skipped", False)

        # 默认前缀逻辑：前缀和后缀都为空时使用 "__"
        if not prefix and not suffix:
            prefix = "__"

        try:
            original_size = os.path.getsize(input_path)
            file_size_mb = original_size / (1024 * 1024)
            filename = os.path.basename(input_path)
            name, orig_ext = os.path.splitext(filename)

            # ── 跳过小文件 ───────────────────────────────────
            if min_size_mb > 0 and file_size_mb < min_size_mb:
                if rename_skipped:
                    result = self._copy_rename(input_path, output_folder, prefix, suffix)
                    return CompressResult(
                        status=result[0], detail=result[1],
                        original_size=original_size, output_size=original_size,
                        output_path=result[1] if result[0] == "SKIPPED_COPIED" else input_path,
                    )
                return CompressResult(
                    status="SKIPPED", detail=input_path,
                    original_size=original_size, output_size=original_size,
                )

            # ── 打开图片 ─────────────────────────────────────
            img = Image.open(input_path)

            # ── 尺寸调整 ─────────────────────────────────────
            if resize_options.get("enabled"):
                try:
                    tw = int(resize_options.get("width", 0))
                    th = int(resize_options.get("height", 0))
                    if tw > 0 and th > 0:
                        img = resize_with_padding(img, tw, th)
                except (ValueError, TypeError):
                    pass

            # ── 确定输出格式和扩展名 ─────────────────────────
            save_format = img.format or "JPEG"
            ext = orig_ext

            if output_format != "Original":
                save_format = output_format
                ext = FORMAT_EXT_MAP.get(output_format, orig_ext)

            # JPEG 不支持 RGBA
            if save_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            elif save_format == "BMP" and img.mode == "RGBA":
                img = img.convert("RGB")

            # GIF 动画处理
            if save_format == "GIF":
                is_animated = getattr(img, "is_animated", False)
            else:
                is_animated = False

            # ── 构建输出路径 ─────────────────────────────────
            new_filename = f"{prefix}{name}{suffix}{ext}"
            output_path = os.path.join(output_folder, new_filename)

            os.makedirs(output_folder, exist_ok=True)

            # 避免覆盖源文件
            if os.path.normpath(input_path) == os.path.normpath(output_path):
                output_path = get_unique_filename(output_path)

            # ── 压缩 ────────────────────────────────────────
            target_bytes = target_size_mb * 1024 * 1024

            if save_format in QUALITY_FORMATS:
                if quality is not None and target_bytes <= 0:
                    # 用户直接指定质量，不使用二分搜索
                    q = max(1, min(100, quality))
                    img.save(output_path, format=save_format, quality=q, optimize=True)
                elif target_bytes > 0:
                    # 有目标大小时使用二分搜索
                    q = self._binary_search_quality(img, save_format, target_bytes)
                    img.save(output_path, format=save_format, quality=q, optimize=True)
                else:
                    # 无目标大小也无指定质量
                    q = quality if quality else 85
                    img.save(output_path, format=save_format, quality=q, optimize=True)
            elif save_format == "PNG":
                img.save(output_path, format="PNG", optimize=True)
            elif save_format == "GIF" and is_animated:
                # 保存 GIF 动画
                frames = []
                try:
                    for frame_idx in range(img.n_frames):
                        img.seek(frame_idx)
                        frames.append(img.copy())
                    frames[0].save(
                        output_path, format="GIF", save_all=True,
                        append_images=frames[1:], loop=0,
                        duration=img.info.get("duration", 100),
                    )
                except Exception:
                    img.save(output_path, format=save_format)
            else:
                img.save(output_path, format=save_format)

            output_size = os.path.getsize(output_path)
            return CompressResult(
                status="SUCCESS",
                detail=f"{format_size(output_size)}",
                original_size=original_size,
                output_size=output_size,
                output_path=output_path,
            )

        except Exception as e:
            return CompressResult(status="ERROR", detail=str(e))

    # ── 二分搜索最优压缩质量 ──────────────────────────────────

    @staticmethod
    def _binary_search_quality(
        img: Image.Image, fmt: str, target_bytes: int
    ) -> int:
        low, high = 5, 95
        best_quality = 85

        while low <= high:
            mid = (low + high) // 2
            buf = io.BytesIO()
            img.save(buf, format=fmt, quality=mid, optimize=True)
            size = buf.tell()

            if size <= target_bytes:
                best_quality = mid
                low = mid + 1
            else:
                high = mid - 1

        return best_quality

    # ── 复制并重命名（用于跳过的文件） ────────────────────────

    @staticmethod
    def _copy_rename(
        input_path: str, output_folder: str, prefix: str, suffix: str
    ) -> tuple[str, str]:
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        new_filename = f"{prefix}{name}{suffix}{ext}"
        output_path = os.path.join(output_folder, new_filename)

        os.makedirs(output_folder, exist_ok=True)

        if os.path.normpath(input_path) == os.path.normpath(output_path):
            return "SKIPPED", input_path

        output_path = get_unique_filename(output_path)
        shutil.copy2(input_path, output_path)
        return "SKIPPED_COPIED", output_path
