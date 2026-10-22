#!/usr/bin/env python3
"""Make ONE labeled input packet for a single-reference image tool. Not a final ad."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--panel-size", type=int, default=1024)
    args = parser.parse_args()
    try:
        from PIL import Image, ImageDraw, ImageOps, ImageFont
    except ImportError:
        parser.exit(2, "Pillow unavailable. Use an existing image tool to prepare the input packet.\n")
    if not 512 <= args.panel_size <= 1600:
        parser.error("--panel-size must be 512-1600")
    product, template, output = map(lambda x: Path(x).resolve(), (args.product, args.template, args.output))
    if output in (product, template):
        parser.error("Output must not overwrite an original input")
    if output.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        parser.error("Output must be PNG or JPEG")
    size, margin, header = args.panel_size, 20, 98
    try:
        font = ImageFont.load_default(size=26)
        note_font = ImageFont.load_default(size=19)
    except TypeError:
        font = note_font = ImageFont.load_default()
    packet = Image.new("RGB", (size * 2 + margin * 3, size + header + margin), "#e9edf1")
    draw = ImageDraw.Draw(packet)
    for index, source in enumerate((product, template)):
        try:
            with Image.open(source) as opened:
                photo = ImageOps.exif_transpose(opened).convert("RGB")
                thumb = ImageOps.contain(photo, (size, size))
        except OSError as exc:
            parser.exit(2, str(exc) + "\n")
        x = margin + index * (size + margin)
        draw.text((x + 8, 12), ["1 - REAL PRODUCT ONLY", "2 - OLD AD: LAYOUT + COPY ONLY"][index], fill="black", font=font)
        packet.paste(thumb, (x + (size - thumb.width) // 2, header + (size - thumb.height) // 2))
    draw.text((margin + 8, 55), "INPUT REFERENCE PACKET. DO NOT OUTPUT THIS SIDE-BY-SIDE LAYOUT.", fill="black", font=note_font)
    output.parent.mkdir(parents=True, exist_ok=True)
    packet.save(output)
    print(str(output))


if __name__ == "__main__":
    main()
