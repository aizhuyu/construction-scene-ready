#!/usr/bin/env python3
"""Verify BibTeX DOI metadata against Crossref and write an auditable CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ENTRY_RE = re.compile(r"@\w+\{([^,]+),(.*?)(?=\n@|\Z)", re.DOTALL)


@dataclass(frozen=True)
class BibRecord:
    key: str
    title: str
    year: str
    doi: str


def _field(block: str, name: str) -> str:
    match = re.search(
        rf"\b{name}\s*=\s*(?:\{{(.*?)\}}|\"(.*?)\")\s*,?\s*(?:\n|$)",
        block,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").replace("\n", " ").strip()


def parse_bibtex(path: Path) -> list[BibRecord]:
    text = path.read_text(encoding="utf-8")
    return [
        BibRecord(
            key=match.group(1).strip(),
            title=_field(match.group(2), "title"),
            year=_field(match.group(2), "year"),
            doi=_field(match.group(2), "doi").lower(),
        )
        for match in ENTRY_RE.finditer(text)
    ]


def normalize_title(value: str) -> str:
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\\[A-Za-z]+\s*", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def crossref_year(message: dict[str, Any]) -> str:
    for field in ("published-print", "published-online", "issued"):
        parts = message.get(field, {}).get("date-parts", [])
        if parts and parts[0]:
            return str(parts[0][0])
    return ""


def fetch_crossref(record: BibRecord, cache_dir: Path) -> dict[str, Any]:
    cache_path = cache_dir / f"{urllib.parse.quote(record.doi, safe='')}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    url = "https://api.crossref.org/works/" + urllib.parse.quote(
        record.doi, safe=""
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            completed = subprocess.run(
                [
                    "curl",
                    "-fsS",
                    "--max-time",
                    "30",
                    "--retry",
                    "2",
                    "-A",
                    "ConstructionSceneReady-reference-audit/0.1",
                    url,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            cache_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return payload
        except (subprocess.SubprocessError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last_error))


def audit_record(record: BibRecord, cache_dir: Path) -> dict[str, str]:
    row = {
        "bibtex_key": record.key,
        "doi": record.doi,
        "bib_title": record.title,
        "crossref_title": "",
        "bib_year": record.year,
        "crossref_year": "",
        "title_similarity": "",
        "status": "no_doi",
        "error": "",
    }
    if not record.doi:
        return row
    try:
        payload = fetch_crossref(record, cache_dir)
        message = payload["message"]
        crossref_title = " ".join(message.get("title") or [])
        similarity = SequenceMatcher(
            None,
            normalize_title(record.title),
            normalize_title(crossref_title),
        ).ratio()
        official_year = crossref_year(message)
        year_ok = (
            not record.year
            or not official_year
            or abs(int(record.year) - int(official_year)) <= 1
        )
        row.update(
            {
                "crossref_title": crossref_title,
                "crossref_year": official_year,
                "title_similarity": f"{similarity:.3f}",
                "status": (
                    "verified"
                    if similarity >= 0.80 and year_ok
                    else "manual_review"
                ),
            }
        )
    except Exception as error:  # The CSV must retain failed verification cases.
        row["status"] = "lookup_failed"
        row["error"] = f"{type(error).__name__}: {error}"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bib", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    records = parse_bibtex(args.bib)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(audit_record, record, args.cache_dir): record
            for record in records
        }
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: row["bibtex_key"].lower())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(json.dumps({"entries": len(rows), "status": counts}, indent=2))
    return 0 if not counts.get("lookup_failed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
