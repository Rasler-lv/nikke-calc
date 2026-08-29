"""
Phase 2: Base stat calculator

Formula:
  (level_stat + (level_stat×0.02+20) × breakthrough + affinity_stat + console_stat)
  × (1 + 0.02×core_enhancement)
  + equipment_stat + cube_stat + collection_stat

Character instance structure:
  {
    "name": "Rapi",
    "level": 200,
    "breakthrough": 3,          # 0~3
    "core_enhancement": 7,      # 0~7 (unlocked after breakthrough 3)
    "affinity": 30,             # 1~40
    "equipment": {
      # If `tier` is omitted = overload gear (upgrade 0~5). Normal gear uses tier: "T1"~"T9" (no upgrades)
      # tier + corp = T9 corporate gear — has upgrade 0~5 and if corp matches character corp it gets +30% (§_equip_stat)
      # Unequipped is tier: "None" — different from upgrade 0 (that also grants flat stats)
      "Head": { "level": 5, "skills": [{"id": "atk_pct", "lv": 10}, ...] },
      "Body": { "level": 5, "skills": [...] },
      "Arm":   { "tier": "T9", "corp": "Tetra", "level": 3, "skills": [...] },
      "Leg": { "tier": "T9", "skills": [...] }
    },
    "cube": { "name": "Resilience Cube", "level": 5 },
    # class_level·company_level can be a number (same across classes/companies) or a dict by class/company.
    # In-game recycled labs have 3 classes and 5 companies separately, so using dicts is more realistic.
    "console": { "common_level": 10, "class_level": 10, "company_level": 10 },
    #   or "console": { "common_level": 250,
    #                     "class_level":   {"Attacker": 138, "Defender": 138, "Supporter": 138},
    #                     "company_level": {"Elysion": 139, ..., "Abnormal": 110} }
    "collection_stage": "SR15"   # "R0"~"SR15" or "None" (unequipped)
  }
"""
import json
import os

_DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
_TABLE_DIR = os.path.join(_DATA_DIR, "base_stat_tables")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Tables (loaded once on module import) ──────────────────────────────────
_NIKKE       = _load(os.path.join(_DATA_DIR, "parsed_nikke.json"))
_LEVEL_STATS = _load(os.path.join(_TABLE_DIR, "level_stats.json"))
_AFFINITY    = _load(os.path.join(_TABLE_DIR, "affinity.json"))
_CONSOLE     = _load(os.path.join(_TABLE_DIR, "console.json"))
_EQUIP_STATS = _load(os.path.join(_TABLE_DIR, "equipment_stats.json"))
_CUBE        = _load(os.path.join(_TABLE_DIR, "cube.json"))
_COLLECTION  = _load(os.path.join(_TABLE_DIR, "collection.json"))

# Representation for unequipped. The equipment `tier` and `collection_stage` share this.
# **Must be distinguished from corporate upgrade 0 / R0** — those are the "lowest equipped state" and
# grant flat stats. Empty slots are common in real accounts.
NO_ITEM = "None"


# ── Internal utilities ───────────────────────────────────────────────────[...]

def _zero():
    return {"atk": 0.0, "def": 0.0, "hp": 0.0}


def _add(a, b):
    return {"atk": a["atk"] + b["atk"],
            "def": a["def"] + b["def"],
            "hp":  a["hp"]  + b["hp"]}


def _scale(s, k):
    return {"atk": s["atk"] * k, "def": s["def"] * k, "hp": s["hp"] * k}


# The level stat table uses 20-level "bands". Within a band the per-level increase is linear,
# and at band boundaries (level ≡ 1 mod 20) there is a larger jump. The ratio between band
# starting values is the same across class/weapon/stat (e.g. 881→901 all share 1.069251).
#
# The table covers up to level 1000 but the game goes beyond that. If we clamp at 1000,
# high-level players would see >15% attack drops (out-of-sync). Instead, levels above the table
# are connected using the measured ratios in `level_beyond.json`, and beyond measured data
# we extrapolate the tail using that ratio behavior.
_BEYOND = _load(os.path.join(_TABLE_DIR, "level_beyond.json"))
BAND = int(_BEYOND["band"])
_BAND_RATIOS = {int(k): float(v) for k, v in _BEYOND["ratios"].items()}
# The share of the band increase that is spread evenly across levels; the remainder is the
# jump at the band boundary. Like ratios, the share slowly decreases with level.
_BAND_SHARES = {int(k): float(v) for k, v in _BEYOND["shares"].items()}


def _power_fit(series: dict) -> tuple:
    """Fit ln(y) = intercept + slope*ln(x) — used to create the tail beyond measured data."""
    import math
    points = [(math.log(b), math.log(y)) for b, y in sorted(series.items()) if y > 0]
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    denom = sum((x - mx) ** 2 for x, _ in points)
    slope = sum((x - mx) * (y - my) for x, y in points) / denom
    return slope, my - slope * mx


