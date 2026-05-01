"""Update children[].gender in each per-case JSON using the second-to-last
digit of the personnummer (odd = male, even = female).

The personnummer itself is NEVER written anywhere; only derived gender is.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ANALYSIS = ROOT / "analysis"

# Personnummer: optional 19/20 century, YYMMDD, optional dash/+ , 4 digits.
PNR_RE = re.compile(
    r"\b(?:(19|20)?(\d{2}))(\d{2})(\d{2})[-+]?(\d{3})(\d)\b"
)


def gender_from_digit(d: str) -> str:
    return "male" if int(d) % 2 == 1 else "female"


def extract_pnrs(text: str):
    """Yield (year_full, month, day, gender) for each personnummer in text."""
    seen = set()
    for m in PNR_RE.finditer(text):
        century, yy, mm, dd, _serial3, last = m.groups()
        # Reject obvious non-pnr (month > 12, day > 31)
        mi, di = int(mm), int(dd)
        if not (1 <= mi <= 12 and 1 <= di <= 31):
            continue
        if century:
            year = int(century + yy)
        else:
            # Heuristic: 2-digit year >= 30 -> 19xx, else 20xx
            year = 1900 + int(yy) if int(yy) >= 30 else 2000 + int(yy)
        key = (year, mi, di, last)
        if key in seen:
            continue
        seen.add(key)
        yield year, mi, di, gender_from_digit(last)


def update_case(json_path: pathlib.Path) -> tuple[int, int]:
    case_id = json_path.stem
    text_path = ROOT / case_id / f"{case_id}.txt"
    md_path = ROOT / case_id / f"{case_id}.md"
    src = None
    for p in (text_path, md_path):
        if p.exists():
            src = p.read_text(errors="ignore")
            break
    if src is None:
        return (0, 0)

    pnrs = list(extract_pnrs(src))
    # Index pnrs by (year, month) and by year only.
    by_ym: dict[tuple[int, int], list[str]] = {}
    by_y: dict[int, list[str]] = {}
    for y, m, _d, g in pnrs:
        by_ym.setdefault((y, m), []).append(g)
        by_y.setdefault(y, []).append(g)

    obj = json.loads(json_path.read_text())
    updated = 0
    skipped = 0
    for child in obj.get("children", []) or []:
        by = child.get("birth_year")
        bm = child.get("birth_month")
        if not by:
            skipped += 1
            continue
        candidates = []
        if bm and (by, bm) in by_ym:
            candidates = by_ym[(by, bm)]
        elif by in by_y:
            candidates = by_y[by]
        if not candidates:
            skipped += 1
            continue
        # If unanimous, use it. Otherwise leave existing.
        if len(set(candidates)) == 1:
            new_g = candidates[0]
            if child.get("gender") != new_g:
                child["gender"] = new_g
                updated += 1
        else:
            skipped += 1

    if updated:
        json_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    return (updated, skipped)


def main() -> None:
    total_u = total_s = 0
    for jp in sorted(ANALYSIS.glob("*.json")):
        if jp.name in ("overview.json",):
            continue
        u, s = update_case(jp)
        total_u += u
        total_s += s
        if u or s:
            print(f"  {jp.stem}: updated {u}, skipped {s}")
    print(f"\nTotal: {total_u} child gender(s) updated, {total_s} skipped")


if __name__ == "__main__":
    main()
