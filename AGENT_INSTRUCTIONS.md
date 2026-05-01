# Agent Instructions: Statistical Analysis of Swedish Child Custody Cases

## 1. Role and goal

You are a legal-analysis agent. Your task is to read every Swedish child-custody
(`vårdnad`, `boende`, `umgänge`) court case in this repository, extract a
structured set of facts from each one, and append it to a single combined
dataset that can be used for statistical overview.

You must work **case by case**, produce **one JSON record per case**, and also
maintain a running **aggregate summary**. Do not skip cases. Do not invent
facts — leave a field `null` if the document does not state it.

### Språk / Language

**All output must be written in Swedish.** This applies to:

- All free-text fields in the per-case JSON (`summary`, `winner_rationale`,
  `notes`, `saken` is already Swedish, etc.).
- The aggregate `overview.md` and `overview.json` (headings, narrative,
  table labels, chart captions).
- Any commit messages, file headers or comments you produce.

The controlled-vocabulary enum values (e.g. `joint`, `sole_mother`,
`alternating`, `mother`, `father`, `both`, `tingsrätt`, `hovrätt`,
`high|medium|low`) and JSON field names stay as defined in this document so
that the data remains machine-readable. Only the human-readable text is in
Swedish.

## 2. Input layout
The repository contains one folder per case after PDF-to-Markdown conversion:

```
<CASE_ID>/
    <CASE_ID>.md          # full ruling text (markdown)
    <CASE_ID>_meta.json   # table of contents + page polygons
    *.jpeg                # extracted figures (usually irrelevant, ignore)
```

The original `<CASE_ID>.pdf` lives at the repo root and should only be
consulted if the markdown is clearly truncated or unreadable.

**Fallback for missing conversions:** if a case has no `<CASE_ID>/` folder
(or the folder is missing the `.md` / `_meta.json` files), read the
`<CASE_ID>.pdf` from the repo root directly and extract the same fields
from the PDF text. Do not skip the case just because the markdown
conversion is absent. Note `"source": "pdf"` (vs `"source": "markdown"`)
in the per-case JSON so it is traceable, and lower
`extraction_confidence` if PDF parsing was noisy.

Case-ID prefix encodes the court:

| Prefix | Court type | Examples |
|---|---|---|
| `TR…` | Tingsrätt (district court, first instance) | `TRSTH` Stockholm, `TRGBG` Göteborg, `TRNTJ` Norrtälje, `TRVAX` Växjö, `TRSTN` … |
| `HR…` | Hovrätt (court of appeal) | `HRG` Göta, `HRS` Svea, `HRNN` Nedre Norrland, `HRON` Övre Norrland, `HRSB` Skåne/Blekinge, `HRVS` Västra Sverige |
| `_R_ORG` suffix | Document is an "original" / referral version | — |

A trailing `_B_` (e.g. `TRSTH_B_2018_15729`) denotes a criminal case (`brottmål`); flag and skip if no custody decision is contained.

## 3. Domain glossary (Swedish → meaning)

- **Vårdnad** — legal custody. `Gemensam vårdnad` = joint, `ensam vårdnad` = sole.
- **Boende** — with whom the child lives. `Växelvis boende` = alternating ~50/50.
- **Umgänge** — visitation rights for the non-residential parent.
- **Kärande / Sökande** — plaintiff. **Svarande** — defendant.
- **Klagande** — appellant. **Motpart** — respondent on appeal.
- **Yrkande** — claim/demand. **Bestritt** — denied.
- **Domslut** — ruling/holding. **Domskäl** — reasoning.
- **Tingsrätten / Hovrätten / Högsta domstolen** — first instance / appeal / supreme.
- **Saken** — the matter at issue (e.g. "Vårdnad om barn", "Barns boende").
- **Personnummer** format `YYMMDD-XXXX` — first 6 digits give birth date; use to compute age at the date of the ruling.
- **Socialnämnden / familjerätten** — social services involvement.
- **LVU** — compulsory care of minors (often relevant context).
- **Våld i nära relation, hot, missbruk** — violence/threats/substance abuse allegations.

