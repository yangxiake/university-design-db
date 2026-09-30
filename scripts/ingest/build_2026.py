#!/usr/bin/env python3
"""Rebuild the 2026 ordinary-HEI index and the selected 933-school scope.

Inputs are the two official Ministry of Education attachments and the two
reviewed selection CSVs supplied with this project. Binary attachments are
read from a local path or downloaded into memory; only text data is committed.
"""

import argparse
import csv
import hashlib
import io
import pathlib
import re
import urllib.request

import xlrd
from pypdf import PdfReader
import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MANIFEST = yaml.safe_load((DATA / "source-manifest.yaml").read_text(encoding="utf-8"))
MOE_XLS = MANIFEST["sources"]["ordinary_schools_2026"]["attachment"]
MOE_SHA256 = MANIFEST["sources"]["ordinary_schools_2026"]["sha256"]
DOUBLE_FIRST_PDF = MANIFEST["sources"]["double_first_class_2022"]["attachment"]
DOUBLE_FIRST_SHA256 = MANIFEST["sources"]["double_first_class_2022"]["sha256"]
SELECTION_SHA256 = {
    "selection-source/benke-candidates-2026.csv": MANIFEST["selection_inputs"]["benke_candidates"]["sha256"],
    "selection-source/scope-selected-2026.csv": MANIFEST["selection_inputs"]["selected_non_double_first"]["sha256"],
}
MILITARY = {"国防科技大学", "海军军医大学", "空军军医大学"}
RENAME = {"上海体育学院": "上海体育大学"}


def normalize(value):
    return str(value).strip().replace("（", "(").replace("）", ")")


def code(value):
    return str(int(value)) if isinstance(value, float) else str(value).strip()


def source_bytes(url, local, expected_sha):
    if local:
        payload = pathlib.Path(local).read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "university-design-db/1.0"})
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha:
        raise ValueError("Official attachment checksum changed: %s (expected %s)" % (digest, expected_sha))
    return payload


def read_official(xls_bytes):
    book = xlrd.open_workbook(file_contents=xls_bytes)
    sheet = book.sheet_by_index(0)
    province = None
    records = []
    for number in range(sheet.nrows):
        cells = [normalize(c.value) for c in sheet.row(number)]
        if not cells:
            continue
        heading = re.fullmatch(r"(.+?)\((\d+)所\)", cells[0])
        if heading:
            province = heading.group(1)
            continue
        if len(cells) < 6:
            continue
        identifier = code(sheet.cell(number, 2).value)
        if not re.fullmatch(r"\d{10}", identifier):
            continue
        if not province:
            raise ValueError("Missing provincial heading before row %d" % number)
        records.append({
            "school_code": identifier,
            "name_zh": cells[1],
            "province": province,
            "city": cells[4],  # The source calls this 所在地; it is not a street address.
            "level": cells[5],
            "authority": cells[3],
            "note": cells[6] if len(cells) > 6 else "",
            "source_url": MOE_XLS,
            "source_as_of": str(MANIFEST["dataset_as_of"]),
        })
    if len(records) != 2952 or sum(r["level"] == "本科" for r in records) != 1412:
        raise ValueError("Official 2026 row/level counts do not reconcile")
    if len({r["school_code"] for r in records}) != len(records):
        raise ValueError("Duplicate Ministry school code")
    return records


