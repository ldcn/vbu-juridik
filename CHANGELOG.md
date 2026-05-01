# Changelog

Detta dokument loggar alla ändringar i repositoryt.

## 2026-05-01 (2)

- Refined parental-access scoring in `analysis/build_overview.py`:
  - Heuristic now supports finer buckets `-100, -75, -50, -25, 0, 25, 50, 75, 100` instead of only coarse `-100/-50/0/50/100`.
  - Scoring uses residence + visitation text signals (e.g. no contact, supervised/very limited contact, varannan helg, substantial contact, alternating/equal split).
  - Per-child fallback handling improved for `children_custody_outcomes` rows where `residence`/`visitation` are top-level fields.
- Updated appendix summary meta in generated `overview.html`:
  - Removed `utfall:` and replaced with `kontaktbalans:` per case.
- Applied Swedish currency formatting for process-cost KPI cards (mean/median/max):
  - Static server-rendered values now use Swedish grouping + `kr` (e.g. `104 644 kr`).
  - Dynamic filtered values in browser now use `Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK' })`.

- Fixed case-loading bug in `analysis/build_overview.py`:
  - `load_cases()` now excludes `analysis/overview_ui_text.json` in addition to `analysis/overview.json`.
  - This removed a non-case config file from aggregates and corrected totals from 66 to 65 real case JSONs.
  - Regenerated `analysis/cases.csv`, `analysis/overview.json`, `analysis/overview.md`, and `analysis/overview.html` with the corrected count.

- Renamed chart label "Vinnare" → **"Utfall per part"** throughout (`build_overview.py`, `overview_ui_text.json`). The old term carried a win/lose connotation inappropriate for child custody decisions; the new label is neutral legal Swedish meaning "what each party obtained".
- Added **Kontaktbalans** chart to the *Utfall* section:
  - Scale −100 (child exclusively with mother, no father contact) to 0 (equal/alternating) to +100 (exclusively with father).
  - `build_overview.py`: new `_parental_access_score(c)` helper reads the explicit `parental_access_score` field if the agent has set it, otherwise falls back to a heuristic based on `custody_after.residence` + visitation free-text.
  - Chart uses a diverging colour scheme (blue = mother-side, green = neutral, pink = father-side).
  - Mini stats row (n, mean, median) below the chart, updated dynamically when the court filter changes.
  - `visibility.charts.access_score` controls can hide/show the card.
- Extended per-case JSON schema in `AGENT_INSTRUCTIONS.md`:
  - New optional field `parental_access_score` (integer −100…+100).
  - New optional field `children_custody_outcomes` (array) for cases where siblings have materially different residence outcomes, enabling per-child score averaging.

## 2026-05-01

- Added configurable dashboard text and labels via `analysis/overview_ui_text.json`.
- Added configurable dashboard visibility controls via:
  - `visibility.sections.*`
  - `visibility.charts.*`
  - `visibility.kpi.*`
- Updated HTML renderer in `analysis/build_overview.py` to honor visibility config for:
  - section rendering
  - nav link rendering
  - chart card rendering
  - KPI rendering
- Set default `visibility.kpi.kids_n = false` to hide the KPI card "mål med barnantal".
- Updated documentation in `AGENT_INSTRUCTIONS.md`:
  - dashboard config reference (text + visibility)
  - mandatory change documentation policy
- Added repository-local Python virtual environment setup references in workspace config (`.vscode/settings.json`) and ignored local env folders in `.gitignore`.