## 4. Per-case extraction schema

For each case produce a JSON object with exactly these fields:

```json
{
  "case_id": "HRG_T_2014_2550",
  "court": "Göta hovrätt",
  "court_level": "hovrätt",                 // tingsrätt | hovrätt | högsta domstolen
  "lower_court": "Norrköpings tingsrätt",   // null if first instance
  "lower_court_case_no": "T 1373-13",
  "ruling_date": "2014-10-24",              // ISO date of THIS court's domslut
  "saken": "Barns boende",                  // verbatim from "SAKEN"
  "summary": "2-4 sentence neutral summary of dispute, parties' positions, outcome and reasoning.",

  "parents": [
    {
      "role": "mother|father|other",
      "procedural_role": "klagande|motpart|kärande|svarande",
      "name_initials": "R.M.A.",            // initials only — do NOT store full name
      "birth_year": 1980,
      "age_at_ruling": 34,
      "nationality": "Somalia",             // if stated, else null
      "represented_by_counsel": true
    }
  ],

  "children": [
    {
      "initials": "M.A.B.",
      "birth_year": 2000,
      "birth_month": 6,
      "age_at_ruling": 14,
      "gender": null                         // only if stated
    }
  ],
  "n_children": 5,

  "custody_before": {
    "legal_custody": "joint|sole_mother|sole_father|unclear",
    "residence": "mother|father|alternating|other|unclear",
    "visitation": "free text or null"
  },
  "custody_after": {
    "legal_custody": "joint|sole_mother|sole_father|unclear",
    "residence": "mother|father|alternating|other|unclear",
    "visitation": "free text or null"
  },

  "winner": "mother|father|both|neither|partial_mother|partial_father",
  "winner_rationale": "1-2 sentences explaining who got what they asked for.",

  // Parental-contact balance for the child(ren) after the ruling.
  // Scale: -100 = child lives exclusively with mother, no father contact;
  //           0 = equal / alternating parenting (växelvist boende);
  //        +100 = child lives exclusively with father, no mother contact.
  // Estimate based on the actual time split described in the ruling.
  // Examples: alternating weeks → 0; mother residence + every-other-weekend father → -65;
  // sole mother, supervised visits only → -85; sole mother, no visitation ordered → -100.
  // If the case has multiple children with different outcomes, set this to
  // the arithmetic mean of all children's individual scores (rounded to integer)
  // and populate children_custody_outcomes with per-child details.
  // Leave null if the ruling gives no information about actual time allocation.
  "parental_access_score": null,

  // Only needed when siblings have materially different custody / residence outcomes.
  "children_custody_outcomes": [
    {
      "child_index": 0,
      "residence": "mother|father|alternating|other|unclear",
      "visitation": "free text or null",
      "parental_access_score": null
    }
  ],

  "key_factors": [                           // pick from a controlled vocabulary, extend if needed
    "parental_agreement",
    "child_best_interest",
    "child_own_wishes",
    "domestic_violence_allegation",
    "substance_abuse_allegation",
    "mental_health",
    "cooperation_problems",
    "relocation",
    "social_services_recommendation",
    "vårdnadsutredning",
    "international_element"
  ],

  "social_services_involved": true,
  "vårdnadsutredning_performed": false,
  "child_was_heard": null,
  "appeal_outcome": "modified|affirmed|reversed|withdrawn|n_a",

  "legal_costs_total_sek": 67418,           // sum of rättshjälp amounts if reported
  "judges": ["Björn Karlsson", "Anna Sjöman", "Ulrika Tyrén"],
  "unanimous": true,

  "notes": "Anything else of statistical value: rare procedural feature, unusually long process, repeated litigation, foreign enforcement, etc.",
  "extraction_confidence": "high|medium|low",
  "missing_or_unclear_fields": ["gender"]
}
```

### Rules for the schema

