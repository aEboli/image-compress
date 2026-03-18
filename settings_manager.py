"""
设置管理模块 — 持久化保存/加载用户设置
"""
import json
import os

# 设置文件与脚本同目录
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_SETTINGS = {
    # 窗口
    "geometry": "1050x720",
    "window_x": None,
    "window_y": None,
    # 压缩
    "target_size": "1.0",
    "min_size": "0.1",
    "output_format": "Original",
    "quality_slider": 85,
    # 重命名
    "prefix": "",
    "suffix": "",
    "rename_skipped": False,
    # 导出
    "custom_output_enabled": False,
    "custom_output_path": "",
    "auto_open_folder": True,
    # 尺寸调整
    "resize_enabled": False,
    "resize_width": "800",
    "resize_height": "600",
    # 外观
    "theme_mode": "Dark",
    # 历史记录
    "last_folders": [],
}


class SettingsManager:
    def __init__(self):
        self.settings = self._load()

    def _load(self) -> dict:
        if not os.path.exists(SETTINGS_FILE):
            return DEFAULT_SETTINGS.copy()
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(loaded)
            return merged
        except Exception:
            return DEFAULT_SETTINGS.copy()

    def save(self, settings_dict: dict):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings_dict, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[SettingsManager] 保存设置失败: {e}")

    def get(self, key: str, default=None):
        return self.settings.get(key, DEFAULT_SETTINGS.get(key, default))
