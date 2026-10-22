#!/usr/bin/env python3
"""Technical checks and reference contact sheets; visual QA is never auto-passed."""
import argparse
import json
from pathlib import Path
from build_batch import read_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError:
        parser.exit(2, "Pillow unavailable; use an existing image viewer for manual checks.\n")
    try:
        plan = read_plan(args.plan)
    except (ValueError, OSError, TypeError) as exc:
        parser.exit(2, str(exc) + "\n")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    results = Path(args.results)
    reports, cards = [], []
    for item in plan["items"]:
        file = results / item["output_file"]
        report = {"id": item["id"], "file": str(file.resolve()), "technical_errors": [], "visual_review": "pending", "copy_review": "pending", "copy_fact_status": item.get("copy_fact_status", "not_verified")}
        card = Image.new("RGB", (940, 490), "#eeeeee")
        draw = ImageDraw.Draw(card)
        draw.text((12, 10), item["id"] + " / ORIGINAL PRODUCT", fill="black")
        draw.text((482, 10), item["id"] + " / MODEL OUTPUT", fill="black")
        for col, path in enumerate((Path(item["product"]), file)):
            try:
                with Image.open(path) as opened:
                    image = ImageOps.exif_transpose(opened).convert("RGB")
                    if col == 1:
                        report["dimensions"] = list(image.size)
                        if min(image.size) < 512:
                            report["technical_errors"].append("max readable size too small: minimum edge below 512")
                        ratio = plan.get("ratio", "1:1").split(":")
                        wanted = float(ratio[0]) / float(ratio[1])
                        if abs(image.width / image.height / wanted - 1) > 0.02:
                            report["technical_errors"].append("unexpected aspect ratio")
                    thumb = ImageOps.contain(image, (450, 450))
                    card.paste(thumb, (col * 470 + (470 - thumb.width) // 2, 34 + (450 - thumb.height) // 2))
            except (OSError, ValueError) as exc:
                report["technical_errors"].append(("product: " if col == 0 else "output: ") + str(exc))
                draw.text((col * 470 + 12, 60), "MISSING / UNREADABLE", fill="red")
        report["technical_pass"] = not report["technical_errors"]
        reports.append(report)
        cards.append(card)
    for start in range(0, len(cards), 4):
        subset = cards[start:start + 4]
        sheet = Image.new("RGB", (940, 490 * len(subset)), "#eeeeee")
        for index, card in enumerate(subset):
            sheet.paste(card, (0, index * 490))
        sheet.save(out / ("review_%02d.jpg" % (start + 1)), quality=92)
    missing = [r["id"] for r in reports if not r["technical_pass"]]
    report = {"expected": len(reports), "technical_pass": not missing, "failed_technical_ids": missing, "visual_review": "pending", "warning": "Technical pass is not visual acceptance. Read every image and exact copy.", "items": reports}
    (out / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"expected": len(reports), "technical_pass": not missing, "visual_review": "pending"}, ensure_ascii=False))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