1. **Privacy**: store **initials only** for natural persons. Discard full names
   and full personnummer. Keep birth year (and month for children, to compute
   age). Never echo a personnummer into the output.
   **Free-text fields (`summary`, `winner_rationale`, `notes`) must also be
   anonymized**: never write a person's first or last name. Use role labels
   instead — `modern` / `mamman`, `fadern` / `pappan`, `sonen`, `dottern`,
   `barnet`, `barnen`, `det äldsta barnet`, `de två yngre barnen`, `en
   släkting`, `behandlande psykolog`, etc. Place names, country names,
   institutions (BUP, Familjerätten, socialnämnden), court names and dates
   are kept. If a person must be distinguished, use `[NN1]`, `[NN2]`. The
   helper `analysis/anonymize_summaries.py` performs curated post-hoc
   redactions for cases where names slipped in; extend its `REPLACEMENTS`
   dict if you spot new leaks and re-run it.

   **Pseudoanonymized publications (typically 2023–2026)**: newer rulings
   are published with party labels `AA` (klagande), `BB` (motpart) for
   parents and `CC`, `DD`, `EE`, … for children, accompanied only by
   birth years. Use these letters as the `name_initials` / `initials`
   values — do not invent names. **Never let the `AA`/`BB`/`CC`… labels
   appear in `summary`, `winner_rationale` or `notes`** — translate them
   to role labels (`modern`/`fadern`, `det äldsta barnet`, `den yngre
   sonen`, …). Even though the source is pre-anonymized, infer:
   - **gender of each child** from Swedish pronouns (han/honom/hans →
     male; hon/henne/hennes → female), kinship words (sonen, dottern,
     pojken, flickan, halvbror, halvsyster) or grammatical agreement.
     Leave `gender` null if no signal exists.
   - **parent role** (mother/father) from gendered references in the
     domskäl (mamman/pappan, modern/fadern, han/hon). If only `AA`/`BB`
     occur with no gendered references, set `role: "other"` and lower
     `extraction_confidence`.
   - **ages** from `birth_year` and the ruling year.
   Mark such cases in `notes` if any field had to be left null because
   the publisher's redaction obscured it.
2. **Ages** are computed as `ruling_year - birth_year` (subtract 1 if the
   birthday has not yet occurred by the ruling date when month/day is known).
3. **`custody_before`** = the situation immediately before this court's
   judgment. For an appeal, this is what the lower court decided (or the
   pre-litigation status quo if the appeal addresses that). Read both the
   `YRKANDEN` section and the appended lower-court judgment.
4. **`custody_after`** = what this judgment establishes. If the appeal court
   only modifies one point, copy unchanged elements from the lower court.
5. **`winner`**:
   - `mother` / `father` — that parent got substantially what they asked for.
   - `both` — outcome was a settled agreement (`överenskommelse`) or fully
     joint custody both parents accepted.
   - `partial_*` — split outcome (e.g. joint custody but residence with one).
   - `neither` — court rejected both parties' main yrkanden.
6. If the case is purely procedural (cost reallocation, rättelse, withdrawal)
   and contains no custody decision, set `winner = "n_a"` and explain in
   `notes`.
7. If a field cannot be determined from the document, set it to `null` and
   list the field name in `missing_or_unclear_fields`. Do not guess.

## 5. Procedure

For each case folder, in lexicographic order:

1. Read `<CASE_ID>.md` in full. If it is shorter than the matching PDF
   suggests, also read the PDF.
2. Identify court, instance, date, parties, children (look in headers,
   `PARTER`, `KÄRANDE`, `SVARANDE`, `KLAGANDE`, `MOTPART`, and the appended
   lower-court judgment if present).
3. Identify yrkanden (claims) of each side from `YRKANDEN`.
4. Identify outcome from `DOMSLUT` and reasoning from `DOMSKÄL`.
5. Map roles mother/father from context (often only personnummer + name +
   pronouns reveal sex; if ambiguous use `other` and lower confidence).