_RATIO_TAIL = _power_fit({b: r - 1 for b, r in _BAND_RATIOS.items()})
_SHARE_TAIL = _power_fit(_BAND_SHARES)


def _tail(fit: tuple, band: int) -> float:
    import math
    slope, inter = fit
    return math.exp(inter + slope * math.log(max(band, 1)))


def band_ratio(band: int) -> float:
    """Return the multiplicative ratio for one band. Use measured if available, otherwise use the extrapolated tail."""
    if band in _BAND_RATIOS:
        return _BAND_RATIOS[band]
    return 1 + _tail(_RATIO_TAIL, band)


def band_share(band: int) -> float:
    """Return the share of a band's increase that is spread evenly across the band."""
    if band in _BAND_SHARES:
        return _BAND_SHARES[band]
    return _tail(_SHARE_TAIL, band)


def _beyond_table(table: dict, keys: list, level: int) -> dict:
    """Extend the top of the table. Mimic the band shape (even increase inside band + one jump at boundary)."""
    top = int(keys[-1])
    start_level = top - (top - 1) % BAND          # start level of the table's last band (e.g. 1000 -> 981)
    value = {k: float(v) for k, v in table[str(start_level)].items()}
    band = (start_level - 1) // BAND
    while True:
        ratio = band_ratio(band)
        gap = {k: v * (ratio - 1) for k, v in value.items()}
        band_start = band * BAND + 1
        if band_start <= level < band_start + BAND:
            offset = level - band_start
            if offset == 0:
                return {k: round(v) for k, v in value.items()}
            share = band_share(band)
            return {k: round(value[k] + gap[k] * share * offset / (BAND - 1))
                    for k in value}
        value = {k: value[k] + gap[k] for k in value}
        band += 1


def _level_stat(cls: str, weapon: str, level: int) -> dict:
    """Lookup level stats in level_stats.json. If the level has no exact key, linearly interpolate between adjacent keys.

    Levels above the table (1000) are connected by `_beyond_table()` — these are estimates.
    """
    table = _LEVEL_STATS[f"{cls}_{weapon}"]
    key = str(level)
    if key in table:
        return dict(table[key])

    keys   = sorted(table.keys(), key=int)
    levels = [int(k) for k in keys]
    if level <= levels[0]:
        return dict(table[keys[0]])
    if level > levels[-1]:
        return _beyond_table(table, keys, level)

    for i in range(len(levels) - 1):
        lo, hi = levels[i], levels[i + 1]
        if lo < level < hi:
            t = (level - lo) / (hi - lo)
            lo_s, hi_s = table[str(lo)], table[str(hi)]
            return {
                "atk": lo_s["atk"] + t * (hi_s["atk"] - lo_s["atk"]),
                "def": lo_s["def"] + t * (hi_s["def"] - lo_s["def"]),
                "hp":  lo_s["hp"]  + t * (hi_s["hp"]  - lo_s["hp"]),
            }


# Multipliers for T9 corporate gear. The in-game formula is `base × (1 + 0.3×corp_match + 0.1×upgrade_level)`
# and the two terms are added, not multiplied (see blablalink frontend `getEquipAttr`).
# Overload gear has no manufacturer and cannot get corp match bonus; its upgrade bonus is already
# baked into `equipment_stats.json` under the "기업" table, so we don't use these constants for overload gear.
CORP_MATCH_BONUS = 0.3
GEAR_LEVEL_BONUS = 0.1


def _equip_stat(cls: str, part: str, part_data: dict, corp: str | None = None) -> dict:
    """Flat stat for a single equipment part. If `tier` is missing it's overload gear (use `level` upgrade stage).

    Three branches:
      `tier` missing      overload — look up the "기업" table by `level` (observed)
      `tier` + `corp`     T9 corporate — use the standard table for the tier and then apply the multiplier
                         `corp` is the equipment manufacturer; if it equals the character corp, add +30% match
      `tier` only         normal T1~T9 — no upgrades, ignore `level`
    `tier: "None"` means unequipped — returns zero.

    The game rounds each part before summing, so we round per-part here as well.
    """
    tier = part_data.get("tier")
    if tier == NO_ITEM:
        return _zero()
    if tier in (None, "Manufacturer"):
        return _EQUIP_STATS["Manufacturer"][cls][part][str(part_data["level"])]
    base = _EQUIP_STATS["Normal"][tier][cls][part]
    gear_corp = part_data.get("corp")
    if not gear_corp:
        return base
    mult = 1 + GEAR_LEVEL_BONUS * part_data.get("level", 0)
    if gear_corp == corp:
        mult += CORP_MATCH_BONUS
    return {k: float(round(v * mult)) for k, v in base.items()}


