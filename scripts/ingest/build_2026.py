#!/usr/bin/env python3
"""Rebuild the 2026 ordinary-HEI index and the complete 1412-school undergraduate scope.

Inputs are the two official Ministry of Education attachments; historical
selection CSVs do not filter the current scope. Binary attachments are
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


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build(records, first_class):
    by_name = {r["name_zh"]: r for r in records}
    within = set(first_class) - MILITARY
    if len(within) != 144 or any(name not in by_name for name in within):
        raise ValueError("Double First-Class schools do not reconcile with Ministry list")
    scope = []
    for record in records:
        if record["level"] != "本科":
            continue
        if record["name_zh"] in MILITARY:
            raise ValueError("Military exception unexpectedly appears in Ministry list")
        vocational = record["name_zh"].endswith(("职业大学", "职业技术大学"))
        cooperative = "合作" in record["note"]
        private = "民办" in record["note"]
        first = record["name_zh"] in within
        category_name = ("双一流建设高校" if first else "职业本科" if vocational else
                         "合作办学本科" if cooperative else "民办本科" if private else "其他本科")
        tags = ["all_undergraduate"]
        for enabled, tag in [(first, "double_first"), (vocational, "vocational_undergraduate"),
                             (cooperative, "cooperative"), (private, "private"),
                             (record["name_zh"].endswith("大学"), "name_ends_university"),
                             (len(record["name_zh"]) <= 5, "short_name"),
                             (not record["note"], "moe_note_blank"),
                             ("海南自由贸易港" in record["note"], "hainan_education_institution")]:
            if enabled:
                tags.append(tag)
        scope.append({**record, "scope_category": category_name,
                      "scope_tags": "|".join(tags), "scope_source_url": MOE_XLS})
    if len(scope) != 1412 or len({r["school_code"] for r in scope}) != 1412:
        raise ValueError("Scope must be every unique undergraduate school in Ministry list")
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
    print("Wrote 2952 indexed schools and 1412 undergraduate schools; no military exceptions.")


if __name__ == "__main__":
    main()