6. Compute ages.
7. Write the JSON record to `analysis/<CASE_ID>.json`.
8. Append a one-line CSV row to `analysis/cases.csv` with the flat columns:
   `case_id, court_level, ruling_date, n_children, child_age_min,
   child_age_max, mother_age, father_age, custody_before_legal,
   custody_before_residence, custody_after_legal, custody_after_residence,
   winner, social_services_involved, appeal_outcome, extraction_confidence`.
9. Move on. Do not re-read prior cases.

After all cases are processed, write `analysis/overview.md` containing:

- Total number of cases, by court level and by year.
- Distribution of `winner` (mother / father / both / partial / n/a).
- Custody change matrix: `custody_before.legal × custody_after.legal`.
- Same matrix for `residence`.
- Distribution of number of children, child age, parent age (mean, median,
  range, histogram in 5-year buckets).
- Frequency of each `key_factor`.
- Share of cases with social-services involvement, with vårdnadsutredning,
  where the child was heard.
- Appeal outcomes: how often hovrätt modified vs affirmed tingsrätt.
- Mean / median legal costs where reported.
- A short narrative (½ page) of the most striking patterns.
- A list of cases flagged with `extraction_confidence = low` for human review.

## 6. Output layout

```
analysis/
    <CASE_ID>.json        # one per case
    cases.csv             # flat table, one row per case
    overview.md           # aggregate statistics + narrative (Swedish)
    overview.json         # machine-readable aggregates (English keys preserved)
    overview.html         # self-contained HTML5/CSS/JS dashboard
    build_overview.py     # aggregator + renderer
    fix_genders.py        # one-shot enrichment script (see §8.2)
    anonymize_summaries.py # curated redaction of names in free-text fields (see §8.5)
```

## 7. PDF text extraction

The original PDF-to-Markdown conversion via `pdf2md` is too slow for bulk
processing. Use `pdftotext` (from `poppler-utils`) instead when the
markdown for a case is missing or truncated:

```bash
pdftotext -layout -enc UTF-8 <CASE_ID>.pdf <CASE_ID>/<CASE_ID>.md
```

Record `"source": "pdftotext"` in the per-case JSON. The rest of the
extraction pipeline is unchanged.

## 8. Aggregation, enrichment and presentation

### 8.1 Aggregator (`analysis/build_overview.py`)

Re-run `python3 analysis/build_overview.py` after adding or editing any
per-case JSON. It loads every `analysis/<CASE_ID>.json` and writes:

- `cases.csv` — 16 flat columns, raw English enum values (machine input).
- `overview.json` — raw aggregates, English keys (machine-readable).
- `overview.md` — **Swedish only**: all enum values, headings, narrative
  and table labels are translated via the `SV_*` translation maps in the
  script. The underlying JSON enum values are kept English.
- `overview.html` — see §8.3.

When extending the aggregator:

- Keep raw English enum values in `overview.json` and `cases.csv` — only
  translate at render time (`tr_*` helpers).
- Add new translation maps to the `SV_*` block at the top of the file.
- Use `_collapse_transitions(transitions, side, mp)` to derive
  per-side distributions from a `before → after` transition counter.

### 8.2 Child gender enrichment (`analysis/fix_genders.py`)

Where the markdown contains a child personnummer, derive gender from the
**second-to-last digit**: odd → `male`, even → `female`. Never write the
personnummer to disk; only the derived `gender` lands in
`children[].gender`. Re-run this script if new cases are added.

### 8.3 HTML dashboard (`analysis/overview.html`)

A single self-contained HTML5 file produced by
`render_html(agg, cases)` in `build_overview.py`. Requirements:

- Plain HTML5 + CSS3 + vanilla JS, no build tools, no frameworks.
- Charts via Chart.js 4.4.1 from
  `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js`
  (CDN, requires internet to view).
- All visible text in **Swedish**.
- Sticky top nav linking to sections: `#nyckeltal`, `#filter`,
  `#instans`, `#utfall`, `#vardnad`, `#barn`, `#foraldrar`, `#faktorer`,
  `#process`, `#bilaga`.
