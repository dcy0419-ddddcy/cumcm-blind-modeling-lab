from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    files = sorted(args.input.glob("*/*.png"))
    cols, rows = 3, 3
    cell_w, cell_h = 420, 600
    margin, label_h = 12, 30
    font = ImageFont.load_default(size=18)
    batch_no = 0

    for batch_no, start in enumerate(range(0, len(files), cols * rows), 1):
        batch = files[start : start + cols * rows]
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "#d9d9d9")
        draw = ImageDraw.Draw(sheet)
        for pos, path in enumerate(batch):
            row, col = divmod(pos, cols)
            with Image.open(path) as source:
                page = source.convert("RGB")
                page.thumbnail((cell_w - 2 * margin, cell_h - label_h - 2 * margin))
                x = col * cell_w + (cell_w - page.width) // 2
                y = row * cell_h + label_h + margin
                sheet.paste(page, (x, y))
            draw.text(
                (col * cell_w + margin, row * cell_h + 5),
                f"{path.parent.name} / {path.stem}",
                fill="black",
                font=font,
            )
        sheet.save(args.output / f"contact_{batch_no:02d}.png", optimize=True)

    print(f"Created {batch_no} contact sheets for {len(files)} rendered pages")


if __name__ == "__main__":
    main()
