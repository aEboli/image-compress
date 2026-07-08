from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from main import ImageCompressorApp, parse_dnd_paths


ROOT = Path(__file__).resolve().parents[1]


def test_settings_are_merged_into_one_sidebar_page():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "CTkTabview" not in main_source
    assert "self.tab_view" not in main_source
    assert "_build_compress_tab" not in main_source
    assert "_build_advanced_tab" not in main_source
    assert "_build_settings_panel" in main_source


def test_sidebar_controls_use_compact_sizing():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "SIDEBAR_W = 270" in main_source
    assert "CONTROL_W = 210" in main_source
    assert "CTkScrollableFrame(self, width=SIDEBAR_W" in main_source
    assert "width=250" not in main_source
    assert "pady=(8, 2)" not in main_source
    assert "pady=(2, 10)" not in main_source
    assert "pady=(2, 12)" not in main_source


def test_visual_group_headers_are_not_rendered_in_sidebar():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    removed_headers = [
        "📦 导出格式",
        "✏️ 重命名规则",
        "📐 尺寸调整",
        "📂 导出路径",
    ]

    for header in removed_headers:
        assert header not in main_source


def test_size_delta_text_reports_growth_and_savings():
    assert ImageCompressorApp._format_size_delta(2048) == "节省 2.00 KB"
    assert ImageCompressorApp._format_size_delta(-2048) == "增加 2.00 KB"
    assert ImageCompressorApp._format_size_delta(0) == "无变化"


def test_dnd_setup_initializes_tkdnd_for_customtkinter():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "TkinterDnD" in main_source
    assert "tkdnd_module._require(self)" in main_source
    assert "_register_drop_target(self.file_list)" in main_source


def test_parse_dnd_paths_handles_braced_paths_and_plain_paths():
    data = r"{C:\Users\Me\Desktop\a file.jpg} C:\Users\Me\Desktop\b.png"

    assert parse_dnd_paths(data) == [
        r"C:\Users\Me\Desktop\a file.jpg",
        r"C:\Users\Me\Desktop\b.png",
    ]


def test_drop_event_adds_files_and_scans_directories(tmp_path):
    source_file = tmp_path / "one file.jpg"
    source_dir = tmp_path / "folder with spaces"
    nested_file = source_dir / "two.png"
    source_dir.mkdir()
    Image.new("RGB", (10, 10), "red").save(source_file)
    Image.new("RGB", (10, 10), "blue").save(nested_file)

    app = ImageCompressorApp()
    try:
        app._on_dnd_drop(SimpleNamespace(data=f"{{{source_file}}} {{{source_dir}}}"))

        selected = {Path(path) for path in app.selected_files}
        assert selected == {source_file, nested_file}
    finally:
        app.destroy()
