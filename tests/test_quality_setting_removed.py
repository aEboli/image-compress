from pathlib import Path
import inspect

from compressor import Compressor


ROOT = Path(__file__).resolve().parents[1]


def test_quality_setting_is_not_exposed_in_ui_or_saved_settings():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    removed_ui_tokens = [
        "var_quality",
        "quality_slider",
        "lbl_quality",
        "_on_quality_change",
        "压缩质量",
    ]

    for token in removed_ui_tokens:
        assert token not in main_source


def test_default_settings_do_not_persist_quality_slider():
    settings_source = (ROOT / "settings_manager.py").read_text(encoding="utf-8")
    default_settings_block = settings_source.split("DEFAULT_SETTINGS = {", 1)[1].split("\n}", 1)[0]

    assert "quality_slider" not in default_settings_block


def test_compressor_does_not_accept_manual_quality_setting():
    signature = inspect.signature(Compressor.compress_image)

    assert "quality" not in signature.parameters
