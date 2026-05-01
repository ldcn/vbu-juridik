#!/usr/bin/env python3
"""Anonymize free-text fields in per-case JSONs.

Replaces real personal names that leaked into `summary`, `winner_rationale`
and `notes` with role-based labels (modern, fadern, sonen, dottern, barnet,
[NN]). Place names and institutions are kept.

Re-run is safe: replacements are exact-string and idempotent.
"""

from __future__ import annotations

import json
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent

# Per-case curated replacements: case_id -> list[(old, new)].
# Order matters: longer (full-name) strings first, then bare given names.
REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    "HRG_T_2019_3360": [("sonen Adrian (född 2016)", "sonen (född 2016)")],
    "HRON_T_2019_1046": [("dottern Edda (född 2018)", "dottern (född 2018)")],
    "HRSB_T_2019_3400": [("fadern Jörgen Olsson", "fadern")],
    "HRS_T_2012_5994": [
        ("modern Maria Fallsäter", "modern"),
        ("fadern Peter Fallsäter", "fadern"),
    ],
    "HRS_T_2013_3500": [
        ("modern Jeanette Eriksson", "modern"),
        ("fadern Andreas Lindgren", "fadern"),
        ("ensam vårdnad om Tim", "ensam vårdnad om sonen"),
        ("Tim hade utvecklat", "Sonen hade utvecklat"),
    ],
    "HRS_T_2013_5076": [
        ("modern Maria Aydin på Lidingö", "modern på Lidingö"),
        ("fadern Turan Sharro", "fadern"),
    ],
    "HRS_T_2014_0022": [
        ("modern Lea Rosengren", "modern"),
        ("fadern Mattias Rosengren", "fadern"),
    ],
    "HRS_T_2014_6311": [
        ("sonen Alexander", "sonen"),
        ("Alexander tillerkändes", "Sonen tillerkändes"),
    ],
    "HRS_T_2014_6359": [("ensam vårdnad om Åke", "ensam vårdnad om sonen")],
    "HRS_T_2014_7196": [
        ("ensam vårdnad om Rasmus", "ensam vårdnad om sonen"),
        ("Rasmus skulle ha umgänge", "sonen skulle ha umgänge"),
    ],
    "HRS_T_2015_3738": [("om Gabriel och Johannes", "om de två sönerna")],
    "HRS_T_2016_4331": [
        ("ändrade endast umgänget för Lukas", "ändrade endast umgänget för sonen"),
        ("Modern (Thea)", "Modern"),
        ("upptrappning för Mattias", "upptrappning för fadern"),
    ],
    "HRS_T_2016_5314": [("Filip skulle få umgänge", "Barnet skulle få umgänge")],
    "HRS_T_2017_0590": [
        ("att Yafet inte skulle", "att fadern inte skulle"),
        ("upptrappat umgänge med stöd för Rinos och Valenttina, medan Lorans (12 år)",
         "upptrappat umgänge med stöd för de två yngre barnen, medan det äldsta barnet (12 år)"),
    ],
    "HRS_T_2017_11396": [("ensam vårdnad för fadern (Morgan)", "ensam vårdnad för fadern")],
    "HRS_T_2017_4044": [
        ("För den 12-årige Lorans", "För det äldsta barnet (12 år)"),
        ("För 10-årige Rinos och 5-åriga Valenttina", "För de två yngre barnen (10 och 5 år)"),
    ],
    "HRS_T_2021_2922": [
        ("mellan Mathilda Lagerbäck och hennes pappa Torbjörn Lagerbäck",
         "mellan dottern och hennes pappa"),
        ("framkom att Mathilda helt motsatte sig", "framkom att dottern helt motsatte sig"),
        ("Mathildas tydliga vilja", "dotterns tydliga vilja"),
    ],
    "HRVS_T_2015_2312": [("sonen Vincent och hans far Shane", "sonen och hans far")],
    "TRGBG_T_2017_15531": [
        ("att Elin, 9 år,", "att dottern, 9 år,"),
        ("hos mamman Therese Johnsson i Göteborg", "hos mamman i Göteborg"),
        ("Fadern Michel Berscheid, bosatt i Luxemburg", "Fadern, bosatt i Luxemburg"),
        ("Michel tidigare dömts", "fadern tidigare dömts"),
        ("fann att Elin, trots", "fann att dottern, trots"),
    ],
    "TRNTJ_T_2015_0475": [
        ("att Helena och Håkan fortsatt", "att modern och fadern fortsatt"),
        ("om barnen Oliver och Cornelia, och att barnen ska bo hos Helena",
         "om de två barnen, och att barnen ska bo hos modern"),
        ("Cornelia motsatte sig umgänge med Håkan",
         "Dottern motsatte sig umgänge med fadern"),
        ("Oliver ville inte träffa", "Sonen ville inte träffa"),
        ("påstått våld Håkan utsatt Lottas för",
         "påstått våld fadern utsatt en närstående för"),
    ],
    "TRSTH_T_2015_9659": [
        ("att barnen Vega Lee, 3 år, och Iggy Lou, 2 år,",
         "att de två barnen (3 och 2 år)"),
        ("hos mammorna Linda och Jona Netsman i Freluga",
         "hos mammorna i Freluga"),
        ("Papporna Peter och Oscar Jöback, gifta tillsammans,",
         "Papporna, gifta tillsammans,"),
    ],
    "TRSTN_T_2014_6489": [
        ("mellan föräldrarna Mary Munez och Mikael Carlsson",
         "mellan föräldrarna"),
        ("växelvist boende för dottern Emelie",
         "växelvist boende för dottern"),
    ],
    "TRVAX_T_2018_1365": [
        ("mellan föräldrarna Karin Vernersson Persson och Martin Vernersson",
         "mellan föräldrarna"),
        ("att barnen Wilda och Alma fortsatt ska bo hos fadern Martin",
         "att de två döttrarna fortsatt ska bo hos fadern"),
    ],
    # second-pass cleanups for notes / winner_rationale
    "HRON_T_2019_1046_extra": [],  # placeholder
}