def read_double_first(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    names = []
    for page in reader.pages:
        for line in page.extract_text().splitlines():
            match = re.match(r"^\s*([\u4e00-\u9fff（）()]+)[：:]", line)
            if match:
                names.append(normalize(RENAME.get(match.group(1), match.group(1))))
    if len(names) != 147 or len(set(names)) != 147:
        raise ValueError("Second-round Double First-Class list is not 147 unique schools")
    return names


def read_csv(name):
    path = DATA / name
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SELECTION_SHA256[name]:
        raise ValueError("Selection input checksum changed: " + str(path))
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def category(row):
    name = row["name_zh"]
    if name.endswith("大学"):
        return "大学类"
    if len(name) <= 5:
        return "短校名≤5字"
    if not row["note"]:
        return "其余未备注本科"
    if row["note"] == "中外合作办学及内地与港澳合作办学":
        return "中外/港澳合作办学"
    if name == "燕京理工学院":
        return "指定民办"
    raise ValueError("Selected school has no selection category: " + name)


def build(records, first_class):
    by_code = {r["school_code"]: r for r in records}
    by_name = {r["name_zh"]: r for r in records}
    within = set(first_class) - MILITARY
    if len(within) != 144 or any(name not in by_name for name in within):
        raise ValueError("Double First-Class schools do not reconcile with 2026 Ministry list")
    if any(name in by_name for name in MILITARY):
        raise ValueError("Military exceptions unexpectedly occur in Ministry list")

    candidates = read_csv("selection-source/benke-candidates-2026.csv")
    selected = read_csv("selection-source/scope-selected-2026.csv")
    expected_candidates = [r for r in records if r["level"] == "本科"
                           and r["name_zh"] not in within
                           and not r["name_zh"].endswith(("职业技术大学", "职业大学"))]
    candidate_codes = [r["学校标识码"] for r in candidates]
    if len(candidates) != 1144 or candidate_codes != [r["school_code"] for r in expected_candidates]:
        raise ValueError("Candidate list differs from official selection chain")
    selected_codes = {r["学校标识码"] for r in selected}
    marked_codes = {r["学校标识码"] for r in candidates if r["纳入范围(打√)"] == "√"}
    if len(selected) != 789 or selected_codes != marked_codes:
        raise ValueError("789 selected schools do not match candidate marks")
    if any(by_code[r["学校标识码"]]["name_zh"] != r["学校名称"] for r in selected):
        raise ValueError("Selected school names do not match Ministry codes")
    selected_by_code = {r["学校标识码"]: r for r in selected}
    category_counts = {}
    for item in selected:
        key = category(by_code[item["学校标识码"]])
        category_counts[key] = category_counts.get(key, 0) + 1
    if category_counts != {"大学类": 349, "短校名≤5字": 146,
                           "其余未备注本科": 289, "中外/港澳合作办学": 4,
                           "指定民办": 1}:
        raise ValueError("Selected categories do not reconcile: %r" % category_counts)

    scope = []
    for record in records:
        if record["name_zh"] in within:
            category_name = "双一流建设高校"
            basis_url = DOUBLE_FIRST_PDF
        elif record["school_code"] in selected_by_code:
            category_name = category(record)
            basis_url = "" if category_name == "指定民办" else MOE_XLS
        else:
            continue
        tags = []
        if record["name_zh"] in within:
            tags.append("double_first")
        if record["name_zh"].endswith("大学"):
            tags.append("name_ends_university")
        if len(record["name_zh"]) <= 5:
            tags.append("short_name")
        if not record["note"]:
            tags.append("moe_note_blank")
        if "合作" in record["note"]:
            tags.append("cooperative")
        if "海南自由贸易港" in record["note"]:
            tags.append("hainan_education_institution")
        if record["name_zh"] == "燕京理工学院":
            tags.append("user_selected")
        scope.append({**record, "scope_category": category_name,
                      "scope_tags": "|".join(tags), "scope_source_url": basis_url})
    counts = {}
    for item in scope:
        key = item["scope_category"]
        counts[key] = counts.get(key, 0) + 1
    if counts != {"双一流建设高校": 144, "大学类": 349, "短校名≤5字": 146,
                  "其余未备注本科": 289, "中外/港澳合作办学": 4, "指定民办": 1}:
        raise ValueError("Final scope categories do not reconcile: %r" % counts)
    if len(scope) != 933 or len({r["school_code"] for r in scope}) != 933:
        raise ValueError("Final scope is not 933 unique Ministry school codes")
    return scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--moe-xls", help="Optional local copy of the official 2026 XLS")
    parser.add_argument("--double-first-pdf", help="Optional local copy of the 2022 official PDF")
    args = parser.parse_args()
    records = read_official(source_bytes(MOE_XLS, args.moe_xls, MOE_SHA256))
    first_class = read_double_first(source_bytes(DOUBLE_FIRST_PDF, args.double_first_pdf, DOUBLE_FIRST_SHA256))
    scope = build(records, first_class)
    index_fields = ["school_code", "name_zh", "province", "city", "level", "authority",
                    "note", "source_url", "source_as_of"]
    write_csv(ROOT / "universities-index.csv", records, index_fields)
    write_csv(DATA / "universities-scope-2026.csv", scope,
              index_fields + ["scope_category", "scope_tags", "scope_source_url"])
    print("Wrote 2952 indexed schools and 933 selected schools; no military exceptions.")


if __name__ == "__main__":
    main()
