"""
图片压缩工具 — 主界面 v2.0
基于 CustomTkinter，简体中文界面，精美 UI，功能完备的图片压缩桌面应用。
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import threading
import time
import subprocess
import sys

from compressor import Compressor, IMAGE_EXTENSIONS
from utils import format_size, generate_thumbnail, open_folder_in_explorer, calc_compression_ratio
from settings_manager import SettingsManager

# ── 常量 ─────────────────────────────────────────────────────
EXPORT_FORMATS = ["Original", "JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF"]
MIN_WIN_W, MIN_WIN_H = 960, 640
FILE_DISPLAY_LIMIT = 500

# 尝试加载自定义主题
_theme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "haze_theme.json")


class ImageCompressorApp(ctk.CTk):
    """图片压缩工具 v2.0 — 精美 UI"""

    def __init__(self):
        super().__init__()

        # ── 设置管理 ─────────────────────────────────────────
        self.settings_mgr = SettingsManager()
        s = self.settings_mgr.settings

        # ── 外观 ─────────────────────────────────────────────
        theme = s.get("theme_mode", "Dark")
        ctk.set_appearance_mode(theme)
        if os.path.exists(_theme_path):
            ctk.set_default_color_theme(_theme_path)
        else:
            ctk.set_default_color_theme("blue")

        # ── 窗口基本属性 ─────────────────────────────────────
        self.title("🖼 图片压缩工具 v2.0")
        self.geometry(s.get("geometry", "1050x720"))
        self.minsize(MIN_WIN_W, MIN_WIN_H)

        # 恢复窗口位置
        wx = s.get("window_x")
        wy = s.get("window_y")
        if wx is not None and wy is not None:
            try:
                self.geometry(f"+{int(wx)}+{int(wy)}")
            except Exception:
                pass

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # ── 数据 ─────────────────────────────────────────────
        self.compressor = Compressor()
        self.selected_files: list[str] = []
        self._selected_set: set[str] = set()
        self.processing = False
        self._thumbnail_cache: dict[str, ImageTk.PhotoImage] = {}
        self._file_widgets: list[ctk.CTkFrame] = []

        # ── 布局 ─────────────────────────────────────────────
        self.grid_columnconfigure(0, weight=0)  # 侧边栏
        self.grid_columnconfigure(1, weight=1)  # 主区域
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar(s)
        self._build_main_area(s)

    # ══════════════════════════════════════════════════════════
    #  侧边栏
    # ══════════════════════════════════════════════════════════

    def _build_sidebar(self, s: dict):
        sidebar = ctk.CTkScrollableFrame(self, width=250, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)

        # ── 标题区 ────────────────────────────────────────────
        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(12, 0), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="🖼 图片压缩工具",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        # 主题切换
        self.var_theme = tk.StringVar(value=s.get("theme_mode", "Dark"))
        theme_switch = ctk.CTkSegmentedButton(
            header, values=["Light", "Dark"],
            variable=self.var_theme,
            command=self._toggle_theme,
            width=100,
        )
        theme_switch.grid(row=0, column=1, sticky="e", padx=(8, 0))

        ctk.CTkLabel(
            sidebar, text="高效 · 批量 · 智能压缩",
            font=ctk.CTkFont(size=11), text_color="gray",
        ).grid(row=1, column=0, padx=16, pady=(2, 8), sticky="w")

        # ── TabView 设置面板 ──────────────────────────────────
        self.tab_view = ctk.CTkTabview(sidebar, height=460)
        self.tab_view.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="nsew")

        tab_compress = self.tab_view.add("压缩设置")
        tab_advanced = self.tab_view.add("高级选项")

        tab_compress.grid_columnconfigure(0, weight=1)
        tab_advanced.grid_columnconfigure(0, weight=1)

        self._build_compress_tab(tab_compress, s)
        self._build_advanced_tab(tab_advanced, s)

    def _build_compress_tab(self, parent, s: dict):
        """压缩设置标签页"""
        row = 0

        # ── 导出格式 ─────────────────────────────────────────
        self._section_label(parent, "📦 导出格式", row)
        row += 1

        self.var_format = tk.StringVar(value=s.get("output_format", "Original"))
        ctk.CTkOptionMenu(
            parent, values=EXPORT_FORMATS, variable=self.var_format, width=220
        ).grid(row=row, column=0, padx=12, pady=(2, 10), sticky="w")
        row += 1

        # ── 目标大小 ─────────────────────────────────────────
        self._section_label(parent, "🎯 目标大小 (MB)", row)
        row += 1

        hint_frame = ctk.CTkFrame(parent, fg_color="transparent")
        hint_frame.grid(row=row, column=0, padx=12, pady=(0, 0), sticky="ew")
        ctk.CTkLabel(hint_frame, text="设为 0 不限制大小", font=ctk.CTkFont(size=10), text_color="gray").pack(side="left")

        row += 1
        self.var_target = tk.StringVar(value=s.get("target_size", "1.0"))
        ctk.CTkEntry(parent, textvariable=self.var_target, width=220, placeholder_text="例如 1.0").grid(
            row=row, column=0, padx=12, pady=(2, 10), sticky="w"
        )
        row += 1

        # ── JPEG 质量滑块 ────────────────────────────────────
        self._section_label(parent, "🔧 压缩质量（仅 JPEG / WEBP）", row)
        row += 1

        quality_frame = ctk.CTkFrame(parent, fg_color="transparent")
        quality_frame.grid(row=row, column=0, padx=12, pady=(2, 4), sticky="ew")
        quality_frame.grid_columnconfigure(0, weight=1)

        self.var_quality = tk.IntVar(value=s.get("quality_slider", 85))
        self.quality_slider = ctk.CTkSlider(
            quality_frame, from_=1, to=100, number_of_steps=99,
            variable=self.var_quality, command=self._on_quality_change,
            width=170,
        )
        self.quality_slider.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.lbl_quality = ctk.CTkLabel(
            quality_frame, text=f"{self.var_quality.get()}%",
            font=ctk.CTkFont(size=13, weight="bold"), width=45,
        )
        self.lbl_quality.grid(row=0, column=1, sticky="e")
        row += 1

        ctk.CTkLabel(parent, text="目标大小 > 0 时将优先使用目标大小", font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, padx=12, pady=(0, 10), sticky="w"
        )
        row += 1

        # ── 忽略小文件 ───────────────────────────────────────
        self._section_label(parent, "⏭ 忽略小于 (MB)", row)
        row += 1

        ctk.CTkLabel(parent, text="设为 0 不忽略", font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=row, column=0, padx=12, pady=(0, 0), sticky="w"
        )
        row += 1

        self.var_min = tk.StringVar(value=s.get("min_size", "0.1"))
        ctk.CTkEntry(parent, textvariable=self.var_min, width=220, placeholder_text="例如 0.1").grid(
            row=row, column=0, padx=12, pady=(2, 10), sticky="w"
        )

    def _build_advanced_tab(self, parent, s: dict):
        """高级选项标签页"""
        row = 0

        # ── 重命名规则 ───────────────────────────────────────
        self._section_label(parent, "✏️ 重命名规则", row)
        row += 1

        ctk.CTkLabel(parent, text="前缀 (留空默认 __)", font=ctk.CTkFont(size=11)).grid(
            row=row, column=0, padx=12, pady=(2, 0), sticky="w"
        )
        row += 1
        self.var_prefix = tk.StringVar(value=s.get("prefix", ""))
        ctk.CTkEntry(parent, textvariable=self.var_prefix, width=220, placeholder_text="例如 compressed_").grid(
            row=row, column=0, padx=12, pady=(2, 4), sticky="w"
        )
        row += 1

        ctk.CTkLabel(parent, text="后缀 (可选)", font=ctk.CTkFont(size=11)).grid(
            row=row, column=0, padx=12, pady=(2, 0), sticky="w"
        )
        row += 1
        self.var_suffix = tk.StringVar(value=s.get("suffix", ""))
        ctk.CTkEntry(parent, textvariable=self.var_suffix, width=220, placeholder_text="例如 _small").grid(
            row=row, column=0, padx=12, pady=(2, 6), sticky="w"
        )
        row += 1

        self.var_rename_skip = tk.BooleanVar(value=s.get("rename_skipped", False))
        ctk.CTkCheckBox(parent, text="未压缩文件也重命名", variable=self.var_rename_skip).grid(
            row=row, column=0, padx=12, pady=(2, 12), sticky="w"
        )
        row += 1

        # ── 尺寸调整 ────────────────────────────────────────
        self._section_label(parent, "📐 尺寸调整", row)
        row += 1

        self.var_resize = tk.BooleanVar(value=s.get("resize_enabled", False))
        ctk.CTkCheckBox(
            parent, text="启用尺寸调整", variable=self.var_resize,
            command=self._toggle_resize,
        ).grid(row=row, column=0, padx=12, pady=(2, 4), sticky="w")
        row += 1

        self.resize_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.resize_frame.grid(row=row, column=0, padx=12, pady=(0, 4), sticky="ew")

        ctk.CTkLabel(self.resize_frame, text="宽", font=ctk.CTkFont(size=11)).pack(side="left")
        self.var_rw = tk.StringVar(value=s.get("resize_width", "800"))
        ctk.CTkEntry(self.resize_frame, textvariable=self.var_rw, width=65).pack(side="left", padx=4)
        ctk.CTkLabel(self.resize_frame, text="×  高", font=ctk.CTkFont(size=11)).pack(side="left")
        self.var_rh = tk.StringVar(value=s.get("resize_height", "600"))
        ctk.CTkEntry(self.resize_frame, textvariable=self.var_rh, width=65).pack(side="left", padx=4)
        row += 1

        ctk.CTkLabel(
            parent, text="不符合比例时用图片主色填充",
            font=ctk.CTkFont(size=10), text_color="gray",
        ).grid(row=row, column=0, padx=12, pady=(0, 12), sticky="w")
        row += 1

        self._toggle_resize()

        # ── 导出路径 ─────────────────────────────────────────
        self._section_label(parent, "📂 导出路径", row)
        row += 1

        self.var_custom_out = tk.BooleanVar(value=s.get("custom_output_enabled", False))
        ctk.CTkCheckBox(
            parent, text="自定义导出文件夹", variable=self.var_custom_out,
            command=self._toggle_output,
        ).grid(row=row, column=0, padx=12, pady=(2, 4), sticky="w")
        row += 1

        self.custom_output_path = s.get("custom_output_path", "")
        self.lbl_out_path = ctk.CTkLabel(
            parent, text=self._output_display_text(), wraplength=210,
            font=ctk.CTkFont(size=10), text_color="gray",
        )
        self.lbl_out_path.grid(row=row, column=0, padx=12, pady=(0, 8), sticky="w")
        row += 1

        # ── 完成后选项 ───────────────────────────────────────
        self._section_label(parent, "✅ 完成后操作", row)
        row += 1

        self.var_auto_open = tk.BooleanVar(value=s.get("auto_open_folder", True))
        ctk.CTkCheckBox(parent, text="压缩完成后打开文件夹", variable=self.var_auto_open).grid(
            row=row, column=0, padx=12, pady=(2, 8), sticky="w"
        )

    @staticmethod
    def _section_label(parent, text: str, row: int):
        """生成分区标签"""
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=row, column=0, padx=12, pady=(8, 2), sticky="w")

    # ══════════════════════════════════════════════════════════
    #  主区域
    # ══════════════════════════════════════════════════════════

    def _build_main_area(self, s: dict):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        main.grid_rowconfigure(2, weight=3)   # 文件列表
        main.grid_rowconfigure(3, weight=2)   # 日志面板
        main.grid_columnconfigure(0, weight=1)

        # ── 操作按钮栏 ───────────────────────────────────────
        btn_bar = ctk.CTkFrame(main, fg_color="transparent")
        btn_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        btn_bar.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(
            btn_bar, text="📁 添加图片", width=120, height=36,
            font=ctk.CTkFont(size=13),
            command=self._add_files,
        ).grid(row=0, column=0, padx=(0, 6))

        ctk.CTkButton(
            btn_bar, text="📂 添加文件夹", width=130, height=36,
            font=ctk.CTkFont(size=13),
            command=self._add_folder,
        ).grid(row=0, column=1, padx=(0, 6))

        ctk.CTkButton(
            btn_bar, text="🗑 清空列表", width=110, height=36,
            fg_color="transparent", border_width=2,
            text_color=("gray10", "#DCE4EE"),
            font=ctk.CTkFont(size=13),
            command=self._clear_list,
        ).grid(row=0, column=2, padx=(0, 6))

        # 拖拽提示
        ctk.CTkLabel(
            btn_bar, text="💡 也可拖拽文件到列表",
            font=ctk.CTkFont(size=10), text_color="gray",
        ).grid(row=0, column=3, sticky="e", padx=(0, 4))

        # ── 统计信息栏 ───────────────────────────────────────
        info_bar = ctk.CTkFrame(main, corner_radius=8, height=36)
        info_bar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        info_bar.grid_columnconfigure(1, weight=1)

        self.lbl_count = ctk.CTkLabel(
            info_bar, text="  📊 已选择: 0 张图片",
            anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.lbl_count.grid(row=0, column=0, padx=(10, 0), pady=6, sticky="w")

        self.lbl_total_size = ctk.CTkLabel(
            info_bar, text="总大小: 0 B", anchor="center",
            font=ctk.CTkFont(size=11), text_color="gray",
        )
        self.lbl_total_size.grid(row=0, column=1, padx=8, pady=6)

        self.lbl_folder_hint = ctk.CTkLabel(
            info_bar, text="", anchor="e", text_color="gray",
            font=ctk.CTkFont(size=10),
        )
        self.lbl_folder_hint.grid(row=0, column=2, padx=(0, 10), pady=6, sticky="e")

        # ── 文件列表 ─────────────────────────────────────────
        self.file_list = ctk.CTkScrollableFrame(main, label_text="📋 待处理文件")
        self.file_list.grid(row=2, column=0, sticky="nsew", pady=(0, 6))
        self.file_list.grid_columnconfigure(0, weight=1)

        # 绑定拖拽（简易方案：绑定drop事件如果tkinterdnd2可用）
        self._setup_dnd()

        # 空状态引导
        self.lbl_empty = ctk.CTkLabel(
            self.file_list,
            text="✨ 点击上方按钮添加图片或文件夹\n支持 JPG / PNG / WEBP / BMP / TIFF / GIF\n\n也可以直接拖拽文件到此区域",
            font=ctk.CTkFont(size=13), text_color="gray",
        )
        self.lbl_empty.pack(pady=50)

        # ── 日志面板 ─────────────────────────────────────────
        log_frame = ctk.CTkFrame(main)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 6))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.grid(row=0, column=0, padx=10, pady=(6, 2), sticky="ew")
        log_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(log_header, text="📝 处理日志", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )

        self.lbl_stats = ctk.CTkLabel(
            log_header, text="", anchor="e",
            font=ctk.CTkFont(size=10), text_color="gray",
        )
        self.lbl_stats.grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(log_frame, height=100, state="disabled", wrap="word")
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        # ── 底部操作区 ───────────────────────────────────────
        bottom = ctk.CTkFrame(main, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        # 进度条 + 百分比
        progress_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        progress_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(progress_frame)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.progress.set(0)

        self.lbl_percent = ctk.CTkLabel(
            progress_frame, text="0%", width=50,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.lbl_percent.grid(row=0, column=1)

        # 状态文本 + 按钮
        self.lbl_status = ctk.CTkLabel(bottom, text="✨ 就绪", anchor="w", font=ctk.CTkFont(size=12))
        self.lbl_status.grid(row=1, column=0, sticky="w")

        self.btn_cancel = ctk.CTkButton(
            bottom, text="⏹ 取消", height=40, width=100,
            fg_color="#e74c3c", hover_color="#c0392b",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._cancel_compression,
        )
        # 取消按钮初始隐藏
        self.btn_cancel.grid(row=1, column=1, sticky="e", padx=(0, 8))
        self.btn_cancel.grid_remove()

        self.btn_start = ctk.CTkButton(
            bottom, text="▶ 开始压缩", height=40, width=140,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_compression,
        )
        self.btn_start.grid(row=1, column=2, sticky="e")

    # ══════════════════════════════════════════════════════════
    #  拖拽支持
    # ══════════════════════════════════════════════════════════

    def _setup_dnd(self):
        """尝试设置拖拽支持（tkinterdnd2 需要特殊基类，可能不可用）"""
        try:
            from tkinterdnd2 import DND_FILES
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_dnd_drop)
        except Exception:
            # tkinterdnd2 不可用或者不兼容 customtkinter，跳过拖拽功能
            pass

    def _on_dnd_drop(self, event):
        """处理拖拽放下事件"""
        try:
            # 解析文件路径（可能有大括号包裹或空格分隔）
            data = event.data
            if data.startswith("{"):
                paths = []
                while "{" in data:
                    start = data.index("{")
                    end = data.index("}")
                    paths.append(data[start + 1:end])
                    data = data[end + 1:].strip()
                if data:
                    paths.extend(data.split())
            else:
                paths = data.split()

            all_images = []
            for p in paths:
                p = p.strip()
                if os.path.isdir(p):
                    all_images.extend(Compressor.scan_folder(p, recursive=True))
                    self.lbl_folder_hint.configure(text=f"来源: {p}")
                elif os.path.isfile(p) and os.path.splitext(p)[1].lower() in IMAGE_EXTENSIONS:
                    all_images.append(p)

            if all_images:
                self._add_to_list(all_images)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════
    #  文件选择
    # ══════════════════════════════════════════════════════════

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.tif *.gif")],
        )
        if files:
            self._add_to_list(files)

    def _add_folder(self):
        folder = filedialog.askdirectory(title="选择文件夹（自动递归扫描）")
        if folder:
            images = Compressor.scan_folder(folder, recursive=True)
            self._add_to_list(images)
            self.lbl_folder_hint.configure(text=f"来源: {folder}")

            # 记录最近文件夹
            last = self.settings_mgr.settings.get("last_folders", [])
            if folder not in last:
                last.insert(0, folder)
                last = last[:5]
                self.settings_mgr.settings["last_folders"] = last

    def _add_to_list(self, paths):
        added = 0
        for p in paths:
            norm = os.path.normpath(p)
            if norm not in self._selected_set:
                self._selected_set.add(norm)
                self.selected_files.append(norm)
                added += 1

        if added > 0:
            self._refresh_file_display()

    def _clear_list(self):
        self.selected_files.clear()
        self._selected_set.clear()
        self._thumbnail_cache.clear()
        self._file_widgets.clear()
        self._refresh_file_display()
        self.lbl_folder_hint.configure(text="")

    def _remove_file(self, filepath: str):
        """右键菜单：移除单个文件"""
        norm = os.path.normpath(filepath)
        if norm in self._selected_set:
            self._selected_set.discard(norm)
            self.selected_files = [f for f in self.selected_files if os.path.normpath(f) != norm]
            self._refresh_file_display()

    def _open_file_folder(self, filepath: str):
        """右键菜单：打开文件所在文件夹"""
        folder = os.path.dirname(filepath)
        open_folder_in_explorer(folder)

    def _refresh_file_display(self):
        """刷新文件列表显示"""
        for w in self.file_list.winfo_children():
            w.destroy()
        self._file_widgets.clear()

        count = len(self.selected_files)
        self.lbl_count.configure(text=f"  📊 已选择: {count} 张图片")

        # 计算总大小
        total_bytes = 0
        for f in self.selected_files:
            try:
                total_bytes += os.path.getsize(f)
            except OSError:
                pass
        self.lbl_total_size.configure(text=f"总大小: {format_size(total_bytes)}")

        if count == 0:
            self.lbl_empty = ctk.CTkLabel(
                self.file_list,
                text="✨ 点击上方按钮添加图片或文件夹\n支持 JPG / PNG / WEBP / BMP / TIFF / GIF\n\n也可以直接拖拽文件到此区域",
                font=ctk.CTkFont(size=13), text_color="gray",
            )
            self.lbl_empty.pack(pady=50)
            return

        for i, f in enumerate(self.selected_files):
            if i >= FILE_DISPLAY_LIMIT:
                more_lbl = ctk.CTkLabel(
                    self.file_list,
                    text=f"… 还有 {count - FILE_DISPLAY_LIMIT} 张图片",
                    text_color="gray", font=ctk.CTkFont(size=11),
                )
                more_lbl.pack(anchor="w", padx=8, pady=4)
                break

            self._create_file_row(f, i)

    def _create_file_row(self, filepath: str, index: int):
        """创建单行文件项（含缩略图和右键菜单）"""
        fname = os.path.basename(filepath)
        fdir = os.path.dirname(filepath)
        try:
            fsize = format_size(os.path.getsize(filepath))
        except OSError:
            fsize = "?"

        # 交替背景色
        bg = ("gray92", "#252830") if index % 2 == 0 else ("gray96", "#1e2028")
        row = ctk.CTkFrame(self.file_list, fg_color=bg, corner_radius=4, height=40)
        row.pack(fill="x", padx=4, pady=1)
        row.pack_propagate(False)

        # 缩略图（异步加载）
        thumb_label = ctk.CTkLabel(row, text="", width=36, height=36)
        thumb_label.pack(side="left", padx=(6, 4), pady=2)

        self._load_thumbnail_async(filepath, thumb_label)

        # 文件名
        ctk.CTkLabel(
            row, text=fname, anchor="w",
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(2, 0))

        # 大小和路径（右侧）
        info_text = f"{fsize}  ·  {fdir}"
        if len(info_text) > 60:
            info_text = f"{fsize}  ·  …{fdir[-40:]}"
        ctk.CTkLabel(
            row, text=info_text,
            anchor="e", text_color="gray", font=ctk.CTkFont(size=10),
        ).pack(side="right", padx=8)

        # 右键菜单
        menu = tk.Menu(row, tearoff=0)
        menu.add_command(label="🗑 移除此文件", command=lambda fp=filepath: self._remove_file(fp))
        menu.add_command(label="📂 打开所在文件夹", command=lambda fp=filepath: self._open_file_folder(fp))

        row.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root))
        for child in row.winfo_children():
            child.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root))

        self._file_widgets.append(row)

    def _load_thumbnail_async(self, filepath: str, label: ctk.CTkLabel):
        """异步加载缩略图"""
        def _load():
            try:
                pil_img = generate_thumbnail(filepath, size=32)
                if pil_img:
                    tk_img = ImageTk.PhotoImage(pil_img)
                    self._thumbnail_cache[filepath] = tk_img
                    self.after(0, lambda: label.configure(image=tk_img))
            except Exception:
                pass

        thread = threading.Thread(target=_load, daemon=True)
        thread.start()

    # ══════════════════════════════════════════════════════════
    #  压缩流程
    # ══════════════════════════════════════════════════════════

    def _start_compression(self):
        if not self.selected_files:
            messagebox.showwarning("提示", "请先添加图片再开始压缩。")
            return
        if self.processing:
            return

        # ── 参数校验 ─────────────────────────────────────────
        try:
            target_size = float(self.var_target.get())
            min_size = float(self.var_min.get())
        except ValueError:
            messagebox.showerror("输入错误", "目标大小和忽略大小必须为有效数字。")
            return

        fmt = self.var_format.get()
        prefix = self.var_prefix.get()
        suffix = self.var_suffix.get()
        quality = self.var_quality.get()

        renaming_rules = {
            "prefix": prefix,
            "suffix": suffix,
            "rename_skipped": self.var_rename_skip.get(),
        }

        resize_options = {
            "enabled": self.var_resize.get(),
        }
        if resize_options["enabled"]:
            try:
                resize_options["width"] = int(self.var_rw.get())
                resize_options["height"] = int(self.var_rh.get())
                if resize_options["width"] <= 0 or resize_options["height"] <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                messagebox.showerror("输入错误", "尺寸宽度和高度必须为正整数。")
                return

        # ── 开始处理 ─────────────────────────────────────────
        self.processing = True
        self.compressor.reset()
        self.btn_start.grid_remove()
        self.btn_cancel.grid()
        self.progress.set(0)
        self.lbl_percent.configure(text="0%")
        self._log_clear()
        self._log(f"🚀 开始处理，共 {len(self.selected_files)} 张图片...\n")
        self.lbl_status.configure(text="⏳ 处理中...")

        thread = threading.Thread(
            target=self._run_compression,
            args=(target_size, min_size, fmt, renaming_rules, resize_options, quality),
            daemon=True,
        )
        thread.start()

    def _cancel_compression(self):
        """取消压缩"""
        self.compressor.request_stop()
        self._log("\n⚠ 用户请求取消，正在停止...\n")
        self.lbl_status.configure(text="⏳ 正在停止...")

    def _run_compression(self, target_size, min_size, fmt, renaming_rules, resize_options, quality):
        total = len(self.selected_files)
        stats = {"success": 0, "skipped": 0, "error": 0}
        total_saved = 0
        output_folders = set()

        start_time = time.time()

        for i, file_path in enumerate(self.selected_files):
            if self.compressor.stop_requested:
                self._log("⏹ 已取消处理。")
                break

            # 确定输出文件夹
            if self.var_custom_out.get() and self.custom_output_path:
                out_folder = self.custom_output_path
            else:
                out_folder = os.path.dirname(file_path)

            output_folders.add(out_folder)

            result = self.compressor.compress_image(
                input_path=file_path,
                output_folder=out_folder,
                target_size_mb=target_size,
                min_size_mb=min_size,
                output_format=fmt,
                renaming_rules=renaming_rules,
                resize_options=resize_options,
                quality=quality if target_size <= 0 else None,
            )

            fname = os.path.basename(file_path)
            if result.status == "SUCCESS":
                stats["success"] += 1
                saved = result.original_size - result.output_size
                total_saved += max(0, saved)
                ratio = calc_compression_ratio(result.original_size, result.output_size)
                self._log(
                    f"✅ {fname}  {format_size(result.original_size)} → {result.detail}  ({ratio})"
                )
            elif result.status in ("SKIPPED", "SKIPPED_COPIED"):
                stats["skipped"] += 1
                action = "已复制重命名" if result.status == "SKIPPED_COPIED" else "已跳过"
                self._log(f"⏭ {fname}  ({action})")
            else:
                stats["error"] += 1
                self._log(f"❌ {fname}  错误: {result.detail}")

            progress = (i + 1) / total
            self.after(0, lambda p=progress, idx=i: self._update_progress(p, idx + 1, total))

        # ── 完成 ─────────────────────────────────────────────
        elapsed = time.time() - start_time
        summary = (
            f"\n{'━' * 40}\n"
            f"  📊 处理完成{'（已取消）' if self.compressor.stop_requested else ''}\n"
            f"  ✅ 成功: {stats['success']}  ⏭ 跳过: {stats['skipped']}  ❌ 失败: {stats['error']}\n"
            f"  📦 共计: {total} 张图片  ⏱ 用时: {elapsed:.1f}s\n"
            f"  💾 节省空间: {format_size(total_saved)}\n"
            f"{'━' * 40}"
        )
        self._log(summary)

        # 更新统计标签
        self.after(0, lambda: self.lbl_stats.configure(
            text=f"✅{stats['success']}  ⏭{stats['skipped']}  ❌{stats['error']}  💾{format_size(total_saved)}"
        ))

        self.after(0, lambda: self._finish_compression(output_folders))

    def _update_progress(self, value, current, total):
        self.progress.set(value)
        pct = int(value * 100)
        self.lbl_percent.configure(text=f"{pct}%")
        self.lbl_status.configure(text=f"⏳ 处理中: {current} / {total}")

    def _finish_compression(self, output_folders: set):
        self.processing = False
        self.btn_cancel.grid_remove()
        self.btn_start.grid()
        self.lbl_status.configure(text="✅ 处理完成")
        self.progress.set(1)
        self.lbl_percent.configure(text="100%")

        if self.compressor.stop_requested:
            self.lbl_status.configure(text="⏹ 已取消")
            messagebox.showinfo("已取消", "压缩任务已取消。部分文件可能已处理完成。")
        else:
            # 弹出完成提示
            if self.var_auto_open.get() and output_folders:
                result = messagebox.askyesno(
                    "完成",
                    "所有图片处理完成！\n\n是否打开输出文件夹？"
                )
                if result:
                    for folder in output_folders:
                        open_folder_in_explorer(folder)
                        break  # 只打开第一个
            else:
                messagebox.showinfo("完成", "所有图片处理完成！请查看日志面板了解详情。")

    # ══════════════════════════════════════════════════════════
    #  日志
    # ══════════════════════════════════════════════════════════

    def _log(self, msg: str):
        """线程安全地写入日志"""
        self.after(0, lambda: self._log_append(msg))

    def _log_append(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _log_clear(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ══════════════════════════════════════════════════════════
    #  UI 切换
    # ══════════════════════════════════════════════════════════

    def _on_quality_change(self, value):
        """质量滑块变化回调"""
        self.lbl_quality.configure(text=f"{int(value)}%")

    def _toggle_theme(self, value):
        """深色/浅色主题切换"""
        ctk.set_appearance_mode(value)

    def _toggle_resize(self):
        if self.var_resize.get():
            for child in self.resize_frame.winfo_children():
                if isinstance(child, ctk.CTkEntry):
                    child.configure(state="normal")
        else:
            for child in self.resize_frame.winfo_children():
                if isinstance(child, ctk.CTkEntry):
                    child.configure(state="disabled")

    def _toggle_output(self):
        if self.var_custom_out.get():
            folder = filedialog.askdirectory(title="选择导出文件夹")
            if folder:
                self.custom_output_path = folder
                self.lbl_out_path.configure(
                    text=f"📁 导出到: {os.path.basename(folder)}/",
                    text_color=("black", "white"),
                )
            else:
                self.var_custom_out.set(False)
        else:
            self.custom_output_path = ""
            self.lbl_out_path.configure(text="默认: 源文件夹", text_color="gray")

    def _output_display_text(self) -> str:
        if self.custom_output_path:
            return f"📁 导出到: {os.path.basename(self.custom_output_path)}/"
        return "默认: 源文件夹"

    # ══════════════════════════════════════════════════════════
    #  退出 & 设置保存
    # ══════════════════════════════════════════════════════════

    def _on_closing(self):
        geo = self.geometry()
        settings = {
            "geometry": geo.split("+")[0] if "+" in geo else geo,
            "window_x": self.winfo_x(),
            "window_y": self.winfo_y(),
            "target_size": self.var_target.get(),
            "min_size": self.var_min.get(),
            "output_format": self.var_format.get(),
            "quality_slider": self.var_quality.get(),
            "prefix": self.var_prefix.get(),
            "suffix": self.var_suffix.get(),
            "rename_skipped": self.var_rename_skip.get(),
            "custom_output_enabled": self.var_custom_out.get(),
            "custom_output_path": self.custom_output_path,
            "resize_enabled": self.var_resize.get(),
            "resize_width": self.var_rw.get(),
            "resize_height": self.var_rh.get(),
            "auto_open_folder": self.var_auto_open.get(),
            "theme_mode": self.var_theme.get(),
            "last_folders": self.settings_mgr.settings.get("last_folders", []),
        }
        self.settings_mgr.save(settings)
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = ImageCompressorApp()
    app.mainloop()