# Additional replacements applied to notes / winner_rationale.
EXTRA: dict[str, list[tuple[str, str]]] = {
    "HRON_T_2019_1046": [("Modig 73801 + Nordlund 50", "moderns ombud + faderns ombud")],
    "HRS_T_2014_6359": [("psykolog Boel Holmgren", "behandlande psykolog")],
    "HRS_T_2014_7196": [
        ("hos Ekerö förbättrades Rasmus situation",
         "hos en släkting förbättrades sonens situation"),
    ],
    "HRS_T_2016_5314": [("Filips önskan", "barnets önskan")],
    "HRS_T_2017_4044": [
        ("två barn (Rinos och Valenttina)", "de två yngre barnen"),
        ("avslogs helt för Lorans enligt dennes vilja",
         "avslogs helt för det äldsta barnet enligt dennes vilja"),
    ],
    "HRS_T_2019_7172": [
        ("förskolegången i Enköping och pappan i Vällingby",
         "förskolegången i moderns ort och pappan på annan ort"),
    ],
    "HRS_T_2021_2922": [
        ("Mathildas bestämda vilja", "dotterns bestämda vilja"),
        ("Mathilda uppgav att Torbjörn var aggressiv", "Dottern uppgav att fadern var aggressiv"),
        ("om att Mathilda inte ville", "om att dottern inte ville"),
        ("att Mathildas filmade", "att dotterns filmade"),
    ],
    "HRVS_T_2015_2312": [
        ("Vincents boende hos mamman", "sonens boende hos mamman"),
        ("Tågresor mellan Vänersborg och Södertälje", "Tågresor mellan parternas orter"),
    ],
    "TRGBG_T_2017_15531": [
        ("att Elin fortsatt", "att dottern fortsatt"),
        ("Elins påstådda vilja", "dotterns påstådda vilja"),
        ("Michel Berscheid dömdes 2015", "Fadern dömdes 2015"),
        ("han förde Elin till Luxemburg", "han förde dottern till Luxemburg"),
        ("ville ge Michel ensam vårdnad", "ville ge fadern ensam vårdnad"),
        ("att Elin kunde få bo i Luxemburg", "att dottern kunde få bo i Luxemburg"),
    ],
    "TRNTJ_T_2015_0475": [
        ("bar Håkan med grovt våld ut Cornelia",
         "bar fadern med grovt våld ut dottern"),
        ("påstått våld från Håkan mot sin sambo Lotta",
         "påstått våld från fadern mot sin sambo"),
    ],
    "TRSTH_T_2015_9659": [
        ("Papporna Peter och Oscar gifta", "Papporna gifta"),
        ("Mammorna Linda och Jona gifta", "Mammorna gifta"),
        ("nämndeman (Birgitta Larsson) var skiljaktig",
         "en nämndeman var skiljaktig"),
    ],
    "TRSTN_T_2014_6489": [("för Emelies aktiviteter", "för dotterns aktiviteter")],
    "HRS_T_2013_5076": [],  # "Tyskland" is a country; keep
}
# merge EXTRA into REPLACEMENTS
for k, v in EXTRA.items():
    REPLACEMENTS.setdefault(k, []).extend(v)

FIELDS = ("summary", "winner_rationale", "notes")


def main() -> None:
    changed = 0
    for f in sorted(ANALYSIS_DIR.glob("*.json")):
        if f.name in {"overview.json"}:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        cid = data.get("case_id")
        repls = REPLACEMENTS.get(cid, [])
        if not repls:
            continue
        touched = False
        for field in FIELDS:
            v = data.get(field)
            if not isinstance(v, str):
                continue
            new_v = v
            for old, new in repls:
                if old in new_v:
                    new_v = new_v.replace(old, new)
            if new_v != v:
                data[field] = new_v
                touched = True
        if touched:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            changed += 1
            print(f"anonymized {cid}")
    print(f"\nDone. {changed} files updated.")


if __name__ == "__main__":
    main()
