#!/usr/bin/env python3
"""Build cases.csv, overview.md, overview.json and overview.html.

Reads every analysis/<CASE_ID>.json and produces aggregate statistics.
Re-run after adding new per-case JSONs.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent

CSV_COLUMNS = [
    "case_id", "court_level", "ruling_date", "n_children",
    "child_age_min", "child_age_max", "mother_age", "father_age",
    "custody_before_legal", "custody_before_residence",
    "custody_after_legal", "custody_after_residence",
    "winner", "social_services_involved", "appeal_outcome",
    "extraction_confidence",
]

# ---------------------------------------------------------------------------
# Swedish translations for controlled vocabularies
# ---------------------------------------------------------------------------

SV_WINNER = {
    "mother": "mor",
    "father": "far",
    "both": "båda",
    "neither": "ingen",
    "partial_mother": "delvis mor",
    "partial_father": "delvis far",
    "n_a": "ej tillämpligt",
}

SV_LEGAL = {
    "joint": "gemensam",
    "sole_mother": "ensam mor",
    "sole_father": "ensam far",
    "unclear": "oklart",
}

SV_RESIDENCE = {
    "mother": "hos mor",
    "father": "hos far",
    "alternating": "växelvis",
    "other": "annat",
    "unclear": "oklart",
    "unknown": "okänt",
}

SV_APPEAL = {
    "modified": "ändrad",
    "partially_modified": "delvis ändrad",
    "affirmed": "fastställd",
    "remanded": "återförvisad",
    "settlement": "förlikning",
}

SV_FACTORS = {
    "child_best_interest": "barnets bästa",
    "cooperation_problems": "samarbetssvårigheter",
    "parental_agreement": "överenskommelse mellan föräldrarna",
    "domestic_violence_allegation": "påståenden om våld",
    "vårdnadsutredning": "vårdnadsutredning",
    "social_services_recommendation": "socialtjänstens rekommendation",
    "child_own_wishes": "barnets egen vilja",
    "mental_health": "psykisk ohälsa",
    "international_element": "internationell anknytning",
    "relocation": "flytt",
    "substance_abuse_allegation": "påståenden om missbruk",
    "trauma": "trauma",
    "continuity": "kontinuitet",
    "geographical_distance": "geografiskt avstånd",
    "parental_alienation": "föräldraalienation",
    "child_was_heard": "barnet har hörts",
}

SV_BOOL = {True: "ja", False: "nej", None: "okänt", "true": "ja", "false": "nej", "null": "okänt"}

SV_LEVEL = {
    "hovrätt": "hovrätt",
    "tingsrätt": "tingsrätt",
    "högsta domstolen": "högsta domstolen",
}

DEFAULT_UI_TEXT = {
    "page": {
      "title": "Översikt – svenska vårdnadsmål",
      "subtitle": "Aggregerad statistik från {total_cases} domar om vårdnad, boende och umgänge.",
    },
    "nav": {
      "nyckeltal": "Nyckeltal",
      "filter": "Filter",
      "instans": "Instans & år",
      "utfall": "Utfall",
      "vardnad": "Vårdnad & boende",
      "barn": "Barn",
      "foraldrar": "Föräldrar",
      "faktorer": "Nyckelfaktorer",
      "process": "Processuella drag",
      "bilaga": "Bilaga: sammanfattningar",
    },
    "sections": {
      "nyckeltal": {
        "title": "Nyckeltal",
        "description": "Snabb översikt över omfattning, barnvolym och genomsnittliga åldrar i materialet.",
      },
      "filter": {
        "title": "Filter och jämförelse",
        "description": "Filtrera hela dashboardsiffran på ursprunglig tingsrätt, eller jämför flera tingsrätter sida vid sida.",
      },
      "instans": {
        "title": "Instans och år",
        "description": "Visar hur målen fördelar sig mellan domstolsnivåer, avgörande domstolar och kalenderår.",
      },
      "utfall": {
        "title": "Utfall",
        "description": "Belyser vem som får gehör samt hur hovrätten förhåller sig till tingsrättens avgörande.",
      },
      "vardnad": {
        "title": "Vårdnad och boende",
        "description": "Jämför läget före och efter dom avseende rättslig vårdnad och barnets boende.",
      },
      "barn": {
        "title": "Barn",
        "description": "Beskriver antal barn per mål, könsfördelning och åldersstruktur i 5-årsintervall.",
      },
      "foraldrar": {
        "title": "Föräldrar",
        "description": "Visar åldersfördelning för mödrar och fäder vid tidpunkten för avgörandet.",
      },
      "faktorer": {
        "title": "Nyckelfaktorer i domskäl",
        "description": "Frekvenser av centrala omständigheter och argument som domstolen beaktar.",
      },
      "process": {
        "title": "Processuella drag",
        "description": "Sammanfattar processindikatorer och rapporterade kostnader i materialet.",
      },
      "bilaga": {
        "title": "Bilaga: kort sammanfattning per mål",
        "description": "Varje sammanfattning är på max 150 ord. Sorterat på målnummer.",
      },
    },
    "filter": {
      "intro": "Välj en eller flera <strong>ursprungliga tingsrätter</strong> (första instans) för att begränsa all statistik nedan till de målen. Markera <em>jämförelseläge</em> för att se varje vald tingsrätt som en egen serie i diagrammen (Ctrl/Cmd-klicka för flera).",
      "court_label": "Ursprunglig tingsrätt:",
      "compare_label": "Jämförelseläge",
      "clear_button": "Rensa val",
    },
    "charts": {
      "court_level": "Fördelning per instans",
      "year": "Mål per år",
      "court": "Fördelning per domstol (avgörande)",
      "origin_tingsratt": "Ursprunglig tingsrätt (första instäns)",
      "winners": "Utfall per part",
      "appeal": "Hovrättens utfall i förhållande till tingsrätten",
      "outcome": "Detaljerat utfall (vårdnad + boende + umgänge)",
      "access_score": "Kontaktbalans",
      "access_score_note": "\u2212100\u00a0=\u00a0barnet enbart hos mor utan faderskontakt\u00a0\u00b7\u00a00\u00a0=\u00a0v\u00e4xelvis boende\u00a0\u00b7\u00a0+100\u00a0=\u00a0barnet enbart hos far utan moderskontakt",
      "legal_before": "Rättslig vårdnad – före",
      "legal_after": "Rättslig vårdnad – efter",
      "residence_before": "Boende – före",
      "residence_after": "Boende – efter",
      "n_children": "Antal barn per mål",
      "child_gender": "Barnens kön",
      "child_age": "Barnens ålder (5-årsintervall)",
      "mother_age": "Mödrarnas ålder (5-årsintervall)",
      "father_age": "Fädernas ålder (5-årsintervall)",
      "factors": "Nyckelfaktorer i domskäl",
      "soc": "Socialtjänst inblandad",
      "vu": "Vårdnadsutredning utförd",
      "heard": "Barnet hört",
    },
    "kpi": {
      "total": "mål totalt",
      "kids_n": "mål med barnantal",
      "children": "barn totalt",
      "child_age": "snittålder barn (år)",
      "mother_age": "snittålder mor (år)",
      "father_age": "snittålder far (år)",
      "cost_n": "mål med kostnadsuppgift",
      "cost_mean": "snittkostnad (SEK)",
      "cost_median": "mediankostnad (SEK)",
      "cost_max": "högsta kostnad (SEK)",
    },
    "js_labels": {
      "cases_series": "Mål",
      "count_series": "Antal",
      "show_all": "Visar alla {total} mål",
      "show_filtered": "Visar {total} mål från {courts}",
      "compare": "Jämför {n_courts} tingsrätter ({parts} = {total} mål)",
    },
    "visibility": {
      "sections": {
        "nyckeltal": True,
        "filter": True,
        "instans": True,
        "utfall": True,
        "vardnad": True,
        "barn": True,
        "foraldrar": True,
        "faktorer": True,
        "process": True,
        "bilaga": True,
      },
      "charts": {
        "court_level": True,
        "year": True,
        "court": True,
        "origin_tingsratt": True,
        "winners": True,
        "appeal": True,
        "outcome": True,
        "access_score": True,
        "legal_before": True,
        "legal_after": True,
        "residence_before": True,
        "residence_after": True,
        "n_children": True,
        "child_gender": True,
        "child_age": True,
        "mother_age": True,
        "father_age": True,
        "factors": True,
        "soc": True,
        "vu": True,
        "heard": True,
      },
      "kpi": {
        "total": True,
        "kids_n": False,
        "children": True,
        "child_age": True,
        "mother_age": True,
        "father_age": True,
        "cost_n": True,
        "cost_mean": True,
        "cost_median": True,
        "cost_max": True,
      },
    },
    "footer": "Genererad av build_overview.py. Underliggande data: per-fall-JSON i analysis/.",
  }


def _deep_merge_dict(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in (override or {}).items():
      if isinstance(value, dict) and isinstance(merged.get(key), dict):
        merged[key] = _deep_merge_dict(merged[key], value)
      else:
        merged[key] = value
    return merged


def load_ui_text() -> dict:
    path = ANALYSIS_DIR / "overview_ui_text.json"
    if not path.exists():
      return DEFAULT_UI_TEXT
    try:
      raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
      print(f"WARN: could not load {path}: {e}; using defaults")
      return DEFAULT_UI_TEXT
    if not isinstance(raw, dict):
      print(f"WARN: {path} must be a JSON object; using defaults")
      return DEFAULT_UI_TEXT
    return _deep_merge_dict(DEFAULT_UI_TEXT, raw)


def sv(map_: dict, value):
    if value is None:
        return "okänt"
    return map_.get(value, str(value))


# ---------------------------------------------------------------------------
# Load + per-case helpers
# ---------------------------------------------------------------------------


def _ages(items, key="age_at_ruling"):
    return [c.get(key) for c in items or [] if isinstance(c, dict) and c.get(key) is not None]


def _parent_age(parents, role):
    for p in parents or []:
        if p.get("role") == role and p.get("age_at_ruling") is not None:
            return p["age_at_ruling"]
    return None


_OUTCOME_LEGAL = {
    "joint": "gemensam vårdnad",
    "sole_mother": "ensam vårdnad (mor)",
    "sole_father": "ensam vårdnad (far)",
    "unclear": "oklart om vårdnad",
}
_OUTCOME_RES = {
    "mother": "boende hos mor",
    "father": "boende hos far",
    "alternating": "växelvist boende",
    "other": "annat boende",
    "unclear": "oklart boende",
    "unknown": None,
    None: None,
}


def _categorize_visitation(v):
    """Map a free-text or enum visitation field to a short Swedish label."""
    if v is None or v == "":
        return None
    if not isinstance(v, str):
        return None
    s = v.strip().lower()
    if s in ("regulated", "reglerat"):
        return "reglerat umgänge"
    if s in ("unregulated", "oreglerat"):
        return "oreglerat umgänge"
    if any(x in s for x in ("inget umgänge", "ingen kontakt", "inget reglerat")):
        return "inget/begränsat umgänge"
    if "trapp" in s:
        return "trappat umgänge"
    if any(x in s for x in ("video", "skype", "telefon")):
        return "videoumgänge / distansumgänge"
    if "varannan helg" in s or "vartannat veckoslut" in s or "vartannan helg" in s:
        return "umgänge varannan helg"
    if "varannan vecka" in s or "varje jämn vecka" in s or "varje ojämn vecka" in s:
        return "umgänge varannan vecka"
    if "var fjärde" in s:
        return "umgänge var fjärde vecka"
    if "omfattande" in s or "utökad" in s:
        return "omfattande umgänge"
    if "planeras" in s or "samråd" in s:
        return "umgänge att fastställas senare"
    return "övrigt reglerat umgänge"


def _outcome_label(c: dict) -> str:
    ca = c.get("custody_after") or {}
    legal = ca.get("legal_custody") or ca.get("type")
    res = ca.get("residence")
    vis = ca.get("visitation")

    legal_lbl = _OUTCOME_LEGAL.get(legal)
    if legal_lbl is None:
        # Composite/blandat (e.g. "sole_father_for_oldest_sole_mother_for_others")
        legal_lbl = "blandad vårdnad (per barn)"

    if isinstance(res, str) and res in _OUTCOME_RES:
        res_lbl = _OUTCOME_RES[res]
    elif isinstance(res, str) and res:
        # Composite ("shared_for_oldest_…", free text)
        res_lbl = "blandat boende (per barn)"
    else:
        res_lbl = None

    parts = [legal_lbl]
    if res_lbl:
        parts.append(res_lbl)
    vis_lbl = _categorize_visitation(vis)
    if vis_lbl and vis_lbl not in ("reglerat umgänge",):
        # only append visitation if it adds information beyond the default
        parts.append(vis_lbl)
    elif vis_lbl == "reglerat umgänge" and res in ("mother", "father"):
        parts.append("reglerat umgänge")

    return ", ".join(p[0].upper() + p[1:] if i == 0 else p for i, p in enumerate(parts))


_NO_VISIT_RE = re.compile(
  r"inget umgänge|inga umgängen|utan umgänge|nekad?\s+umgänge|nekad?\s+all\s+kontakt",
  re.IGNORECASE,
)
_EQUAL_ACCESS_RE = re.compile(
  r"växelvis|varannan\s+vecka|halva\s+tiden|50\s*/\s*50|lika\s+mycket",
  re.IGNORECASE,
)
_SUBSTANTIAL_ACCESS_RE = re.compile(
  r"varje\s+helg|3\s+av\s+4\s+helger|tre\s+helger|flera\s+vardagar|halva\s+lov",
  re.IGNORECASE,
)
_LIMITED_ACCESS_RE = re.compile(
  r"varannan\s+helg|en\s+vardag|onsdag|två\s+helger|2\s+helger",
  re.IGNORECASE,
)
_VERY_LIMITED_ACCESS_RE = re.compile(
  r"umgängesstöd|övervakat|kontaktperson|några\s+timmar|kort\s+umgänge|2\s+timmar",
  re.IGNORECASE,
)


def _score_from_share(father_share: float) -> int:
  """Map a father contact share to nearest discrete score bucket."""
  score = (father_share - 0.5) * 200
  buckets = [-100, -75, -50, -25, 0, 25, 50, 75, 100]
  return min(buckets, key=lambda b: abs(score - b))


def _residence_visit_to_share(res: str | None, visit: str) -> float | None:
  """Estimate father share from residence + visitation wording."""
  if res == "alternating" or _EQUAL_ACCESS_RE.search(visit):
    return 0.5

  if res == "mother":
    if _NO_VISIT_RE.search(visit):
      return 0.0
    if _VERY_LIMITED_ACCESS_RE.search(visit):
      return 0.125
    if _LIMITED_ACCESS_RE.search(visit):
      return 0.25
    if _SUBSTANTIAL_ACCESS_RE.search(visit):
      return 0.375
    # Default for mother residence when visitation exists but is unclear.
    return 0.25

  if res == "father":
    if _NO_VISIT_RE.search(visit):
      return 1.0
    if _VERY_LIMITED_ACCESS_RE.search(visit):
      return 0.875
    if _LIMITED_ACCESS_RE.search(visit):
      return 0.75
    if _SUBSTANTIAL_ACCESS_RE.search(visit):
      return 0.625
    # Default for father residence when visitation exists but is unclear.
    return 0.75

  return None


def _parental_access_score(c: dict) -> int | None:
  """Return a score from -100 to +100 representing the child's access balance.

  -100 = lives exclusively with mother, no father contact.
    0  = equal / alternating parenting.
  +100 = lives exclusively with father, no mother contact.

  Reads the explicit ``parental_access_score`` field if the agent has set it;
  otherwise falls back to a heuristic based on ``custody_after.residence``
  and the free-text ``visitation`` string.  Returns None if undetermined.
  """
  explicit = c.get("parental_access_score")
  if isinstance(explicit, (int, float)):
    return int(max(-100, min(100, explicit)))

  ca = c.get("custody_after") or {}
  children_outcomes = c.get("children_custody_outcomes") or []

  # Per-child outcomes (if populated by agent)
  if children_outcomes:
    scores = []
    for ch in children_outcomes:
      s = _parental_access_score(ch)
      if s is not None:
        scores.append(s)
    if scores:
      return round(sum(scores) / len(scores))

  # Support both full case objects (custody_after.*) and per-child rows where
  # residence/visitation may be top-level.
  res = ca.get("residence") or c.get("residence")
  visit = (ca.get("visitation") or c.get("visitation") or "")

  share = _residence_visit_to_share(res, visit)
  if share is None:
    return None
  return _score_from_share(share)


def _format_sek(value: float | int | None) -> str:
  if value is None:
    return "–"
  n = int(round(value))
  sign = "−" if n < 0 else ""
  return f"{sign}{abs(n):,}".replace(",", " ") + " kr"


def load_cases() -> list[dict]:
  cases = []
  for f in sorted(ANALYSIS_DIR.glob("*.json")):
    if f.name in {"overview.json", "overview_ui_text.json"}:
      continue
    try:
      cases.append(json.loads(f.read_text(encoding="utf-8")))
    except Exception as e:
      print(f"WARN: could not load {f}: {e}")
  return cases


def to_csv_row(c: dict) -> dict:
    child_ages = _ages(c.get("children"))
    return {
        "case_id": c.get("case_id"),
        "court_level": c.get("court_level"),
        "ruling_date": c.get("ruling_date"),
        "n_children": c.get("n_children"),
        "child_age_min": min(child_ages) if child_ages else None,
        "child_age_max": max(child_ages) if child_ages else None,
        "mother_age": _parent_age(c.get("parents"), "mother"),
        "father_age": _parent_age(c.get("parents"), "father"),
        "custody_before_legal": (c.get("custody_before") or {}).get("legal_custody"),
        "custody_before_residence": (c.get("custody_before") or {}).get("residence"),
        "custody_after_legal": (c.get("custody_after") or {}).get("legal_custody"),
        "custody_after_residence": (c.get("custody_after") or {}).get("residence"),
        "winner": c.get("winner"),
        "social_services_involved": c.get("social_services_involved"),
        "appeal_outcome": c.get("appeal_outcome"),
        "extraction_confidence": c.get("extraction_confidence"),
    }


def write_csv(cases: list[dict]) -> Path:
    path = ANALYSIS_DIR / "cases.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for c in cases:
            w.writerow(to_csv_row(c))
    return path


def hist_buckets(values: list[int], width: int = 5) -> dict[str, int]:
    buckets: dict[str, int] = defaultdict(int)
    for v in values:
        lo = (v // width) * width
        buckets[f"{lo}-{lo + width - 1}"] += 1
    return dict(sorted(buckets.items(), key=lambda kv: int(kv[0].split("-")[0])))


def stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 2),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


# ---------------------------------------------------------------------------
# Aggregate raw numbers (English keys for JSON, translated at render time)
# ---------------------------------------------------------------------------


def build_aggregates(cases: list[dict]) -> dict:
    total = len(cases)
    by_level = Counter(c.get("court_level") for c in cases)
    by_court = Counter(c.get("court") for c in cases)
    by_origin_tingsratt = Counter(
        (c.get("lower_court") if c.get("court_level") == "hovrätt" else c.get("court"))
        for c in cases
    )
    by_year = Counter((c.get("ruling_date") or "")[:4] for c in cases)
    winners = Counter(c.get("winner") for c in cases)
    custody_legal = Counter(
        (
            (c.get("custody_before") or {}).get("legal_custody"),
            (c.get("custody_after") or {}).get("legal_custody"),
        )
        for c in cases
    )
    custody_res = Counter(
        (
            (c.get("custody_before") or {}).get("residence"),
            (c.get("custody_after") or {}).get("residence"),
        )
        for c in cases
    )
    n_children = [c.get("n_children") for c in cases if isinstance(c.get("n_children"), int)]
    child_ages = [a for c in cases for a in _ages(c.get("children"))]
    child_genders = Counter(
        ch.get("gender") for c in cases for ch in (c.get("children") or []) if isinstance(ch, dict)
    )
    mother_ages = [_parent_age(c.get("parents"), "mother") for c in cases]
    mother_ages = [a for a in mother_ages if a is not None]
    father_ages = [_parent_age(c.get("parents"), "father") for c in cases]
    father_ages = [a for a in father_ages if a is not None]
    key_factors = Counter(f for c in cases for f in (c.get("key_factors") or []))
    soc = Counter(c.get("social_services_involved") for c in cases)
    vu = Counter(c.get("vårdnadsutredning_performed") for c in cases)
    heard = Counter(c.get("child_was_heard") for c in cases)
    appeal = Counter(c.get("appeal_outcome") for c in cases if c.get("court_level") == "hovrätt")
    costs = [c.get("legal_costs_total_sek") for c in cases if isinstance(c.get("legal_costs_total_sek"), (int, float))]
    low_conf = [c.get("case_id") for c in cases if c.get("extraction_confidence") == "low"]
    access_scores_raw = [_parental_access_score(c) for c in cases]
    access_score_dist = dict(
      sorted(
        Counter(s for s in access_scores_raw if s is not None).items()
      )
    )

    return {
        "total_cases": total,
        "by_court_level": dict(by_level),
        "by_court": dict(by_court.most_common()),
        "by_origin_tingsratt": dict(by_origin_tingsratt.most_common()),
        "by_year": dict(sorted(by_year.items())),
        "winners": dict(winners),
        "custody_legal_transitions": {f"{a or 'null'} → {b or 'null'}": n for (a, b), n in custody_legal.items()},
        "custody_residence_transitions": {f"{a or 'null'} → {b or 'null'}": n for (a, b), n in custody_res.items()},
        "n_children_distribution": dict(sorted(Counter(n_children).items())),
        "n_children_stats": stats(n_children),
        "child_age_stats": stats(child_ages),
        "child_age_histogram_5y": hist_buckets(child_ages, 5),
        "child_gender_distribution": dict(child_genders),
        "mother_age_stats": stats(mother_ages),
        "father_age_stats": stats(father_ages),
        "mother_age_histogram_5y": hist_buckets(mother_ages, 5),
        "father_age_histogram_5y": hist_buckets(father_ages, 5),
        "key_factor_frequency": dict(key_factors.most_common()),
        "social_services_involved": dict(soc),
        "vårdnadsutredning_performed": dict(vu),
        "child_was_heard": dict(heard),
        "appeal_outcomes_hovratt": dict(appeal),
        "legal_costs_sek_stats": stats(costs),
        "outcome_detail": dict(Counter(_outcome_label(c) for c in cases).most_common()),
        "low_confidence_cases": low_conf,
        "access_score_distribution": access_score_dist,
        "access_score_stats": stats([s for s in access_scores_raw if s is not None]),
      }


# ---------------------------------------------------------------------------
# Translation helpers for keys
# ---------------------------------------------------------------------------


def tr_winners(d: dict) -> dict:
    return {sv(SV_WINNER, k): v for k, v in d.items()}


def tr_legal_transitions(d: dict) -> dict:
    out: dict[str, int] = {}
    for key, n in d.items():
        a, b = key.split(" → ")
        a_sv = "okänt" if a in ("null", "None") else SV_LEGAL.get(a, a)
        b_sv = "okänt" if b in ("null", "None") else SV_LEGAL.get(b, b)
        k = f"{a_sv} → {b_sv}"
        out[k] = out.get(k, 0) + n
    return out


def tr_residence_transitions(d: dict) -> dict:
    out: dict[str, int] = {}
    for key, n in d.items():
        a, b = key.split(" → ")
        a_sv = "okänt" if a in ("null", "None") else SV_RESIDENCE.get(a, a)
        b_sv = "okänt" if b in ("null", "None") else SV_RESIDENCE.get(b, b)
        k = f"{a_sv} → {b_sv}"
        out[k] = out.get(k, 0) + n
    return out


def tr_appeal(d: dict) -> dict:
    return {sv(SV_APPEAL, k): v for k, v in d.items()}


def tr_factors(d: dict) -> dict:
    return {SV_FACTORS.get(k, k): v for k, v in d.items()}


def tr_bool_dict(d: dict) -> dict:
    out: dict[str, int] = {}
    for k, v in d.items():
        if isinstance(k, str) and k in ("true", "false", "null"):
            kk = SV_BOOL[k]
        else:
            kk = SV_BOOL.get(k, "okänt")
        out[kk] = out.get(kk, 0) + v
    return out


def tr_court_level(d: dict) -> dict:
    return {SV_LEVEL.get(k, k or "okänt"): v for k, v in d.items()}


def tr_gender(d: dict) -> dict:
    m = {"male": "pojke", "female": "flicka", None: "okänt"}
    out: dict[str, int] = {}
    for k, v in d.items():
        kk = m.get(k, str(k) if k else "okänt")
        out[kk] = out.get(kk, 0) + v
    return out


def _collapse_transitions(transitions: dict, side: str, mp: dict) -> dict:
    """Collapse a 'before → after' transition counter to one side, translated."""
    out: dict[str, int] = {}
    for key, n in transitions.items():
        a, b = key.split(" → ")
        v = a if side == "before" else b
        v_sv = "okänt" if v in ("null", "None") else mp.get(v, v)
        out[v_sv] = out.get(v_sv, 0) + n
    return out


# ---------------------------------------------------------------------------
# Markdown rendering (Swedish)
# ---------------------------------------------------------------------------


def md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def render_md(agg: dict) -> str:
    lines = []
    lines.append("# Översikt – svenska vårdnadsmål")
    lines.append("")
    lines.append(f"Totalt antal mål: **{agg['total_cases']}**")
    lines.append("")
    lines.append("## Fördelning per instans")
    lines.append(md_table(["Instans", "Antal"], list(tr_court_level(agg["by_court_level"]).items())))
    lines.append("")
    lines.append("## Fördelning per domstol (avgörande instans)")
    lines.append(md_table(["Domstol", "Antal"], [[k or "okänt", v] for k, v in agg["by_court"].items()]))
    lines.append("")
    lines.append("## Ursprunglig tingsrätt (första instäns)")
    lines.append(md_table(["Tingsrätt", "Antal"], [[k or "okänt", v] for k, v in agg["by_origin_tingsratt"].items()]))
    lines.append("")
    lines.append("## Mål per år (datum för aktuell domstols dom)")
    lines.append(md_table(["År", "Antal"], list(agg["by_year"].items())))
    lines.append("")
    lines.append("## Utfall per part")
    lines.append(md_table(["Utfall per part", "Antal"], list(tr_winners(agg["winners"]).items())))
    lines.append("")
    lines.append("## Detaljerat utfall (vårdnad + boende + umgänge)")
    lines.append(md_table(["Utfall", "Antal"], list(agg["outcome_detail"].items())))
    lines.append("")
    lines.append("## Övergångsmatris – rättslig vårdnad (före → efter)")
    lines.append(md_table(["Övergång", "Antal"], list(tr_legal_transitions(agg["custody_legal_transitions"]).items())))
    lines.append("")
    lines.append("## Övergångsmatris – boende (före → efter)")
    lines.append(md_table(["Övergång", "Antal"], list(tr_residence_transitions(agg["custody_residence_transitions"]).items())))
    lines.append("")
    lines.append("## Antal barn per mål")
    lines.append(md_table(["Antal barn", "Mål"], list(agg["n_children_distribution"].items())))
    s = agg["n_children_stats"]
    lines.append("")
    lines.append(f"Snitt: {s.get('mean')}  Median: {s.get('median')}  Min/Max: {s.get('min')}–{s.get('max')}")
    lines.append("")
    lines.append("## Barnens kön")
    lines.append(md_table(["Kön", "Antal"], list(tr_gender(agg["child_gender_distribution"]).items())))
    lines.append("")
    lines.append("## Barnens ålder (alla barn, år)")
    s = agg["child_age_stats"]
    lines.append(f"n={s.get('n')}  Snitt: {s.get('mean')}  Median: {s.get('median')}  Min/Max: {s.get('min')}–{s.get('max')}")
    lines.append("")
    lines.append("### Histogram 5-årsintervall")
    lines.append(md_table(["Ålder", "Antal"], list(agg["child_age_histogram_5y"].items())))
    lines.append("")
    lines.append("## Föräldrarnas ålder")
    s = agg["mother_age_stats"]
    lines.append(f"**Mödrar** n={s.get('n')}  Snitt: {s.get('mean')}  Median: {s.get('median')}  Min/Max: {s.get('min')}–{s.get('max')}")
    lines.append(md_table(["Ålder", "Antal"], list(agg["mother_age_histogram_5y"].items())))
    lines.append("")
    s = agg["father_age_stats"]
    lines.append(f"**Fäder** n={s.get('n')}  Snitt: {s.get('mean')}  Median: {s.get('median')}  Min/Max: {s.get('min')}–{s.get('max')}")
    lines.append(md_table(["Ålder", "Antal"], list(agg["father_age_histogram_5y"].items())))
    lines.append("")
    lines.append("## Frekvens av nyckelfaktorer")
    lines.append(md_table(["Faktor", "Antal mål"], list(tr_factors(agg["key_factor_frequency"]).items())))
    lines.append("")
    lines.append("## Processuella drag")
    lines.append(md_table(["Egenskap", "Värden"], [
        ["Socialtjänst inblandad", json.dumps(tr_bool_dict(agg["social_services_involved"]), ensure_ascii=False)],
        ["Vårdnadsutredning utförd", json.dumps(tr_bool_dict(agg["vårdnadsutredning_performed"]), ensure_ascii=False)],
        ["Barnet hört", json.dumps(tr_bool_dict(agg["child_was_heard"]), ensure_ascii=False)],
    ]))
    lines.append("")
    lines.append("## Hovrättens utfall i förhållande till tingsrätten")
    lines.append(md_table(["Utfall", "Antal"], list(tr_appeal(agg["appeal_outcomes_hovratt"]).items())))
    lines.append("")
    lines.append("## Rättegångskostnader (rapporterade rättshjälpsbelopp, SEK)")
    s = agg["legal_costs_sek_stats"]
    lines.append(f"n={s.get('n')}  Snitt: {s.get('mean')}  Median: {s.get('median')}  Min/Max: {s.get('min')}–{s.get('max')}")
    lines.append("")
    lines.append("## Mål flaggade för manuell granskning")
    if agg["low_confidence_cases"]:
        for cid in agg["low_confidence_cases"]:
            lines.append(f"- {cid}")
    else:
        lines.append("_Inga._")
    lines.append("")
    lines.append("## Sammanfattande beskrivning")
    lines.append("")
    lines.append(_narrative_sv(agg))
    lines.append("")
    return "\n".join(lines)


def _narrative_sv(agg: dict) -> str:
    total = agg["total_cases"]
    if total == 0:
        return "_Inga mål bearbetade ännu._"
    winners = tr_winners(agg["winners"])
    factors = tr_factors(agg["key_factor_frequency"])
    appeal = tr_appeal(agg["appeal_outcomes_hovratt"])
    parts = [
        f"Datasetet omfattar {total} mål, övervägande hovrättsavgöranden. ",
        "Utfallen fördelar sig enligt följande: ",
        ", ".join(f"{k}={v}" for k, v in winners.items() if k),
        ". ",
    ]
    if factors:
        top = list(factors.items())[:5]
        parts.append("De vanligaste motiveringarna i domarna rör " +
                     ", ".join(f"{k} ({v})" for k, v in top) + ". ")
    if appeal:
        parts.append("I de hovrättsavgöranden som granskats fördelar sig utfallen " +
                     ", ".join(f"{k}={v}" for k, v in appeal.items() if k) + ". ")
    parts.append(
        "Samarbetssvårigheter, barnets bästa och uppgifter om våld eller missbruk "
        "återkommer som centrala teman. För djupare analys, se per-fall-JSON i samma mapp."
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Per-case Swedish summary (max 150 ord)
# ---------------------------------------------------------------------------


def _truncate_words(text: str, n: int = 150) -> str:
    words = (text or "").split()
    if len(words) <= n:
        return text or ""
    return " ".join(words[:n]).rstrip(",.;:") + " …"


def case_short_summary(c: dict) -> str:
    return _truncate_words(c.get("summary") or "", 150)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------


def _to_chart_pairs(d: dict) -> tuple[list[str], list[int]]:
    if not d:
        return [], []
    items = list(d.items())
    return [str(k) for k, _ in items], [int(v) for _, v in items]


def _case_for_js(c: dict) -> dict:
    children = c.get("children") or []
    parents = c.get("parents") or []

    def pa(role):
        for p in parents:
            if isinstance(p, dict) and p.get("role") == role:
                a = p.get("age_at_ruling")
                if isinstance(a, (int, float)):
                    return int(a)
        return None

    gmap = {"male": "pojke", "female": "flicka"}
    cb = c.get("custody_before") or {}
    ca = c.get("custody_after") or {}
    return {
        "id": c.get("case_id", ""),
        "level": SV_LEVEL.get(c.get("court_level"), c.get("court_level") or "okänt"),
        "court": c.get("court") or "okänt",
        "origin": (c.get("lower_court") if c.get("court_level") == "hovrätt" else c.get("court")) or "okänt",
        "year": (c.get("ruling_date") or "")[:4] or "okänt",
        "winner": SV_WINNER.get(c.get("winner"), "okänt"),
        "legal_before": SV_LEGAL.get(cb.get("legal_custody"), "okänt"),
        "legal_after": SV_LEGAL.get(ca.get("legal_custody"), "okänt"),
        "res_before": SV_RESIDENCE.get(cb.get("residence"), "okänt"),
        "res_after": SV_RESIDENCE.get(ca.get("residence"), "okänt"),
        "n_children": c.get("n_children") if isinstance(c.get("n_children"), int) else None,
        "child_ages": _ages(children),
        "child_genders": [
            gmap.get(ch.get("gender"), "okänt")
            for ch in children if isinstance(ch, dict)
        ],
        "mother_age": pa("mother"),
        "father_age": pa("father"),
        "factors": [SV_FACTORS.get(f, f) for f in (c.get("key_factors") or [])],
        "soc": SV_BOOL.get(c.get("social_services_involved"), "okänt"),
        "vu": SV_BOOL.get(c.get("vårdnadsutredning_performed"), "okänt"),
        "heard": SV_BOOL.get(c.get("child_was_heard"), "okänt"),
        "appeal": SV_APPEAL.get(c.get("appeal_outcome"), "okänt") if c.get("court_level") == "hovrätt" else None,
        "cost": c.get("legal_costs_total_sek") if isinstance(c.get("legal_costs_total_sek"), (int, float)) else None,
        "outcome": _outcome_label(c),
        "access_score": _parental_access_score(c),
      }


def render_html(agg: dict, cases: list[dict], ui: dict) -> str:
    charts = {
        "court_level": _to_chart_pairs(tr_court_level(agg["by_court_level"])),
        "court": _to_chart_pairs({(k or "okänt"): v for k, v in agg["by_court"].items()}),
        "origin_tingsratt": _to_chart_pairs({(k or "okänt"): v for k, v in agg["by_origin_tingsratt"].items()}),
        "year": _to_chart_pairs(agg["by_year"]),
        "winners": _to_chart_pairs(tr_winners(agg["winners"])),
        "legal_before": _to_chart_pairs(_collapse_transitions(agg["custody_legal_transitions"], "before", SV_LEGAL)),
        "legal_after": _to_chart_pairs(_collapse_transitions(agg["custody_legal_transitions"], "after", SV_LEGAL)),
        "residence_before": _to_chart_pairs(_collapse_transitions(agg["custody_residence_transitions"], "before", SV_RESIDENCE)),
        "residence_after": _to_chart_pairs(_collapse_transitions(agg["custody_residence_transitions"], "after", SV_RESIDENCE)),
        "n_children": _to_chart_pairs({str(k): v for k, v in agg["n_children_distribution"].items()}),
        "child_age": _to_chart_pairs(agg["child_age_histogram_5y"]),
        "child_gender": _to_chart_pairs(tr_gender(agg["child_gender_distribution"])),
        "mother_age": _to_chart_pairs(agg["mother_age_histogram_5y"]),
        "father_age": _to_chart_pairs(agg["father_age_histogram_5y"]),
        "factors": _to_chart_pairs(tr_factors(agg["key_factor_frequency"])),
        "soc": _to_chart_pairs(tr_bool_dict(agg["social_services_involved"])),
        "vu": _to_chart_pairs(tr_bool_dict(agg["vårdnadsutredning_performed"])),
        "heard": _to_chart_pairs(tr_bool_dict(agg["child_was_heard"])),
        "appeal": _to_chart_pairs(tr_appeal(agg["appeal_outcomes_hovratt"])),
        "outcome": _to_chart_pairs(agg["outcome_detail"]),
        "access_score": _to_chart_pairs({str(k): v for k, v in agg["access_score_distribution"].items()}),
      }
    data_json = json.dumps(charts, ensure_ascii=False)
    cases_for_js = [_case_for_js(c) for c in cases]
    cases_json = json.dumps(cases_for_js, ensure_ascii=False)
    ui_json = json.dumps(ui, ensure_ascii=False)

    page_title = ui["page"]["title"]
    page_subtitle = ui["page"]["subtitle"].format(total_cases=agg["total_cases"])
    nav = ui["nav"]
    sections = ui["sections"]
    charts_ui = ui["charts"]
    kpi_ui = ui["kpi"]
    filter_ui = ui["filter"]
    visibility = ui.get("visibility", {})

    def is_visible(group: str, key: str, default: bool = True) -> bool:
      bucket = visibility.get(group)
      if isinstance(bucket, dict) and key in bucket:
        return bool(bucket.get(key))
      return default

    s_child = agg["child_age_stats"]
    s_mother = agg["mother_age_stats"]
    s_father = agg["father_age_stats"]
    s_costs = agg["legal_costs_sek_stats"]
    s_kids = agg["n_children_stats"]

    appendix_items = []
    for c in sorted(cases, key=lambda x: x.get("case_id") or ""):
        cid = c.get("case_id", "")
        court = c.get("court", "")
        date = c.get("ruling_date", "")
        access_score = _parental_access_score(c)
        access_label = f"{access_score:+d}" if access_score is not None else "okänt"
        n_kids = c.get("n_children", "?")
        summary = case_short_summary(c)
        appendix_items.append(
            f'        <article class="case">\n'
            f'          <header>\n'
            f'            <h3 id="{escape(cid)}">{escape(cid)}</h3>\n'
            f'            <div class="meta">{escape(court)} · {escape(date)} · {n_kids} barn · kontaktbalans: <strong>{escape(access_label)}</strong></div>\n'
            f'          </header>\n'
            f'          <p>{escape(summary)}</p>\n'
            f'        </article>'
        )
    appendix_html = "\n".join(appendix_items)

    cost_n = s_costs.get("n", 0)
    cost_mean = _format_sek(s_costs.get("mean")) if cost_n else "–"
    cost_median = _format_sek(s_costs.get("median")) if cost_n else "–"
    cost_max = _format_sek(s_costs.get("max")) if cost_n else "–"

    filter_options = "\n".join(
      f'            <option value="{escape(name or "okänt")}">{escape(name or "okänt")} ({n})</option>'
      for name, n in agg["by_origin_tingsratt"].items()
    )

    nav_order = [
      "nyckeltal", "filter", "instans", "utfall", "vardnad",
      "barn", "foraldrar", "faktorer", "process", "bilaga",
    ]
    nav_html = "\n".join(
      f'    <a href="#{sid}">{escape(nav[sid])}</a>'
      for sid in nav_order
      if is_visible("sections", sid)
    )

    nyckeltal_kpis = "\n".join(x for x in [
      f'        <div class="kpi"><div class="num" id="kpi_total">{agg["total_cases"]}</div><div class="lbl">{escape(kpi_ui["total"])}</div></div>' if is_visible("kpi", "total") else "",
      f'        <div class="kpi"><div class="num" id="kpi_kids_n">{s_kids.get("n", 0)}</div><div class="lbl">{escape(kpi_ui["kids_n"])}</div></div>' if is_visible("kpi", "kids_n") else "",
      f'        <div class="kpi"><div class="num" id="kpi_children">{s_child.get("n", 0)}</div><div class="lbl">{escape(kpi_ui["children"])}</div></div>' if is_visible("kpi", "children") else "",
      f'        <div class="kpi"><div class="num" id="kpi_child_age">{s_child.get("mean", "–")}</div><div class="lbl">{escape(kpi_ui["child_age"])}</div></div>' if is_visible("kpi", "child_age") else "",
      f'        <div class="kpi"><div class="num" id="kpi_mother_age">{s_mother.get("mean", "–")}</div><div class="lbl">{escape(kpi_ui["mother_age"])}</div></div>' if is_visible("kpi", "mother_age") else "",
      f'        <div class="kpi"><div class="num" id="kpi_father_age">{s_father.get("mean", "–")}</div><div class="lbl">{escape(kpi_ui["father_age"])}</div></div>' if is_visible("kpi", "father_age") else "",
    ] if x)

    instans_cards = "\n".join(x for x in [
      f'        <div class="card"><h3>{escape(charts_ui["court_level"])}</h3><div class="canvas-wrap"><canvas id="ch_court_level"></canvas></div></div>' if is_visible("charts", "court_level") else "",
      f'        <div class="card"><h3>{escape(charts_ui["year"])}</h3><div class="canvas-wrap"><canvas id="ch_year"></canvas></div></div>' if is_visible("charts", "year") else "",
      f'        <div class="card"><h3>{escape(charts_ui["court"])}</h3><div class="canvas-wrap" style="height:360px"><canvas id="ch_court"></canvas></div></div>' if is_visible("charts", "court") else "",
      f'        <div class="card wide"><h3>{escape(charts_ui["origin_tingsratt"])}</h3><div class="canvas-wrap" style="height:__ORIGIN_H__px"><canvas id="ch_origin_tingsratt"></canvas></div></div>' if is_visible("charts", "origin_tingsratt") else "",
    ] if x)

    utfall_cards = "\n".join(x for x in [
      f'        <div class="card"><h3>{escape(charts_ui["winners"])}</h3><div class="canvas-wrap"><canvas id="ch_winners"></canvas></div></div>' if is_visible("charts", "winners") else "",
      f'        <div class="card"><h3>{escape(charts_ui["appeal"])}</h3><div class="canvas-wrap"><canvas id="ch_appeal"></canvas></div></div>' if is_visible("charts", "appeal") else "",
      f'        <div class="card wide"><h3>{escape(charts_ui["outcome"])}</h3><div class="canvas-wrap" style="height:__OUTCOME_H__px"><canvas id="ch_outcome"></canvas></div></div>' if is_visible("charts", "outcome") else "",
      (
        f'        <div class="card">'
        f'<h3>{escape(charts_ui["access_score"])}</h3>'
        f'<p style="font-size:.8rem;color:var(--muted);margin:.2rem 0 .6rem 0">'
        f'{escape(charts_ui.get("access_score_note", ""))}</p>'
        f'<div class="canvas-wrap"><canvas id="ch_access_score"></canvas></div>'
        f'<div class="stats-row"><span>n=<strong id="kpi_as_n">–</strong></span>'
        f'<span>Snitt: <strong id="kpi_as_mean">–</strong></span>'
        f'<span>Median: <strong id="kpi_as_median">–</strong></span></div>'
        f'</div>'
      ) if is_visible("charts", "access_score") else "",
    ] if x)

    vardnad_cards = "\n".join(x for x in [
      f'        <div class="card"><h3>{escape(charts_ui["legal_before"])}</h3><div class="canvas-wrap"><canvas id="ch_legal_before"></canvas></div></div>' if is_visible("charts", "legal_before") else "",
      f'        <div class="card"><h3>{escape(charts_ui["legal_after"])}</h3><div class="canvas-wrap"><canvas id="ch_legal_after"></canvas></div></div>' if is_visible("charts", "legal_after") else "",
      f'        <div class="card"><h3>{escape(charts_ui["residence_before"])}</h3><div class="canvas-wrap"><canvas id="ch_residence_before"></canvas></div></div>' if is_visible("charts", "residence_before") else "",
      f'        <div class="card"><h3>{escape(charts_ui["residence_after"])}</h3><div class="canvas-wrap"><canvas id="ch_residence_after"></canvas></div></div>' if is_visible("charts", "residence_after") else "",
    ] if x)

    barn_cards = "\n".join(x for x in [
      (
        f'        <div class="card"><h3>{escape(charts_ui["n_children"])}</h3><div class="canvas-wrap"><canvas id="ch_n_children"></canvas></div>'
        f'<div class="stats-row"><span>Snitt: <strong>{s_kids.get("mean", "–")}</strong></span><span>Median: <strong>{s_kids.get("median", "–")}</strong></span><span>Min/Max: <strong>{s_kids.get("min", "–")}–{s_kids.get("max", "–")}</strong></span></div></div>'
      ) if is_visible("charts", "n_children") else "",
      f'        <div class="card"><h3>{escape(charts_ui["child_gender"])}</h3><div class="canvas-wrap"><canvas id="ch_child_gender"></canvas></div></div>' if is_visible("charts", "child_gender") else "",
      (
        f'        <div class="card"><h3>{escape(charts_ui["child_age"])}</h3><div class="canvas-wrap"><canvas id="ch_child_age"></canvas></div>'
        f'<div class="stats-row"><span>n=<strong>{s_child.get("n", 0)}</strong></span><span>Snitt: <strong>{s_child.get("mean", "–")}</strong></span><span>Median: <strong>{s_child.get("median", "–")}</strong></span><span>Min/Max: <strong>{s_child.get("min", "–")}–{s_child.get("max", "–")}</strong></span></div></div>'
      ) if is_visible("charts", "child_age") else "",
    ] if x)

    foraldrar_cards = "\n".join(x for x in [
      (
        f'        <div class="card"><h3>{escape(charts_ui["mother_age"])}</h3><div class="canvas-wrap"><canvas id="ch_mother_age"></canvas></div>'
        f'<div class="stats-row"><span>n=<strong>{s_mother.get("n", 0)}</strong></span><span>Snitt: <strong>{s_mother.get("mean", "–")}</strong></span><span>Median: <strong>{s_mother.get("median", "–")}</strong></span><span>Min/Max: <strong>{s_mother.get("min", "–")}–{s_mother.get("max", "–")}</strong></span></div></div>'
      ) if is_visible("charts", "mother_age") else "",
      (
        f'        <div class="card"><h3>{escape(charts_ui["father_age"])}</h3><div class="canvas-wrap"><canvas id="ch_father_age"></canvas></div>'
        f'<div class="stats-row"><span>n=<strong>{s_father.get("n", 0)}</strong></span><span>Snitt: <strong>{s_father.get("mean", "–")}</strong></span><span>Median: <strong>{s_father.get("median", "–")}</strong></span><span>Min/Max: <strong>{s_father.get("min", "–")}–{s_father.get("max", "–")}</strong></span></div></div>'
      ) if is_visible("charts", "father_age") else "",
    ] if x)

    faktorer_card = (
      f'      <div class="card"><h3>{escape(charts_ui["factors"])}</h3><div class="canvas-wrap" style="height:420px"><canvas id="ch_factors"></canvas></div></div>'
      if is_visible("charts", "factors") else ""
    )

    process_cards = "\n".join(x for x in [
      f'        <div class="card"><h3>{escape(charts_ui["soc"])}</h3><div class="canvas-wrap"><canvas id="ch_soc"></canvas></div></div>' if is_visible("charts", "soc") else "",
      f'        <div class="card"><h3>{escape(charts_ui["vu"])}</h3><div class="canvas-wrap"><canvas id="ch_vu"></canvas></div></div>' if is_visible("charts", "vu") else "",
      f'        <div class="card"><h3>{escape(charts_ui["heard"])}</h3><div class="canvas-wrap"><canvas id="ch_heard"></canvas></div></div>' if is_visible("charts", "heard") else "",
    ] if x)

    process_kpis = "\n".join(x for x in [
      f'        <div class="kpi"><div class="num" id="kpi_cost_n">{cost_n}</div><div class="lbl">{escape(kpi_ui["cost_n"])}</div></div>' if is_visible("kpi", "cost_n") else "",
      f'        <div class="kpi"><div class="num" id="kpi_cost_mean">{cost_mean}</div><div class="lbl">{escape(kpi_ui["cost_mean"])}</div></div>' if is_visible("kpi", "cost_mean") else "",
      f'        <div class="kpi"><div class="num" id="kpi_cost_median">{cost_median}</div><div class="lbl">{escape(kpi_ui["cost_median"])}</div></div>' if is_visible("kpi", "cost_median") else "",
      f'        <div class="kpi"><div class="num" id="kpi_cost_max">{cost_max}</div><div class="lbl">{escape(kpi_ui["cost_max"])}</div></div>' if is_visible("kpi", "cost_max") else "",
    ] if x)

    css = """
    :root {
      --bg: #f7f7f5;
      --card: #ffffff;
      --ink: #1f2937;
      --muted: #6b7280;
      --accent: #2563eb;
      --border: #e5e7eb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.55;
    }
    header.page {
      background: linear-gradient(135deg, #1e3a8a, #2563eb);
      color: #fff;
      padding: 2.5rem 1.5rem;
    }
    header.page h1 { margin: 0 0 .3rem 0; font-size: 1.9rem; }
    header.page p { margin: 0; opacity: .9; }
    nav {
      background: var(--card);
      border-bottom: 1px solid var(--border);
      padding: .6rem 1.5rem;
      position: sticky; top: 0;
      display: flex; gap: 1rem; flex-wrap: wrap;
      z-index: 10;
    }
    nav a { color: var(--accent); text-decoration: none; font-size: .9rem; }
    nav a:hover { text-decoration: underline; }
    main { max-width: 1200px; margin: 0 auto; padding: 1.5rem; }
    section { margin-bottom: 2rem; }
    section > h2 { border-bottom: 2px solid var(--accent); padding-bottom: .3rem; margin-top: 2.5rem; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 1rem;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.2rem;
      box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .card.wide { grid-column: 1 / -1; }
    .card h3 { margin: 0 0 .5rem 0; font-size: 1.05rem; }
    .card .canvas-wrap { position: relative; height: 280px; }
    .filter-row {
      display: flex; flex-wrap: wrap; gap: 1rem; align-items: flex-start;
    }
    .filter-row select {
      font-family: inherit; font-size: .9rem; padding: .3rem;
      border: 1px solid var(--border); border-radius: 6px; background: #fff;
    }
    .filter-controls {
      display: flex; flex-direction: column; gap: .6rem; min-width: 160px;
    }
    .filter-controls label { font-size: .9rem; }
    .filter-controls button {
      padding: .4rem .8rem; border: 1px solid var(--accent);
      background: #fff; color: var(--accent); border-radius: 6px;
      cursor: pointer; font-size: .9rem;
    }
    .filter-controls button:hover { background: var(--accent); color: #fff; }
    .stats-row {
      display: flex; gap: 1rem; flex-wrap: wrap; margin-top: .6rem;
      font-size: .85rem; color: var(--muted);
    }
    .stats-row span strong { color: var(--ink); }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-top: 1rem;
    }
    .kpi {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem;
      text-align: center;
    }
    .kpi .num { font-size: 2rem; font-weight: 700; color: var(--accent); }
    .kpi .lbl { font-size: .85rem; color: var(--muted); margin-top: .2rem; }
    article.case {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem 1.2rem;
      margin-bottom: .8rem;
    }
    article.case h3 { margin: 0 0 .2rem 0; font-size: 1rem; font-family: ui-monospace, monospace; }
    article.case .meta { font-size: .85rem; color: var(--muted); margin-bottom: .5rem; }
    article.case p { margin: 0; font-size: .92rem; }
    footer { text-align: center; padding: 2rem 1rem; color: var(--muted); font-size: .85rem; }
    @media (max-width: 600px) {
      header.page { padding: 1.5rem 1rem; }
      header.page h1 { font-size: 1.4rem; }
    }
    """

    js = r"""
    const ALL = __CASES__;
    const UI = __UI__;
    const PALETTE = [
      '#2563eb','#db2777','#059669','#d97706','#7c3aed','#0891b2',
      '#dc2626','#65a30d','#ea580c','#0d9488','#9333ea','#ca8a04',
      '#1d4ed8','#be185d','#15803d','#b45309','#6d28d9','#0e7490'
    ];
    // Stabila färger per etikett — samma kategori har alltid samma färg
    // i alla diagram (mor=blå, far=rosa, gemensam=grön, osv.).
    const LABEL_COLOR = {
      // Vinnare
      'mor': '#2563eb', 'far': '#db2777', 'båda': '#059669',
      'ingen': '#6b7280', 'delvis mor': '#60a5fa', 'delvis far': '#f472b6',
      'ej tillämpligt': '#9ca3af',
      // Vårdnad
      'gemensam': '#059669', 'ensam mor': '#2563eb', 'ensam far': '#db2777',
      'oklart': '#9ca3af',
      // Boende
      'hos mor': '#2563eb', 'hos far': '#db2777', 'växelvis': '#059669',
      'annat': '#7c3aed',
      // Kön
      'pojke': '#2563eb', 'flicka': '#db2777',
      // Bool
      'ja': '#059669', 'nej': '#dc2626',
      // Instans
      'tingsrätt': '#2563eb', 'hovrätt': '#db2777', 'högsta domstolen': '#7c3aed',
      // Hovrättens utfall
      'fastställd': '#059669', 'ändrad': '#d97706', 'delvis ändrad': '#fbbf24',
      'återförvisad': '#7c3aed', 'förlikning': '#0891b2',
      // Generiska
      'okänt': '#9ca3af',
    };
    function colorFor(label, fallbackIdx) {
      return LABEL_COLOR[label] || PALETTE[fallbackIdx % PALETTE.length];
    }
    function colorForScore(scoreStr) {
      const s = parseInt(scoreStr, 10);
      if (isNaN(s)) return '#9ca3af';
      if (s < -60) return '#2563eb';   // strong mother side — blue
      if (s < -10) return '#60a5fa';   // moderate mother side — light blue
      if (s <= 10) return '#059669';   // neutral / alternating — green
      if (s <= 60) return '#f472b6';   // moderate father side — light pink
      return '#db2777';                 // strong father side — pink
    }
    const inst = {};
    const CHART_META = {
      court_level:      {type: 'pie'},
      court:            {type: 'barh'},
      origin_tingsratt: {type: 'barh'},
      year:             {type: 'line', sort: 'label'},
      winners:          {type: 'pie'},
      legal_before:     {type: 'pie'},
      legal_after:      {type: 'pie'},
      residence_before: {type: 'pie'},
      residence_after:  {type: 'pie'},
      n_children:       {type: 'bar', sort: 'numeric_label'},
      child_age:        {type: 'bar', sort: 'numeric_label'},
      child_gender:     {type: 'pie'},
      mother_age:       {type: 'bar', sort: 'numeric_label'},
      father_age:       {type: 'bar', sort: 'numeric_label'},
      factors:          {type: 'barh'},
      soc:              {type: 'pie'},
      vu:               {type: 'pie'},
      heard:            {type: 'pie'},
      appeal:           {type: 'pie'},
      outcome:          {type: 'barh'},
      access_score:     {type: 'bar', sort: 'numeric_label'},
    };

    function fmt(tpl, vars) {
      return String(tpl || '').replace(/\{(\w+)\}/g, (_, k) => (
        Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : ''
      ));
    }

    function tally(items, keyFn) {
      const m = new Map();
      for (const x of items) {
        const k = keyFn(x);
        if (k == null) continue;
        m.set(k, (m.get(k) || 0) + 1);
      }
      return m;
    }
    function histMap(values, w) {
      const m = new Map();
      for (const v of values) {
        if (v == null) continue;
        const lo = Math.floor(v / w) * w;
        const k = lo + '-' + (lo + w - 1);
        m.set(k, (m.get(k) || 0) + 1);
      }
      return m;
    }
    function sortPairs(map, mode) {
      const arr = [...map.entries()];
      if (mode === 'label') arr.sort((a, b) => String(a[0]).localeCompare(String(b[0])));
      else if (mode === 'numeric_label') arr.sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
      else arr.sort((a, b) => b[1] - a[1]);
      return arr;
    }

    function aggregate(cases) {
      const m = {
        court_level:      tally(cases, c => c.level),
        court:            tally(cases, c => c.court),
        origin_tingsratt: tally(cases, c => c.origin),
        year:             tally(cases, c => c.year),
        winners:          tally(cases, c => c.winner),
        legal_before:     tally(cases, c => c.legal_before),
        legal_after:      tally(cases, c => c.legal_after),
        residence_before: tally(cases, c => c.res_before),
        residence_after:  tally(cases, c => c.res_after),
        n_children:       tally(cases.filter(c => c.n_children != null), c => String(c.n_children)),
        child_age:        histMap(cases.flatMap(c => c.child_ages || []), 5),
        child_gender:     tally(cases.flatMap(c => c.child_genders || []), x => x),
        mother_age:       histMap(cases.map(c => c.mother_age), 5),
        father_age:       histMap(cases.map(c => c.father_age), 5),
        factors:          tally(cases.flatMap(c => c.factors || []), x => x),
        soc:              tally(cases, c => c.soc),
        vu:               tally(cases, c => c.vu),
        heard:            tally(cases, c => c.heard),
        appeal:           tally(cases.filter(c => c.appeal), c => c.appeal),
        outcome:          tally(cases, c => c.outcome),
        access_score:     tally(cases.filter(c => c.access_score != null), c => String(c.access_score)),
      };
      const out = {};
      for (const k in m) {
        const sorted = sortPairs(m[k], CHART_META[k].sort);
        out[k] = { labels: sorted.map(x => x[0]), data: sorted.map(x => x[1]) };
      }
      return out;
    }

    function destroyAll() {
      for (const k in inst) { inst[k].destroy(); delete inst[k]; }
    }

    function chartOptions(meta, isCompare) {
      const horizontal = meta.type === 'barh';
      const isPieAsBar = isCompare && meta.type === 'pie';
      return {
        responsive: true, maintainAspectRatio: false,
        indexAxis: horizontal ? 'y' : 'x',
        plugins: {
          legend: { display: isCompare || meta.type === 'pie', position: 'bottom' },
          tooltip: { mode: 'index', intersect: false }
        },
        scales: meta.type === 'pie' && !isCompare
          ? {}
          : (horizontal
              ? { x: { beginAtZero: true, ticks: { precision: 0 } } }
              : { y: { beginAtZero: true, ticks: { precision: 0 } } })
      };
    }

    function renderChart(id, key, datasets, labels, isCompare) {
      const meta = CHART_META[key];
      const el = document.getElementById(id);
      if (!el) return;
      let type = meta.type;
      if (isCompare && type === 'pie') type = 'bar';
      if (type === 'barh') type = 'bar';
      inst[id] = new Chart(el, {
        type: type === 'line' ? 'line' : type,
        data: { labels, datasets },
        options: chartOptions(meta, isCompare)
      });
    }

    function renderSingle(filtered) {
      const agg = aggregate(filtered);
      for (const key in CHART_META) {
        const meta = CHART_META[key];
        const { labels, data } = agg[key];
        let datasets;
        if (key === 'access_score') {
          datasets = [{ label: UI.js_labels.count_series, data, backgroundColor: labels.map(l => colorForScore(l)) }];
        } else if (meta.type === 'pie') {
          datasets = [{ data, backgroundColor: labels.map((l, i) => colorFor(l, i)) }];
        } else if (meta.type === 'line') {
          datasets = [{
            label: UI.js_labels.cases_series, data,
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37,99,235,0.15)',
            fill: true, tension: 0.25, pointRadius: 4
          }];
        } else if (meta.type === 'barh') {
          datasets = [{ label: UI.js_labels.count_series, data, backgroundColor: '#db2777' }];
        } else {
          // bar — färglägg per etikett om vi har stabil färg, annars enhetlig accent
          const colors = labels.map((l, i) => LABEL_COLOR[l] || '#2563eb');
          datasets = [{ label: UI.js_labels.count_series, data, backgroundColor: colors }];
        }
        renderChart('ch_' + key, key, datasets, labels, false);
      }
    }

    function renderCompare(courts) {
      const aggs = courts.map(c => ({
        court: c,
        agg: aggregate(ALL.filter(x => x.origin === c)),
      }));
      for (const key in CHART_META) {
        const meta = CHART_META[key];
        const labelSet = new Set();
        aggs.forEach(({ agg }) => agg[key].labels.forEach(l => labelSet.add(l)));
        let labels = [...labelSet];
        if (meta.sort === 'label') labels.sort((a, b) => String(a).localeCompare(String(b)));
        else if (meta.sort === 'numeric_label') labels.sort((a, b) => parseInt(a) - parseInt(b));
        const datasets = aggs.map(({ court, agg }, idx) => {
          const map = new Map(agg[key].labels.map((l, i) => [l, agg[key].data[i]]));
          const color = PALETTE[idx % PALETTE.length];
          if (meta.type === 'line') {
            return {
              label: court,
              data: labels.map(l => map.get(l) || 0),
              borderColor: color,
              backgroundColor: color + '33',
              fill: false, tension: 0.25, pointRadius: 3
            };
          }
          return {
            label: court,
            data: labels.map(l => map.get(l) || 0),
            backgroundColor: color,
          };
        });
        renderChart('ch_' + key, key, datasets, labels, true);
      }
    }

    const SEK_FMT = new Intl.NumberFormat('sv-SE', {
      style: 'currency', currency: 'SEK', maximumFractionDigits: 0
    });
    function fmtSek(n) { return n == null ? '–' : SEK_FMT.format(Math.round(n)); }
    function mean(values) {
      const v = values.filter(x => x != null);
      if (!v.length) return null;
      return v.reduce((a, b) => a + b, 0) / v.length;
    }
    function median(values) {
      const v = values.filter(x => x != null).sort((a, b) => a - b);
      if (!v.length) return null;
      const m = Math.floor(v.length / 2);
      return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
    }

    function updateKPIs(filtered) {
      const childAges = filtered.flatMap(c => c.child_ages || []);
      const motherAges = filtered.map(c => c.mother_age).filter(x => x != null);
      const fatherAges = filtered.map(c => c.father_age).filter(x => x != null);
      const costs = filtered.map(c => c.cost).filter(x => x != null);
      const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
      set('kpi_total', filtered.length);
      set('kpi_kids_n', filtered.filter(c => c.n_children != null).length);
      set('kpi_children', childAges.length);
      set('kpi_child_age', childAges.length ? (Math.round(mean(childAges) * 10) / 10) : '–');
      set('kpi_mother_age', motherAges.length ? (Math.round(mean(motherAges) * 10) / 10) : '–');
      set('kpi_father_age', fatherAges.length ? (Math.round(mean(fatherAges) * 10) / 10) : '–');
      set('kpi_cost_n', costs.length);
      set('kpi_cost_mean', costs.length ? fmtSek(mean(costs)) : '–');
      set('kpi_cost_median', costs.length ? fmtSek(median(costs)) : '–');
      set('kpi_cost_max', costs.length ? fmtSek(Math.max.apply(null, costs)) : '–');
      const asValues = filtered.map(c => c.access_score).filter(x => x != null);
      set('kpi_as_n', asValues.length);
      set('kpi_as_mean', asValues.length ? (Math.round(mean(asValues) * 10) / 10) : '–');
      set('kpi_as_median', asValues.length ? median(asValues) : '–');
    }

    function applyFilter() {
      const sel = document.getElementById('filter_courts');
      const compare = document.getElementById('filter_compare').checked;
      const courts = [...sel.selectedOptions].map(o => o.value);
      destroyAll();
      let filtered = ALL;
      let label = '';
      if (compare && courts.length >= 2) {
        filtered = ALL.filter(c => courts.includes(c.origin));
        renderCompare(courts);
        const counts = courts.map(c => ALL.filter(x => x.origin === c).length);
        label = fmt(UI.js_labels.compare, {
          n_courts: courts.length,
          parts: counts.join(' + '),
          total: filtered.length,
        });
      } else {
        if (courts.length > 0) {
          filtered = ALL.filter(c => courts.includes(c.origin));
          label = fmt(UI.js_labels.show_filtered, {
            total: filtered.length,
            courts: courts.join(', '),
          });
        } else {
          label = fmt(UI.js_labels.show_all, { total: ALL.length });
        }
        renderSingle(filtered);
      }
      document.getElementById('filter_status').textContent = label;
      updateKPIs(filtered);
    }

    function clearFilter() {
      const sel = document.getElementById('filter_courts');
      [...sel.options].forEach(o => o.selected = false);
      document.getElementById('filter_compare').checked = false;
      applyFilter();
    }

    document.addEventListener('DOMContentLoaded', () => {
      document.getElementById('filter_courts').addEventListener('change', applyFilter);
      document.getElementById('filter_compare').addEventListener('change', applyFilter);
      document.getElementById('filter_clear').addEventListener('click', clearFilter);
      applyFilter();
    });
    """.replace("__CASES__", cases_json).replace("__UI__", ui_json)

    html = f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{escape(page_title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>{css}</style>
</head>
<body>
  <header class="page">
    <h1>{escape(page_title)}</h1>
    <p>{escape(page_subtitle)}</p>
  </header>

  <nav>
{nav_html}
  </nav>

  <main>
{f'''    <section id="nyckeltal">
      <h2>{escape(sections['nyckeltal']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['nyckeltal']['description'])}</p>
      <div class="kpi-grid">
{nyckeltal_kpis}
      </div>
    </section>''' if is_visible("sections", "nyckeltal") else ''}

{f'''    <section id="filter">
      <h2>{escape(sections['filter']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['filter']['description'])}</p>
      <div class="card">
        <p style="margin:.2rem 0 .8rem 0; color:var(--muted); font-size:.92rem;">{filter_ui['intro']}</p>
        <div class="filter-row">
          <label for="filter_courts" style="font-weight:600;">{escape(filter_ui['court_label'])}</label>
          <select id="filter_courts" multiple size="8" style="min-width:280px; flex:1;">
{filter_options}
          </select>
          <div class="filter-controls">
            <label><input type="checkbox" id="filter_compare"> {escape(filter_ui['compare_label'])}</label>
            <button id="filter_clear" type="button">{escape(filter_ui['clear_button'])}</button>
          </div>
        </div>
        <div id="filter_status" style="margin-top:.6rem; font-size:.9rem; color:var(--accent); font-weight:600;"></div>
      </div>
    </section>''' if is_visible("sections", "filter") else ''}

{f'''    <section id="instans">
      <h2>{escape(sections['instans']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['instans']['description'])}</p>
      <div class="grid">
{instans_cards}
      </div>
    </section>''' if is_visible("sections", "instans") else ''}

{f'''    <section id="utfall">
      <h2>{escape(sections['utfall']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['utfall']['description'])}</p>
      <div class="grid">
{utfall_cards}
      </div>
    </section>''' if is_visible("sections", "utfall") else ''}

{f'''    <section id="vardnad">
      <h2>{escape(sections['vardnad']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['vardnad']['description'])}</p>
      <div class="grid">
{vardnad_cards}
      </div>
    </section>''' if is_visible("sections", "vardnad") else ''}

{f'''    <section id="barn">
      <h2>{escape(sections['barn']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['barn']['description'])}</p>
      <div class="grid">
{barn_cards}
      </div>
    </section>''' if is_visible("sections", "barn") else ''}

{f'''    <section id="foraldrar">
      <h2>{escape(sections['foraldrar']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['foraldrar']['description'])}</p>
      <div class="grid">
{foraldrar_cards}
      </div>
    </section>''' if is_visible("sections", "foraldrar") else ''}

{f'''    <section id="faktorer">
      <h2>{escape(sections['faktorer']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['faktorer']['description'])}</p>
{faktorer_card}
    </section>''' if is_visible("sections", "faktorer") else ''}

{f'''    <section id="process">
      <h2>{escape(sections['process']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['process']['description'])}</p>
      <div class="grid">
{process_cards}
      </div>
      <div class="kpi-grid" style="margin-top:1.5rem">
{process_kpis}
      </div>
    </section>''' if is_visible("sections", "process") else ''}

{f'''    <section id="bilaga">
      <h2>{escape(sections['bilaga']['title'])}</h2>
      <p style="color:var(--muted)">{escape(sections['bilaga']['description'])}</p>
{appendix_html}
    </section>''' if is_visible("sections", "bilaga") else ''}
  </main>

  <footer>
    {escape(ui['footer'])}
  </footer>

  <script>
{js}
  </script>
</body>
</html>
"""
    origin_h = max(420, 28 * len(agg["by_origin_tingsratt"]) + 60)
    html = html.replace("__ORIGIN_H__", str(origin_h))
    outcome_h = max(360, 28 * len(agg["outcome_detail"]) + 60)
    html = html.replace("__OUTCOME_H__", str(outcome_h))
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    cases = load_cases()
    csv_path = write_csv(cases)
    agg = build_aggregates(cases)
    ui = load_ui_text()
    (ANALYSIS_DIR / "overview.json").write_text(
        json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ANALYSIS_DIR / "overview.md").write_text(render_md(agg), encoding="utf-8")
    (ANALYSIS_DIR / "overview.html").write_text(render_html(agg, cases, ui), encoding="utf-8")
    print(f"Wrote {csv_path}, overview.json, overview.md, overview.html  ({len(cases)} cases).")


if __name__ == "__main__":
    main()
