# Changelog

Detta dokument loggar alla ändringar i repositoryt.

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
