from pathlib import Path
import random

from PIL import Image

from compressor import Compressor


def make_noisy_rgb_image(size=(512, 512)) -> Image.Image:
    image = Image.new("RGB", size)
    pixels = image.load()
    random.seed(7)

    for y in range(size[1]):
        for x in range(size[0]):
            pixels[x, y] = (
                (x * 3 + y * 5 + random.randrange(64)) % 256,
                (x * 7 + y * 2 + random.randrange(64)) % 256,
                (x * 11 + y * 13 + random.randrange(64)) % 256,
            )

    return image


def test_png_export_uses_target_size_when_possible(tmp_path):
    source = tmp_path / "source.jpg"
    output_dir = tmp_path / "out"
    target_mb = 0.09
    target_bytes = int(target_mb * 1024 * 1024)

    make_noisy_rgb_image().save(source, format="JPEG", quality=95)

    result = Compressor().compress_image(
        input_path=str(source),
        output_folder=str(output_dir),
        target_size_mb=target_mb,
        min_size_mb=0,
        output_format="PNG",
    )

    assert result.status == "SUCCESS"
    assert Path(result.output_path).suffix.lower() == ".png"
    assert result.output_size <= target_bytes


def test_png_export_with_alpha_uses_target_size_path(tmp_path):
    source = tmp_path / "transparent.png"
    output_dir = tmp_path / "out"
    image = Image.new("RGBA", (128, 128), (255, 0, 0, 0))

    for y in range(128):
        for x in range(128):
            if (x + y) % 3 == 0:
                image.putpixel((x, y), (x * 2 % 256, y * 2 % 256, 128, 128))

    image.save(source, format="PNG")

    result = Compressor().compress_image(
        input_path=str(source),
        output_folder=str(output_dir),
        target_size_mb=0.01,
        min_size_mb=0,
        output_format="PNG",
    )

    assert result.status == "SUCCESS"
    assert Path(result.output_path).suffix.lower() == ".png"
    assert result.output_size > 0