- KPI cards (totals, mean ages), grid of `<canvas>` cards. Chart types:
  - doughnut (pie) for categorical splits (instans, vinnare, vårdnad
    före/efter, boende före/efter, kön, processuella ja/nej, hovrättens
    utfall),
  - bar for distributions (antal barn, ålderhistogram för barn/mor/far),
  - horizontal bar for nyckelfaktorer **och för „Detaljerat utfall“**,
  - line for mål per år.
- **Stabila färger per kategori**: kategoriska etiketter (mor, far,
  gemensam, hos mor, hos far, växelvis, pojke, flicka, ja, nej,
  fastställd, ändrad, …) måste alltid renderas i samma färg över alla
  diagram via JS-mappen `LABEL_COLOR` och hjälpfunktionen
  `colorFor(label, idx)`. PALETTE används bara som fallback för
  etiketter utan fast färg (t.ex. domstolsnamn) och som per-serie-färg
  i jämförelseläge.
- The "Ursprunglig tingsrätt"-diagrammet ska vara en **wide** kort
  (`class="card wide"`, full bredd via `grid-column: 1 / -1`) och
  visa **alla** tingsrätter; höjden beräknas dynamiskt i
  `render_html` som `max(420, 28 * antal_tingsrätter + 60)` så att
  varje stapel får plats.
- **Interaktivitet (klientsida)**: hela per-mål-datamängden bäddas in
  som JS-konstant `ALL` (en kompakt projektion via `_case_for_js(c)`,
  fält redan översatta till svenska etiketter). En `aggregate(cases)`
  i JS räknar om alla diagram från en filtrerad lista, och
  `applyFilter()` återskapar Chart.js-instanser via `inst[id].destroy()`
  följt av `new Chart(...)`. UI-panelen `#filter` innehåller en
  `<select multiple>` med alla ursprungliga tingsrätter och en
  kryssruta `Jämförelseläge`:
  - Inget val → all statistik visas (default).
  - Ett eller flera val utan jämförelseläge → diagrammen visar enbart
    de valda tingsrätternas mål, med ursprungliga diagramtyper
    (doughnut/bar/line).
  - Två eller fler val + jämförelseläge → varje vald tingsrätt blir en
    egen serie/dataset; doughnut-diagrammen renderas om till grupperade
    stapeldiagram, och årslinjen blir flera linjer.
  - KPI-talen (totalt antal mål, snittåldrar, kostnadsstatistik) räknas
    om för det filtrerade urvalet via element-id `kpi_*`.
  - `#filter_status` visar antal mål i nuvarande urval.
  Bibehåll denna kontrakt vid framtida ändringar: lägg till nya fält
  i `_case_for_js` om de ska kunna filtreras, och uppdatera
  `CHART_META`/`aggregate` i JS i samma takt som diagramkort läggs till.
- Per-case-data injiceras som JS-konstant `const ALL = […]` via
  `_case_for_js(c)`; statiska aggregat (används bara som
  startvärden i KPI-korten) byggs av `build_aggregates`.
- **Detaljerat utfall**: `outcome_detail` aggregeras av
  `_outcome_label(c)` som kombinerar `custody_after.legal_custody`
  (eller `custody_after.type`), `custody_after.residence` och en
  kategoriserad version av `custody_after.visitation` till en svensk
  etikett som t.ex. `Gemensam vårdnad, växelvist boende` eller
  `Ensam vårdnad (mor), boende hos mor, umgänge varannan helg`.
  Visitation-fri text grupperas av `_categorize_visitation` till
  kända hinkar (`umgänge varannan helg`, `umgänge varannan vecka`,
  `trappat umgänge`, `videoumgänge / distansumgänge`,
  `inget/begränsat umgänge`, `omfattande umgänge`,
  `umgänge var fjärde vecka`, `umgänge att fastställas senare`,
  `övrigt reglerat umgänge`). Sammansatta `residence`-värden
  (t.ex. `shared_for_oldest_mother_for_others`) blir
  `blandat boende (per barn)`. Diagrammet `ch_outcome` är en
  **wide** horisontell stapel med höjd `max(360, 28 * N + 60)`.