def console_level(console: dict, key: str, bucket: str, name: str) -> int:
    """Select a single console level. If the value is a dict, pick using `bucket` (class or company).

    Recycled labs in-game can have separate levels for 3 classes and 5 companies. A single number
    means the same level for all buckets; if a dict is used it must include every bucket — missing
    entries would quietly cause 0 which is unintended.
    """
    val = console[key]
    if not isinstance(val, dict):
        return val
    if bucket not in val:
        raise KeyError(
            f"[{name}] console.{key} is missing {bucket!r} (available keys: {sorted(val)}). "
            f"If console levels are specified per-class/company, you must include all buckets — missing entries must not silently become 0.")
    return val[bucket]


def collection_stat(stage: str) -> dict:
    """Flat stat for collection (favorite) stage. `"None"` (unequipped) returns zero.

    SSR favorite items have identical flat stats and favorite skill levels to SR15, so they are
    represented as `"SR15"` (CDN `favorite_{id}.json`: atk/hp/def arrays match SR15, `level1`=4).
    """
    if stage == NO_ITEM:
        return _zero()
    entry = _COLLECTION["_stat_table"].get(stage)
    if entry is None:
        raise KeyError(
            f"Unknown collection stage {stage!r} — must be 'R0'~'R15', 'SR0'~'SR15' or 'None' (unequipped)")
    return {"atk": entry["atk"], "def": entry["def"], "hp": entry["hp"]}


def _core_formula(lv_val: float, bt: int) -> float:
    """Apply DealForm ② b formula to a single level stat value."""
    return lv_val + (lv_val * 0.02 + 20) * bt


# ── Main calculation function ─────────────────────────────────────────────

def calc_base_stats(char: dict) -> dict:
    """
    Convert a character instance into base ATK / DEF / HP.
    Returns: {"atk": int, "def": int, "hp": int}
    """
    name       = char["name"]
    level      = char["level"]
    bt         = char["breakthrough"]
    core_enh   = char["core_enhancement"]
    affinity   = char["affinity"]
    equip_inst = char["equipment"]
    cube_inst  = char["cube"]
    console    = char["console"]
    coll_stage = char["collection_stage"]

    # Character metadata
    meta   = _NIKKE[name]
    cls    = meta["class"]
    weapon = meta["weapon_type"]

    # Level stats
    lv_s = _level_stat(cls, weapon, level)

    # Core formula (for atk/def/hp individually)
    core = {
        "atk": _core_formula(lv_s["atk"], bt),
        "def": _core_formula(lv_s["def"], bt),
        "hp":  _core_formula(lv_s["hp"],  bt),
    }

    # Affinity stats
    aff_s = _AFFINITY[cls][str(affinity)]

    # Console stats (common + class + company). Class/company may be given per-bucket.
    con_s = _zero()
    for con_type, level_key, bucket in (
        ("Common",   "common_level",  ""),
        ("Class", "class_level",   cls),
        ("Manufacturer",   "company_level", meta["manufacturer"]),
    ):
        per = _CONSOLE[con_type]["per_level"]
        con_s = _add(con_s, _scale(per, console_level(console, level_key, bucket, name)))

    # Sum before core enhancement → apply core enhancement multiplier
    pre_scaled = _scale(
        _add(_add(core, aff_s), con_s),
        1 + 0.02 * core_enh,
    )

    # Flat equipment stats (sum of 4 parts)
    equip_s = _zero()
    for part, part_data in equip_inst.items():
        equip_s = _add(equip_s, _equip_stat(cls, part, part_data, meta["manufacturer"]))

    # Cube flat stats. "None" means the cube is not equipped and grants no stats.
    # (Some combos like Miranda intentionally have negative cube synergy so unequipping is a valid choice.)
    cube_s = _zero() if cube_inst.get("name") == "None" else _CUBE["_stats"][str(cube_inst["level"])]

    # Collection flat stats
    coll_s = collection_stat(coll_stage)

    # Final sum
    total = _add(_add(_add(pre_scaled, equip_s), cube_s), coll_s)
    return {"atk": round(total["atk"]),
            "def": round(total["def"]),
            "hp":  round(total["hp"])}


def hp_to_atk(hp: float, ratio: float) -> float:
    """
    Convert HP → ATK. Matches skill text 'N% of max HP as attack'.
    ratio: fraction (5% → 0.05)
    """
    return hp * ratio


# ── Quick test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    sample = {
        "name": "Rapi",
        "level": 200,
        "breakthrough": 0,
        "core_enhancement": 0,
        "affinity": 1,
        "equipment": {
            "Head": {"level": 0, "skills": []},
            "Body": {"level": 0, "skills": []},
            "Arm":   {"level": 0, "skills": []},
            "Leg": {"level": 0, "skills": []},
        },
        "cube": {"name": "Resilience Cube", "level": 1},
        "console": {"common_level": 0, "class_level": 0, "company_level": 0},
        "collection_stage": "R0",
    }

    result = calc_base_stats(sample)
    print("Rapi lv200 bt0 minimum:", result)
