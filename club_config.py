"""Shared club-code normalization and GSPro bag-mapping helpers."""
from __future__ import annotations

import json
import re
from typing import Any

WEDGE_LOFTS = (46, 48, 50, 52, 54, 56, 58, 60, 62, 64)

# Canonical source clubs that GSPro may identify. These are the rows shown in
# Bag Mapping. Target clubs may additionally be loft-specific wedges.
BAG_SOURCE_CLUBS = (
    "D",
    "W3", "W5", "W7", "W9",
    "HY", "H2", "H3", "H4", "H5", "H6", "H7",
    "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9",
    "PW", "GW", "AW", "SW", "LW",
    "PT",
)

CLUB_CHOICES = (
    "D",
    "W3", "W5", "W7", "W9",
    "HY", "H2", "H3", "H4", "H5", "H6", "H7",
    "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9",
    "PW", "GW", "AW", "SW", "LW",
    *(f"{loft}DEG" for loft in WEDGE_LOFTS),
    "PT",
)


def canonical_club(value: Any) -> str:
    code = str(value or "UNKNOWN").strip().upper() or "UNKNOWN"
    # GSPro integrations emit both compact codes ("3W") and display names
    # ("3 Wood", "Iron 7"). Normalize both before applying bag mappings.
    code = code.replace("\u00c2\u00b0", "\u00b0").replace("\u00b0", " DEG ")
    code = re.sub(r"[_\-/]+", " ", code)
    code = re.sub(r"\s+", " ", code).strip()
    if code in {"PT", "PUTT", "PUTTER"}:
        return "PT"
    if code in {"D", "DR", "DRIVER", "1W", "W1"}:
        return "D"
    if code in {"FW", "FAIRWAY", "FAIRWAY WOOD"}:
        return "FW"
    if code in {"HY", "HYBRID"}:
        return "HY"
    wedge_names = {
        "PITCHING WEDGE": "PW", "PITCH WEDGE": "PW",
        "GAP WEDGE": "GW", "APPROACH WEDGE": "AW",
        "SAND WEDGE": "SW", "LOB WEDGE": "LW",
    }
    if code in wedge_names:
        return wedge_names[code]
    compact = code.replace(" ", "")
    if len(compact) == 2 and compact[0].isdigit() and compact[1] in {"I", "W", "H"}:
        return compact[1] + compact[0]
    if len(compact) == 2 and compact[0] in {"I", "W", "H"} and compact[1].isdigit():
        return compact
    named = re.fullmatch(r"([1-9])\s*(?:FAIRWAY\s*)?(WOOD|IRON|HYBRID)", code)
    if named:
        number, kind = named.groups()
    else:
        named = re.fullmatch(r"(?:FAIRWAY\s*)?(WOOD|IRON|HYBRID)\s*([1-9])", code)
        kind, number = named.groups() if named else (None, None)
    if number and kind:
        return {"WOOD": "W", "IRON": "I", "HYBRID": "H"}[kind] + number
    loft = (
        code.replace("WEDGE", "")
        .replace("DEGREES", "")
        .replace("DEGREE", "")
        .replace("DEG", "")
        .strip()
    )
    if loft.isdigit() and int(loft) in WEDGE_LOFTS:
        return f"{int(loft)}DEG"
    return code


def display_club(value: Any) -> str:
    code = canonical_club(value)
    if code == "D":
        return "Driver"
    if code == "PT":
        return "Putter"
    if code == "FW":
        return "Fairway Wood"
    if code == "HY":
        return "Hybrid"
    if len(code) == 2 and code[0] == "I" and code[1].isdigit():
        return f"{code[1]} Iron"
    if len(code) == 2 and code[0] == "W" and code[1].isdigit():
        return f"{code[1]} Wood"
    if len(code) == 2 and code[0] == "H" and code[1].isdigit():
        return f"{code[1]} Hybrid"
    if code.endswith("DEG") and code[:-3].isdigit():
        return f"{code[:-3]}° Wedge"
    return {
        "PW": "Pitching Wedge",
        "GW": "Gap Wedge",
        "AW": "Approach Wedge",
        "SW": "Sand Wedge",
        "LW": "Lob Wedge",
    }.get(code, code)


def normalize_bag_mapping(value: Any) -> dict[str, str]:
    """Return a validated canonical source->target mapping.

    Empty/unmapped values are omitted. Mapping a club to itself is also omitted,
    which keeps the persisted JSON compact and means "use GSPro value".
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    if not isinstance(value, dict):
        return {}

    allowed_targets = set(CLUB_CHOICES)
    result: dict[str, str] = {}
    for source, target in value.items():
        src = canonical_club(source)
        raw_target = str(target or "").strip()
        if not raw_target:
            continue
        dst = canonical_club(raw_target)
        if dst not in allowed_targets:
            continue
        if dst != src:
            result[src] = dst
    return result


def map_gspro_club(raw_club: Any, mapping: Any) -> str | None:
    if raw_club is None or not str(raw_club).strip():
        return None
    source = canonical_club(raw_club)
    normalized = normalize_bag_mapping(mapping)
    return normalized.get(source, source)