- Appendix `#bilaga`: one `<article class="case">` per case (sorted by
  `case_id`) with målnummer, instans, datum, antal barn, vinnare (svensk
  etikett) and a Swedish summary truncated to **max 150 ord** via
  `_truncate_words(c["summary"], 150)`.

- **Text and visibility config**: all dashboard copy (titles, labels,
  section descriptions, chart titles, KPI labels, filter UI text) and
  component visibility are configured via
  `analysis/overview_ui_text.json`.
  - `visibility.sections.<id>` controls whole sections (`nyckeltal`,
    `filter`, `instans`, `utfall`, `vardnad`, `barn`, `foraldrar`,
    `faktorer`, `process`, `bilaga`).
  - `visibility.charts.<id>` controls individual chart cards
    (`court_level`, `year`, `court`, `origin_tingsratt`, `winners`,
    `appeal`, `outcome`, `legal_before`, `legal_after`,
    `residence_before`, `residence_after`, `n_children`, `child_gender`,
    `child_age`, `mother_age`, `father_age`, `factors`, `soc`, `vu`,
    `heard`).
  - `visibility.kpi.<id>` controls KPI cards (`total`, `kids_n`,
    `children`, `child_age`, `mother_age`, `father_age`, `cost_n`,
    `cost_mean`, `cost_median`, `cost_max`).
  - Missing keys fall back to defaults in `DEFAULT_UI_TEXT` in
    `analysis/build_overview.py`.

The HTML is **always** regenerated together with `cases.csv`,
`overview.json` and `overview.md` by a single run of
`python3 analysis/build_overview.py`. Whenever new cases are added (or
existing JSONs edited), re-run the script and verify both that the
appendix `#bilaga` contains an `<article class="case">` for every new
`case_id` and that the script's stdout reports the expected total
(`Wrote … (N cases).`). For pseudoanonymized cases (AA/BB/CC… labels)
also confirm that no such labels leak into the appendix summaries —
they must be rewritten to role labels before the rebuild.

### 8.4 Re-build workflow

```bash
python3 analysis/fix_genders.py          # only if new cases added
python3 analysis/anonymize_summaries.py  # after writing new summaries
python3 analysis/build_overview.py       # always after JSON edits;
                                         # also regenerates overview.html
```

### 8.5 Anonymization of free-text fields

`analysis/anonymize_summaries.py` keeps a per-`case_id` dict of literal
`(old, new)` string replacements applied to `summary`,
`winner_rationale` and `notes`. It is idempotent (replacements only fire
if `old` is still present). When a new case is added or an existing
summary is edited, scan the JSON for capitalised first names and add
entries for any leaks before re-running the script. Use role labels
(`modern`, `fadern`, `sonen`, `dottern`, `barnet`, `det äldsta barnet`,
…) rather than initials in the redacted text — initials still uniquely
identify individuals when combined with the målnummer.

## 9. Quality and safety

- Be conservative. `null` is better than a wrong value.
- Do not include personally identifying information beyond initials and
  birth year (month for children).
- The text is sometimes OCR-noisy (`Hovrätten`/`Hovratten`,
  `Aadan`/`Aadam`, missing diacritics, broken hyphens). Normalise silently
  but record the case in `notes` if a critical field is unreadable.
- Use the controlled vocabularies above; if you must add a new
  `key_factor` value, use `snake_case` and document it in `overview.md`.
- Do not draw legal conclusions of your own; only summarise what the court
  wrote.
- Process cases independently; do not let one case's interpretation bias
  another.

## 10. Change documentation policy

Every repository change must be documented in the same commit/PR.

- Update this file (`AGENT_INSTRUCTIONS.md`) when behavior, schema,
  workflow, or conventions change.
- Add a dated entry to `CHANGELOG.md` for every implemented change
  (code, data pipeline, dashboard behavior, configuration keys,
  documentation-only changes).
- For dashboard/UI changes, document both:
  1. user-facing effect and
  2. config key/path (`analysis/overview_ui_text.json`) or code path
     (`analysis/build_overview.py`) used.
- Do not merge undocumented changes.
