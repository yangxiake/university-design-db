#!/usr/bin/env python3
"""Render the human-facing official resource note from each profile.yaml."""

import argparse
import pathlib

from yaml_io import load_yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
LABELS = {
    "unresearched": "待核查",
    "not_found": "已检索，尚未找到官方模板页",
    "conflict": "来源存在冲突，待复核",
    "found": "已找到官方资源入口",
}


def render(profile):
    name = profile["identity"]["name_zh"]
    resources = profile["resources"]
    link = resources["official_templates_url"]
    lines = [f"# {name} 官方 PPT 资源", "", f"状态：{LABELS[link['availability']]}。", ""]
    if link["availability"] == "found":
        lines += [f"- 官方入口：{link['value']}",
                  f"- 页面来源：{link['source']}",
                  f"- 核查日期：{link['checked_at']}",
                  f"- 核实状态：{link['verified']}"]
        for field, label in (("official_template_publisher", "发布方"),
                             ("official_template_terms", "使用规则摘要")):
            fact = resources[field]
            if fact["availability"] == "found":
                lines += [f"- {label}：{fact['value']}（来源：{fact['source']}）"]
        lines.append("")
    elif link["availability"] == "not_found":
        lines += [f"检索日期：{link['checked_at']}。检索入口：", ""]
        lines += [f"- {url}" for url in link["search_sources"]]
        lines.append("")
    lines += ["本仓库只提供链接，不镜像学校模板、校徽或照片。使用前请阅读来源页面的规则。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Only check generated files")
    args = parser.parse_args()
    mismatches = []
    paths = list((ROOT / "universities").glob("*/*/profile.yaml"))
    for path in paths:
        expected = render(load_yaml(path.read_text(encoding="utf-8")))
        output = path.with_name("OFFICIAL.md")
        if args.check:
            if not output.exists() or output.read_text(encoding="utf-8") != expected:
                mismatches.append(str(output))
        else:
            output.write_text(expected, encoding="utf-8")
    if mismatches:
        print("Outdated OFFICIAL.md files:", *mismatches[:20], sep="\n")
        raise SystemExit(1)
    print(("Checked" if args.check else "Rendered"), len(paths), "official resource views.")


if __name__ == "__main__":
    main()
