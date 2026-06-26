"""Create the compact, high-contrast Windows icon for 星算工坊."""

import math
from pathlib import Path

from PIL import Image, ImageDraw


ASSET_DIR = Path(__file__).resolve().parent
PNG_PATH = ASSET_DIR / "app_icon.png"
ICO_PATH = ASSET_DIR / "app_icon.ico"
MASTER_SIZE = 1024
ICON_SIZES = (256, 128, 64, 48, 32, 24, 20, 16)


def _star_points(cx: float, cy: float, outer: float, inner: float) -> list[tuple[int, int]]:
    """Return a symmetric five-point star suitable for very small icon frames."""
    points = []
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        radius = outer if index % 2 == 0 else inner
        points.append((round(cx + math.cos(angle) * radius), round(cy + math.sin(angle) * radius)))
    return points


def _draw_master_icon(size: int = MASTER_SIZE) -> Image.Image:
    """Draw a deliberately simple mark that remains readable at 16 pixels."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = size / MASTER_SIZE
    px = lambda value: round(value * scale)

    # A high-contrast app tile creates a clean silhouette on light and dark taskbars.
    draw.rounded_rectangle(
        (px(54), px(54), px(970), px(970)),
        radius=px(210),
        fill="#10213d",
        outline="#315174",
        width=px(28),
    )
    draw.rounded_rectangle(
        (px(94), px(94), px(930), px(930)),
        radius=px(174),
        outline="#1ee4f1",
        width=px(12),
    )

    # Taskbar frames are normally only 16--32 pixels.  A single large mark is
    # clearer than the old star-and-orbit illustration at that scale.
    star = _star_points(px(510), px(500), px(330), px(145))
    draw.polygon(star, fill="#22d6e7")
    draw.line(star + [star[0]], fill="#d9ffff", width=px(20), joint="curve")
    draw.ellipse((px(752), px(205), px(826), px(279)), fill="#ffb30f")
    return image


def _draw_taskbar_icon(size: int) -> Image.Image:
    """Draw a dedicated small icon frame instead of shrinking the large artwork.

    Windows taskbars normally use 16--32 pixel frames.  At that scale the
    decorative border and small orange detail become visual noise, so this
    frame deliberately uses only a large, high-contrast star on a solid tile.
    """
    supersampling = 8
    canvas_size = size * supersampling
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def px(value: float) -> int:
        return round(value * supersampling)

    outer_margin = max(0.5, size * 0.025)
    radius = max(2.0, size * 0.19)
    draw.rounded_rectangle(
        (px(outer_margin), px(outer_margin), px(size - outer_margin), px(size - outer_margin)),
        radius=px(radius),
        fill="#10213d",
    )
    star = _star_points(px(size * 0.5), px(size * 0.52), px(size * 0.405), px(size * 0.178))
    draw.polygon(star, fill="#22d6e7")

    # Keep the 16/20 px frames as just two solid colours.  A small accent is
    # only useful once there are enough physical pixels to render it cleanly.
    if size >= 24:
        dot_radius = size * 0.075
        draw.ellipse(
            (px(size * 0.72 - dot_radius), px(size * 0.26 - dot_radius),
             px(size * 0.72 + dot_radius), px(size * 0.26 + dot_radius)),
            fill="#ffb30f",
        )
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    master = _draw_master_icon()
    master.save(PNG_PATH, optimize=True)

    # Use the same interface artwork in every Windows icon frame.
    frames = [master.resize((size, size), Image.Resampling.LANCZOS) for size in ICON_SIZES]
    frames[0].save(ICO_PATH, format="ICO", sizes=[(size, size) for size in ICON_SIZES], append_images=frames[1:])
    print(f"Updated {PNG_PATH.name} and {ICO_PATH.name}")


if __name__ == "__main__":
    main()
