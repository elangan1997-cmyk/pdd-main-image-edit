#!/usr/bin/env python3
"""Build portable per-image jobs and prompts. Never calls an image model."""
import argparse
import json
import re
from pathlib import Path

MODE_QUESTION = "这次是 A. 只改产品，保留原图全部文字，还是 B. 产品和文字一起改？"


def read_plan(path):
    path = Path(path).resolve()
    plan = json.loads(path.read_text(encoding="utf-8"))
    mode = plan.get("mode")
    if mode not in ("product-only", "product-and-copy"):
        raise ValueError(MODE_QUESTION)
    if plan.get("profile", "low") not in ("low", "standard"):
        raise ValueError("profile must be low or standard")
    items = plan.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty list")
    seen = set()
    parsed = []
    for item in items:
        item = dict(item)
        ident = item.get("id", "")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", ident) or ident in seen:
            raise ValueError("Invalid or duplicate id: " + str(ident))
        seen.add(ident)
        for key in ("template", "product"):
            value = item.get(key)
            if not isinstance(value, str) or not value:
                raise ValueError(ident + ": missing " + key)
            file = (path.parent / value).resolve()
            if not file.is_file() or file.name.startswith("._"):
                raise ValueError(ident + ": unreadable input " + str(file))
            item[key] = str(file)
        original = item.get("original_copy")
        if not isinstance(original, list) or not original or any(not isinstance(x, str) or not x.strip() for x in original):
            raise ValueError(ident + ": original_copy must contain exact non-empty strings")
        target = item.get("target_copy", original if mode == "product-only" else None)
        if not isinstance(target, list) or not target or any(not isinstance(x, str) or not x.strip() for x in target):
            raise ValueError(ident + ": target_copy must contain exact non-empty strings")
        if mode == "product-only" and target != original:
            raise ValueError(ident + ": product-only cannot change any original copy")
        if mode == "product-and-copy" and item.get("copy_confirmed") is not True:
            raise ValueError(ident + ": new copy requires user confirmation")
        item["target_copy"] = target
        for key, maximum in (("layout", 4), ("anchors", 5)):
            value = item.get(key)
            if not isinstance(value, list) or not value or len(value) > maximum or any(not isinstance(x, str) or not x for x in value):
                raise ValueError(ident + ": " + key + " must contain 1-" + str(maximum) + " concise strings")
        if not isinstance(item.get("product_lock"), str) or not item["product_lock"].strip():
            raise ValueError(ident + ": missing product_lock")
        if item.get("layout_conflict") and item.get("product_priority_confirmed") is not True:
            raise ValueError(ident + ": resolve product versus layout conflict before generation")
        output = item.get("output_file", ident + ".png")
        if Path(output).name != output or Path(output).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise ValueError(ident + ": output_file must be a plain image filename")
        item["output_file"] = output
        parsed.append(item)
    names = [x["output_file"].casefold() for x in parsed]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate output filenames")
    plan["items"] = parsed
    return plan


def make_prompt(item, ratio="1:1", standard=False):
    copy = "；".join("「" + x + "」" for x in item["target_copy"])
    parts = [
        "生成一张完整拼多多主图，比例" + ratio + "。图1是唯一真实产品；图2只供原主图版式、文字和配色参考。",
        "产品锁定：" + item["product_lock"] + "。保留整组实拍原形状、视角、颜色、孔洞、排列和数量关系，只精修光线与清理外背景，不拆散、不复制。",
        "核对锚点：" + "、".join(item["anchors"]) + "。",
        "版式延续：" + "；".join(item["layout"]) + "。",
        "全文必须逐字完整为：" + copy + "。",
        "自然粗黑体，正常字宽字高，不拉伸；通过字号、留白适配。文字、色块、圆角边缘同样清晰。",
        "不用图2旧产品，不新增颗粒、包装或其他文字。图片模型一次生成产品、背景、文字、版式，输出一张成品，不要拼图。"
    ]
    if item.get("product_priority_confirmed") is True:
        parts.insert(2, "用户已选产品一致优先：保留图1真实容器，不改成图2的容器；清除所有旧产品和旧散粒。")
    if standard:
        parts.append("不改变产品透视、厚度和关键结构；不得将生成图当作产品母图。曝光精修不能把实物改成光滑渲染质感。")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        plan = read_plan(args.plan)
    except (ValueError, OSError, TypeError) as exc:
        parser.exit(2, str(exc) + "\n")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for i, item in enumerate(plan["items"]):
        prompt = make_prompt(item, plan.get("ratio", "1:1"), plan.get("profile", "low") == "standard")
        (out / (item["id"] + "_prompt.txt")).write_text(prompt, encoding="utf-8")
        jobs.append({
            **item, "references_in_order": [item["product"], item["template"]],
            "prompt": prompt, "attempts_limit": 3,
            "ready_for_generation": i == 0 or plan.get("sample_approved") is True,
            "visual_review": "pending", "generation_status": "not_generated"
        })
    batch = {"mode": plan["mode"], "sample_approved": plan.get("sample_approved") is True, "count": len(jobs), "jobs": jobs}
    (out / "batch.json").write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(jobs), "ready": sum(j["ready_for_generation"] for j in jobs), "output": str(out.resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
