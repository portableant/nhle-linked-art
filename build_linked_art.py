#!/usr/bin/env python3
"""
Pre-Scraped NHLE CSV -> Linked Art 1.0 JSON-LD Static API Builder
-----------------------------------------------------------------
Zero external dependencies (Python 3.9+ standard library only).
"""

import argparse
import csv
import json
import math
import re
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LINKED_ART_CONTEXT = "https://linked.art/ns/v1/linked-art.json"

MATERIAL_PATTERNS = [
    (r"\b(limestone|oolitic|ashlar|portland stone|stone)\b", "http://vocab.getty.edu/aat/300011692", "Stone / Limestone"),
    (r"\b(clunch|totternhoe)\b", "http://vocab.getty.edu/aat/300011692", "Limestone (Clunch)"),
    (r"\b(purbeck marble|marble)\b", "http://vocab.getty.edu/aat/300011443", "Marble"),
    (r"\b(sandstone|gritstone|millstone grit|sarsen)\b", "http://vocab.getty.edu/aat/300011738", "Sandstone"),
    (r"\b(flint|knapped flint|rubble flint)\b", "http://vocab.getty.edu/aat/300011229", "Flint"),
    (r"\b(brick|red brick|stock brick|brickwork)\b", "http://vocab.getty.edu/aat/300010463", "Brick"),
    (r"\b(timber[- ]framed|half[- ]timbered|oak|timber)\b", "http://vocab.getty.edu/aat/300011914", "Wood (Timber)"),
    (r"\b(lead|lead[- ]covered|leaded)\b", "http://vocab.getty.edu/aat/300010900", "Lead"),
    (r"\b(slate|welsh slate|stone slate|collyweston)\b", "http://vocab.getty.edu/aat/300011775", "Slate"),
    (r"\b(tile|tiled|red tile|old tile)\b", "http://vocab.getty.edu/aat/300010673", "Tile (Terracotta)"),
    (r"\b(thatch|thatched|reed)\b", "http://vocab.getty.edu/aat/300011898", "Thatch"),
    (r"\b(cob|earth|witchert|roughcast)\b", "http://vocab.getty.edu/aat/300011002", "Earth / Render"),
    (r"\b(granite)\b", "http://vocab.getty.edu/aat/300011303", "Granite"),
    (r"\b(wrought[- ]iron|cast[- ]iron|iron)\b", "http://vocab.getty.edu/aat/300011002", "Iron"),
]

GRADE_CONCEPTS = {
    "I": ("grade-i", "Grade I Listed Building"),
    "II*": ("grade-ii-star", "Grade II* Listed Building"),
    "II": ("grade-ii", "Grade II Listed Building"),
    "SM": ("scheduled-monument", "Scheduled Monument"),
}

PERIOD_PATTERNS = [
    (r"\b(neolithic|bronze age|iron age)\b", "Prehistoric"),
    (r"\b(roman|romano-british)\b", "Roman"),
    (r"\b(anglo-saxon|saxon|c10|c11)\b", "Anglo-Saxon / Norman"),
    (r"\b(c12|12th century)\b", "12th Century"),
    (r"\b(c13|13th century)\b", "13th Century"),
    (r"\b(c14|14th century)\b", "14th Century"),
    (r"\b(c15|15th century|perpendicular)\b", "15th Century"),
    (r"\b(c16|16th century|tudor|elizabethan)\b", "16th Century"),
    (r"\b(c17|17th century|jacobean|carolean)\b", "17th Century"),
    (r"\b(c18|18th century|georgian|palladian)\b", "18th Century"),
    (r"\b(c19|19th century|regency|victorian)\b", "19th Century"),
    (r"\b(c20|20th century|edwardian|art deco)\b", "20th Century"),
]

ARCHITECT_PATTERNS = [
    r"\b(?:designed by|rebuilt by|restored by|altered by|extended by|enlarged by|architect(?:s)?(?:\s+was|\s+were)?)\s+((?:Sir\s+)?(?:[A-Z][a-z]+|[A-Z]\.)(?:\s+(?:de|van|von|and|&|[A-Z]\.|[A-Z][a-z]+)){1,3})",
    r"(?:1[0-9]{3}|C1[0-9]|C20),?\s+by\s+((?:Sir\s+)?(?:[A-Z][a-z]+|[A-Z]\.)(?:\s+(?:de|van|von|and|&|[A-Z]\.|[A-Z][a-z]+)){1,3})",
]

STOP_TOKENS = {
    "Historic", "England", "Church", "Parish", "North", "South", "East", "West",
    "London", "Public", "Subscription", "High", "Street", "Listing", "The", "Road",
    "Track", "Lane", "Avenue", "Park", "House", "Farm", "Cottage", "Bridge", "Estate",
    "Trust", "Council", "Society", "Company", "Ministry", "Board", "Office", "Works"
}


def osgb36_to_wgs84(easting: float, northing: float) -> Tuple[float, float]:
    a = 6377563.396
    b = 6356256.909
    F0 = 0.9996012717
    lat0 = math.radians(49.0)
    lon0 = math.radians(-2.0)
    N0 = -100000.0
    E0 = 400000.0
    e2 = 1.0 - (b * b) / (a * a)
    n = (a - b) / (a + b)
    n2 = n * n
    n3 = n * n * n

    lat = lat0
    M = 0.0
    while True:
        lat = (northing - N0 - M) / (a * F0) + lat
        Ma = (1.0 + n + (5.0 / 4.0) * n2 + (5.0 / 4.0) * n3) * (lat - lat0)
        Mb = (3.0 * n + 3.0 * n2 + (21.0 / 8.0) * n3) * math.sin(lat - lat0) * math.cos(lat + lat0)
        Mc = ((15.0 / 8.0) * n2 + (15.0 / 8.0) * n3) * math.sin(2.0 * (lat - lat0)) * math.cos(2.0 * (lat + lat0))
        Md = (35.0 / 24.0) * n3 * math.sin(3.0 * (lat - lat0)) * math.cos(3.0 * (lat + lat0))
        M = b * F0 * (Ma - Mb + Mc - Md)
        if abs(northing - N0 - M) < 0.00001:
            break

    cos_lat = math.cos(lat)
    sin_lat = math.sin(lat)
    nu = a * F0 / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    rho = a * F0 * (1.0 - e2) / pow(1.0 - e2 * sin_lat * sin_lat, 1.5)
    eta2 = nu / rho - 1.0
    tan_lat = math.tan(lat)
    tan2 = tan_lat * tan_lat
    tan4 = tan2 * tan2
    tan6 = tan4 * tan2
    sec_lat = 1.0 / cos_lat
    nu3 = nu * nu * nu
    nu5 = nu3 * nu * nu
    nu7 = nu5 * nu * nu

    VII = tan_lat / (2.0 * rho * nu)
    VIII = tan_lat / (24.0 * rho * nu3) * (5.0 + 3.0 * tan2 + eta2 - 9.0 * tan2 * eta2)
    IX = tan_lat / (720.0 * rho * nu5) * (61.0 + 90.0 * tan2 + 45.0 * tan4)
    X = sec_lat / nu
    XI = sec_lat / (6.0 * nu3) * (nu / rho + 2.0 * tan2)
    XII = sec_lat / (120.0 * nu5) * (5.0 + 28.0 * tan2 + 24.0 * tan4)
    XIIA = sec_lat / (5040.0 * nu7) * (61.0 + 662.0 * tan2 + 1320.0 * tan4 + 720.0 * tan6)

    dE = easting - E0
    dE2 = dE * dE
    dE3 = dE2 * dE
    dE4 = dE2 * dE2
    dE5 = dE3 * dE2
    dE6 = dE3 * dE3
    dE7 = dE4 * dE3

    lat_osgb = lat - VII * dE2 + VIII * dE4 - IX * dE6
    lon_osgb = lon0 + X * dE - XI * dE3 + XII * dE5 - XIIA * dE7

    sin_lo = math.sin(lat_osgb)
    cos_lo = math.cos(lat_osgb)
    nu_osgb = a / math.sqrt(1.0 - e2 * sin_lo * sin_lo)
    x1 = nu_osgb * cos_lo * math.cos(lon_osgb)
    y1 = nu_osgb * cos_lo * math.sin(lon_osgb)
    z1 = (1.0 - e2) * nu_osgb * sin_lo

    tx, ty, tz = 446.448, -125.157, 542.060
    s = -20.4894 * 1e-6
    rx = math.radians(0.1502 / 3600.0)
    ry = math.radians(0.2470 / 3600.0)
    rz = math.radians(0.8421 / 3600.0)

    x2 = tx + (1.0 + s) * x1 - rz * y1 + ry * z1
    y2 = ty + rz * x1 + (1.0 + s) * y1 - rx * z1
    z2 = tz - ry * x1 + rx * y1 + (1.0 + s) * z1

    a_wgs = 6378137.0
    b_wgs = 6356752.3141
    e2_wgs = 1.0 - (b_wgs * b_wgs) / (a_wgs * a_wgs)
    p = math.sqrt(x2 * x2 + y2 * y2)
    lat_wgs = math.atan2(z2, p * (1.0 - e2_wgs))
    for _ in range(6):
        nu_w = a_wgs / math.sqrt(1.0 - e2_wgs * math.sin(lat_wgs) ** 2)
        lat_wgs = math.atan2(z2 + e2_wgs * nu_w * math.sin(lat_wgs), p)
    lon_wgs = math.atan2(y2, x2)

    return round(math.degrees(lat_wgs), 6), round(math.degrees(lon_wgs), 6)


def parse_he_date(raw_date: str) -> Optional[str]:
    raw = (raw_date or "").strip()
    if not raw or raw.lower() == "nan":
        return None
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def title_case_name(name: str) -> str:
    return name.title() if name.isupper() else name


def normalize_locality(raw_loc: str) -> str:
    loc = re.sub(r"[\-–—\.,;:]+$", "", (raw_loc or "").strip())
    loc = re.sub(r"\s+", " ", loc).strip()
    if not loc or loc.lower() in {"nan", "england", "the", "north", "south", "east", "west"}:
        return "Unassigned Locality"
    if "cholesbury" in loc.lower():
        return "Cholesbury-cum-St Leonards"
    return loc.title().replace("-Cum-", "-cum-").replace("St.", "St")


def extract_locality_from_details(details: str) -> str:
    if not details:
        return "Unassigned Locality"
    first_chunk = details.strip().split("\n")[0][:140]
    cleaned = re.sub(r"\b[A-Z]{2}\s*\d{2}\s*(?:NW|NE|SW|SE)?\b", " ", first_chunk)
    m = re.match(r"^\s*([A-Z][A-Z\-\.\s]{2,40}?)(?:\s{2,}|\t|\()", cleaned)
    if m:
        loc = normalize_locality(m.group(1))
        if len(loc) >= 3:
            return loc
    return "Unassigned Locality"


def extract_legacy_id(legacy_text: str) -> Optional[Tuple[str, str]]:
    if not legacy_text or legacy_text.lower() == "nan":
        return None
    num_m = re.search(r"Legacy System number:\s*([A-Za-z0-9\-]+)", legacy_text)
    sys_m = re.search(r"Legacy System:\s*([A-Za-z0-9\-]+)", legacy_text)
    if num_m:
        return (sys_m.group(1) if sys_m else "Legacy"), num_m.group(1)
    return None


def extract_architects(text: str) -> List[str]:
    found: List[str] = []
    for pat in ARCHITECT_PATTERNS:
        for match in re.finditer(pat, text):
            candidate = re.sub(r"\s+", " ", match.group(1).strip().rstrip(".,;:"))
            words = candidate.replace(".", "").split()
            if len(words) < 2:
                continue
            if any(w in STOP_TOKENS for w in words):
                continue
            if 5 <= len(candidate) <= 45 and candidate not in found:
                found.append(candidate)
    return found


def extract_build_timespan(text: str) -> Optional[Dict[str, str]]:
    m = re.search(r"\b(1[0-9]{3})(?:\s*[-–]\s*(1[0-9]{3}|[0-9]{2}))?\b", text)
    if m:
        start_yr = m.group(1)
        end_raw = m.group(2)
        end_yr = (end_raw if len(end_raw) == 4 else f"{start_yr[:2]}{end_raw}") if end_raw else start_yr
        return {
            "type": "TimeSpan",
            "_label": f"{start_yr}–{end_yr}" if start_yr != end_yr else start_yr,
            "begin_of_the_begin": f"{start_yr}-01-01T00:00:00Z",
            "end_of_the_end": f"{end_yr}-12-31T23:59:59Z",
        }
    return None


def extract_provenance_chain(text: str, name: str, locality: str, list_entry: str, base_url: str, prod_timespan: Optional[Dict[str, str]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extracts Linked Art `changed_ownership_through` (Acquisition events) and `current_owner`
    from Historic England listing text so `@micropasts/provenance-timeline` can render a
    complete chain of custody alongside `produced_by`.
    """
    acquisitions: List[Dict[str, Any]] = []
    owners: List[Dict[str, Any]] = []
    cleaned = re.sub(r"Listing NGR:.*$", "", text)
    clauses = re.split(r"(?<=[\.;])\s+", cleaned)

    transfer_rules = [
        (r"\b(?:presented by|given by|gift of|donated by)\s+((?:Sir\s+|Lord\s+|Lady\s+)?[A-Z][a-z]+(?:\s+(?:de|van|von|[A-Z]\.|[A-Z][a-z]+)){0,3})", "Gift"),
        (r"\b(?:bequeathed by|left by|inherited from)\s+((?:Sir\s+|Lord\s+|Lady\s+)?[A-Z][a-z]+(?:\s+(?:de|van|von|[A-Z]\.|[A-Z][a-z]+)){0,3})", "Inheritance"),
        (r"\b(?:sold to|purchased by|bought by|acquired by)\s+((?:the\s+)?(?:National Trust|English Heritage|Crown|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}))", "Sales"),
    ]

    idx = 1
    for clause in clauses:
        c_clean = re.sub(r"\s+", " ", clause).strip()
        if not c_clean:
            continue

        year_match = re.search(r"\b(1[0-9]{3})\b", c_clean)
        ts_obj = None
        if year_match:
            yr = year_match.group(1)
            ts_obj = {
                "type": "TimeSpan",
                "_label": yr,
                "begin_of_the_begin": f"{yr}-01-01T00:00:00Z",
                "end_of_the_end": f"{yr}-12-31T23:59:59Z",
            }
        elif prod_timespan:
            ts_obj = prod_timespan

        for pat, method_label in transfer_rules:
            m = re.search(pat, c_clean)
            if m:
                party_name = m.group(1).strip().rstrip(".,;:")
                acq: Dict[str, Any] = {
                    "id": f"{base_url}/api/acquisition/nhle-{list_entry}-{idx}",
                    "type": "Acquisition",
                    "_label": f"{method_label}: {c_clean[:120]}",
                    "classified_as": [
                        {
                            "id": "http://vocab.getty.edu/aat/300417642" if method_label == "Gift" else "http://vocab.getty.edu/aat/300417644",
                            "type": "Type",
                            "_label": method_label,
                        }
                    ],
                    "referred_to_by": [
                        {
                            "type": "LinguisticObject",
                            "classified_as": [{"id": "http://vocab.getty.edu/aat/300435416", "type": "Type", "_label": "Provenance Statement"}],
                            "content": c_clean,
                        }
                    ],
                }
                if ts_obj:
                    acq["timespan"] = ts_obj

                if method_label in ("Gift", "Inheritance"):
                    acq["transferred_title_from"] = [{"type": "Person", "_label": party_name}]
                    acq["transferred_title_to"] = [{"type": "Group", "_label": f"Public / Trust Stewards ({locality})"}]
                else:
                    acq["transferred_title_from"] = [{"type": "Person", "_label": "Unknown"}]
                    acq["transferred_title_to"] = [{"type": "Group", "_label": party_name}]

                acquisitions.append(acq)
                idx += 1

    # Determine current steward / owner
    lower_all = cleaned.lower()
    if "national trust" in lower_all:
        owners.append({"type": "Group", "_label": "The National Trust"})
    elif "english heritage" in lower_all:
        owners.append({"type": "Group", "_label": "English Heritage"})
    elif "now offices" in lower_all or "council chamber" in lower_all or "town hall" in lower_all:
        owners.append({"type": "Group", "_label": f"Civic / Municipal Stewardship ({locality})"})
    elif "parish church" in lower_all:
        owners.append({"type": "Group", "_label": f"Parochial Church Council ({locality})"})
    else:
        owners.append({"type": "Group", "_label": f"Statutory Listed Property Steward ({locality})"})

    return acquisitions, owners


def extract_chronology_phases(text: str) -> List[Dict[str, Any]]:
    """
    Extracts ordered historical construction & alteration phases (both explicit years like
    '1772', '1898', 'after 1910' and century tokens like 'Late C16', 'C17', 'C18', 'C19')
    with surrounding clause context for Linked Art `Modification` nodes and timeline rendering.
    """
    phases: List[Dict[str, Any]] = []
    seen_keys = set()

    # Split into sentences/clauses while avoiding NGR codes
    cleaned = re.sub(r"Listing NGR:.*$", "", text)
    clauses = re.split(r"(?<=[\.;])\s+", cleaned)

    for clause in clauses:
        c_clean = re.sub(r"\s+", " ", clause).strip()
        if len(c_clean) < 8:
            continue

        # 1. Explicit years / ranges (e.g., 1675-1710, 1772, 1898, after 1910)
        for ym in re.finditer(r"\b(after\s+|c\.?\s*)?(1[0-9]{3})(?:\s*[-–]\s*(1[0-9]{3}|[0-9]{2}))?\b", c_clean, flags=re.IGNORECASE):
            qual = (ym.group(1) or "").strip()
            start_yr = int(ym.group(2))
            end_raw = ym.group(3)
            if end_raw:
                end_yr = int(end_raw) if len(end_raw) == 4 else int(f"{str(start_yr)[:2]}{end_raw}")
            else:
                end_yr = start_yr
            label = f"{qual + ' ' if qual else ''}{start_yr}" + (f"–{end_yr}" if end_yr != start_yr else "")
            key = ("year", start_yr, end_yr)
            if key not in seen_keys:
                seen_keys.add(key)
                phases.append({
                    "sort_year": start_yr,
                    "label": label,
                    "begin": f"{start_yr}-01-01T00:00:00Z",
                    "end": f"{end_yr}-12-31T23:59:59Z",
                    "note": c_clean[:140] + ("…" if len(c_clean) > 140 else ""),
                })

        # 2. Century mentions (e.g., Late C16, Early C17, C18, mid C19)
        for cm in re.finditer(r"\b((?:early|mid|late)[-\s]+)?C(1[0-9]|20)\b", c_clean, flags=re.IGNORECASE):
            qual = (cm.group(1) or "").strip().title()
            cent = int(cm.group(2))
            base_yr = (cent - 1) * 100
            if "early" in qual.lower():
                s_yr, e_yr = base_yr, base_yr + 33
            elif "mid" in qual.lower():
                s_yr, e_yr = base_yr + 34, base_yr + 66
            elif "late" in qual.lower():
                s_yr, e_yr = base_yr + 67, base_yr + 99
            else:
                s_yr, e_yr = base_yr, base_yr + 99
            label = f"{qual + ' ' if qual else ''}C{cent}"
            key = ("cent", s_yr, e_yr)
            if key not in seen_keys:
                seen_keys.add(key)
                phases.append({
                    "sort_year": s_yr,
                    "label": label,
                    "begin": f"{s_yr:04d}-01-01T00:00:00Z",
                    "end": f"{e_yr:04d}-12-31T23:59:59Z",
                    "note": c_clean[:140] + ("…" if len(c_clean) > 140 else ""),
                })

    phases.sort(key=lambda p: p["sort_year"])
    return phases[:8]


def extract_materials(text: str) -> List[Dict[str, str]]:
    found = []
    seen = set()
    lower_text = text.lower()
    for pattern, aat_uri, label in MATERIAL_PATTERNS:
        if re.search(pattern, lower_text) and label not in seen:
            seen.add(label)
            found.append({"id": aat_uri, "type": "Material", "_label": label})
    return found


def extract_periods(text: str) -> List[str]:
    found = []
    lower_text = text.lower()
    for pattern, label in PERIOD_PATTERNS:
        if re.search(pattern, lower_text) and label not in found:
            found.append(label)
    return found or ["Unassigned Period"]


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")



def load_authority_cache(cache_path: Path) -> Dict[str, Any]:
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"persons": {}, "places": {}}


def save_authority_cache(cache_path: Path, cache: Dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def sparql_post_with_retry(query: str, max_retries: int = 4, base_delay: float = 1.5) -> Dict[str, Any]:
    """
    Executes a POST SPARQL query against Wikidata with automatic `Retry-After` /
    exponential backoff handling for HTTP 429 (Too Many Requests) and 503/504 responses.
    """
    endpoint = "https://query.wikidata.org/sparql"
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode("utf-8")
    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "NHLE-LinkedArt-Builder/1.4 (https://github.com/portableant; polite-batch)",
    }

    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(endpoint, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=35) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503, 504) and attempt < max_retries:
                retry_after = exc.headers.get("Retry-After")
                wait_s = float(retry_after) if (retry_after and retry_after.isdigit()) else base_delay * (2 ** attempt)
                print(f"[rate-limit] Wikidata HTTP {exc.code}; pausing {wait_s:.1f}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(wait_s)
                continue
            raise
        except Exception:
            if attempt < max_retries:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise
    return {}


def normalize_actor_variants(raw_name: str) -> List[str]:
    """Generates clean label variants for Wikidata matching (handles 'and' vs '&', 'Co' vs 'Co.', honorifics)."""
    base = re.sub(r"^(?:Sir|Lord|Lady|Dr|Rev)\s+", "", raw_name.strip()).strip()
    variants = [base]
    if " and Co" in base:
        variants.append(base.replace(" and Co", " & Co."))
        variants.append(base.replace(" and Co", " & Co"))
    elif " & Co" in base:
        variants.append(base.replace(" & Co.", " and Co").replace(" & Co", " and Co"))
    if " and " in base:
        variants.append(base.replace(" and ", " & "))
    return list(dict.fromkeys(v for v in variants if v))


def resolve_person_authorities(names: List[str], cache: Dict[str, Any], cache_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """
    Batch-reconciles extracted architects, makers, firms (e.g. 'Liberty and Co'), and patrons
    against Wikidata SPARQL using `VALUES ?searchLabel` chunks of 60 labels per request
    (preventing HTTP 429 rate-limit errors).
    """
    person_cache = cache.setdefault("persons", {})
    to_query = [n for n in sorted(set(names)) if n and n not in person_cache]
    if not to_query:
        return person_cache

    variant_to_originals: Dict[str, List[str]] = {}
    for orig in to_query:
        for var in normalize_actor_variants(orig):
            variant_to_originals.setdefault(var, []).append(orig)

    all_variants = list(variant_to_originals.keys())
    batch_size = 60

    for i in range(0, len(all_variants), batch_size):
        chunk = all_variants[i : i + batch_size]
        values_str = " ".join(f'"{v.replace(chr(34), "")}"@en' for v in chunk)
        query = f"""
        PREFIX schema: <http://schema.org/>
        SELECT ?searchLabel ?item ?itemLabel ?desc ?isOrg ?ulan ?viaf ?odnb ?wikipedia WHERE {{
          VALUES ?searchLabel {{ {values_str} }}
          ?item rdfs:label ?searchLabel .
          {{
            ?item wdt:P31 wd:Q5 .
            BIND(false AS ?isOrg)
          }} UNION {{
            ?item wdt:P31/wdt:P279* wd:Q43229 .
            BIND(true AS ?isOrg)
          }}
          OPTIONAL {{ ?item wdt:P245 ?ulan . }}
          OPTIONAL {{ ?item wdt:P214 ?viaf . }}
          OPTIONAL {{ ?item wdt:P1415 ?odnb . }}
          OPTIONAL {{
            ?wikipedia schema:about ?item ;
                       schema:isPartOf <https://en.wikipedia.org/> .
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        try:
            payload = sparql_post_with_retry(query)
            by_label: Dict[str, List[Dict[str, Any]]] = {}
            for b in payload.get("results", {}).get("bindings", []):
                lbl = b["searchLabel"]["value"]
                by_label.setdefault(lbl, []).append(b)

            for var in chunk:
                candidates = by_label.get(var, [])
                best = None
                for b in candidates:
                    desc = b.get("desc", {}).get("value", "").lower()
                    if b.get("ulan") or any(k in desc for k in ("architect", "builder", "mason", "engineer", "sculptor", "surveyor", "department store", "design", "firm", "noble", "banker", "politician")):
                        best = b
                        break
                if not best and candidates:
                    best = candidates[0]

                if best:
                    qid_uri = best["item"]["value"]
                    qid = qid_uri.rsplit("/", 1)[-1]
                    is_org = best.get("isOrg", {}).get("value") == "true"
                    record = {
                        "wikidata_uri": qid_uri,
                        "wikidata_qid": qid,
                        "entity_type": "Group" if is_org else "Person",
                        "label": best.get("itemLabel", {}).get("value", var),
                        "ulan": best.get("ulan", {}).get("value", ""),
                        "viaf": best.get("viaf", {}).get("value", ""),
                        "odnb": best.get("odnb", {}).get("value", ""),
                        "wikipedia": best.get("wikipedia", {}).get("value", ""),
                    }
                    for orig in variant_to_originals[var]:
                        if not person_cache.get(orig):
                            person_cache[orig] = record

            for orig in to_query:
                if any(v in chunk for v in normalize_actor_variants(orig)):
                    person_cache.setdefault(orig, {})

            if cache_path:
                save_authority_cache(cache_path, cache)
            time.sleep(1.0)
        except Exception as exc:
            print(f"[warn] Batched person/firm authority lookup failed: {exc}")

    return person_cache


def resolve_place_authorities(localities: List[str], cache: Dict[str, Any], cache_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """
    Batch-reconciles UK localities/parishes against Wikidata SPARQL using `VALUES ?searchLabel`
    chunks of 60 labels per request (preventing HTTP 429 rate-limit errors).
    """
    place_cache = cache.setdefault("places", {})
    to_query = [
        loc for loc in sorted(set(localities))
        if loc and loc != "Unassigned Locality" and loc not in place_cache
    ]
    if not to_query:
        return place_cache

    batch_size = 60
    for i in range(0, len(to_query), batch_size):
        chunk = to_query[i : i + batch_size]
        values_str = " ".join(f'"{loc.replace(chr(34), "")}"@en' for loc in chunk)
        query = f"""
        PREFIX schema: <http://schema.org/>
        SELECT ?searchLabel ?item ?itemLabel ?tgn ?geonames ?gss ?wikipedia WHERE {{
          VALUES ?searchLabel {{ {values_str} }}
          ?item rdfs:label ?searchLabel ;
                wdt:P17 wd:Q145 ;
                wdt:P31/wdt:P279* wd:Q486972 .
          OPTIONAL {{ ?item wdt:P1667 ?tgn . }}
          OPTIONAL {{ ?item wdt:P1566 ?geonames . }}
          OPTIONAL {{ ?item wdt:P836 ?gss . }}
          OPTIONAL {{
            ?wikipedia schema:about ?item ;
                       schema:isPartOf <https://en.wikipedia.org/> .
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        try:
            payload = sparql_post_with_retry(query)
            by_label: Dict[str, List[Dict[str, Any]]] = {}
            for b in payload.get("results", {}).get("bindings", []):
                lbl = b["searchLabel"]["value"]
                by_label.setdefault(lbl, []).append(b)

            for loc in chunk:
                candidates = by_label.get(loc, [])
                best = next((b for b in candidates if b.get("tgn") or b.get("geonames")), candidates[0] if candidates else None)
                if best:
                    qid_uri = best["item"]["value"]
                    qid = qid_uri.rsplit("/", 1)[-1]
                    place_cache[loc] = {
                        "wikidata_uri": qid_uri,
                        "wikidata_qid": qid,
                        "label": best.get("itemLabel", {}).get("value", loc),
                        "tgn": best.get("tgn", {}).get("value", ""),
                        "geonames": best.get("geonames", {}).get("value", ""),
                        "gss": best.get("gss", {}).get("value", ""),
                        "wikipedia": best.get("wikipedia", {}).get("value", ""),
                    }
                else:
                    place_cache[loc] = {}

            if cache_path:
                save_authority_cache(cache_path, cache)
            time.sleep(1.0)
        except Exception as exc:
            print(f"[warn] Batched place authority lookup failed: {exc}")

    return place_cache


def enrich_person_node(person_node: Dict[str, Any], auth: Dict[str, Any]) -> Dict[str, Any]:
    """Attaches Linked Art `equivalent`, `identified_by`, and `subject_of` authority links to a Person or Group node."""
    if not auth or not auth.get("wikidata_uri"):
        return person_node

    crm_type = auth.get("entity_type", "Person")
    person_node["type"] = crm_type

    eqs: List[Dict[str, Any]] = [
        {
            "id": auth["wikidata_uri"],
            "type": crm_type,
            "_label": f"{auth.get('label', person_node['_label'])} (Wikidata {auth['wikidata_qid']})",
        }
    ]
    ids: List[Dict[str, Any]] = [
        {
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "Wikidata Entity ID"}],
            "content": auth["wikidata_qid"],
        }
    ]

    if auth.get("ulan"):
        eqs.append({
            "id": f"http://vocab.getty.edu/ulan/{auth['ulan']}",
            "type": crm_type,
            "_label": f"Getty ULAN {auth['ulan']}",
        })
        ids.append({
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "Getty ULAN ID"}],
            "content": auth["ulan"],
        })

    if auth.get("viaf"):
        eqs.append({
            "id": f"https://viaf.org/viaf/{auth['viaf']}",
            "type": crm_type,
            "_label": f"VIAF {auth['viaf']}",
        })
        ids.append({
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "VIAF ID"}],
            "content": auth["viaf"],
        })

    if auth.get("odnb"):
        ids.append({
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "Oxford DNB ID"}],
            "content": auth["odnb"],
        })

    person_node["equivalent"] = eqs
    person_node["identified_by"] = ids

    if auth.get("wikipedia"):
        person_node["subject_of"] = [
            {
                "id": auth["wikipedia"],
                "type": "LinguisticObject",
                "_label": f"Wikipedia: {auth.get('label', person_node['_label'])}",
                "format": "text/html",
            }
        ]

    return person_node


def enrich_place_node(place_node: Dict[str, Any], locality: str, auth: Dict[str, Any]) -> Dict[str, Any]:
    """Attaches Linked Art `equivalent`, `identified_by`, and `subject_of` authority links to a Place node."""
    if not auth or not auth.get("wikidata_uri"):
        return place_node

    eqs: List[Dict[str, Any]] = [
        {
            "id": auth["wikidata_uri"],
            "type": "Place",
            "_label": f"{auth.get('label', locality)} (Wikidata {auth['wikidata_qid']})",
        }
    ]
    ids: List[Dict[str, Any]] = [
        {
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "Wikidata Entity ID"}],
            "content": auth["wikidata_qid"],
        }
    ]

    if auth.get("tgn"):
        eqs.append({
            "id": f"http://vocab.getty.edu/tgn/{auth['tgn']}",
            "type": "Place",
            "_label": f"Getty TGN {auth['tgn']}",
        })
        ids.append({
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "Getty TGN ID"}],
            "content": auth["tgn"],
        })

    if auth.get("geonames"):
        eqs.append({
            "id": f"https://sws.geonames.org/{auth['geonames']}/",
            "type": "Place",
            "_label": f"GeoNames {auth['geonames']}",
        })
        ids.append({
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "GeoNames ID"}],
            "content": auth["geonames"],
        })

    if auth.get("gss"):
        ids.append({
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "ONS GSS Code"}],
            "content": auth["gss"],
        })

    place_node["equivalent"] = eqs
    place_node["identified_by"] = ids

    if auth.get("wikipedia"):
        place_node["subject_of"] = [
            {
                "id": auth["wikipedia"],
                "type": "LinguisticObject",
                "_label": f"Wikipedia: {auth.get('label', locality)}",
                "format": "text/html",
            }
        ]

    return place_node


def fetch_wikidata_exact_matches(list_entries: List[str]) -> Dict[str, Dict[str, str]]:
    results: Dict[str, Dict[str, str]] = {}
    batch_size = 100
    endpoint = "https://query.wikidata.org/sparql"

    for i in range(0, len(list_entries), batch_size):
        chunk = [str(le).strip() for le in list_entries[i : i + batch_size] if str(le).strip()]
        if not chunk:
            continue
        values_str = " ".join(f'"{le}"' for le in chunk)
        query = f"""
        PREFIX schema: <http://schema.org/>
        SELECT ?nhle ?item ?itemLabel ?image ?commonsCat ?geograph ?wikipedia WHERE {{
          VALUES ?nhle {{ {values_str} }}
          ?item wdt:P1216 ?nhle .
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P373 ?commonsCat . }}
          OPTIONAL {{ ?item wdt:P1261 ?geograph . }}
          OPTIONAL {{
            ?wikipedia schema:about ?item ;
                       schema:isPartOf <https://en.wikipedia.org/> .
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        try:
            payload = sparql_post_with_retry(query)

            for b in payload.get("results", {}).get("bindings", []):
                nhle_id = b["nhle"]["value"].strip()
                qid_uri = b["item"]["value"]
                qid_code = qid_uri.rsplit("/", 1)[-1]
                label = b.get("itemLabel", {}).get("value", qid_code)
                img_uri = b.get("image", {}).get("value", "")
                if img_uri.startswith("http://"):
                    img_uri = "https://" + img_uri[7:]
                commons_cat = b.get("commonsCat", {}).get("value", "")
                commons_cat_url = (
                    f"https://commons.wikimedia.org/wiki/Category:{urllib.parse.quote(commons_cat.replace(' ', '_'))}"
                    if commons_cat
                    else ""
                )
                geograph_id = b.get("geograph", {}).get("value", "")
                geograph_url = f"https://www.geograph.org.uk/photo/{geograph_id}" if geograph_id else ""
                wikipedia_url = b.get("wikipedia", {}).get("value", "")

                existing = results.get(nhle_id, {})
                results[nhle_id] = {
                    "wikidata_uri": qid_uri,
                    "wikidata_qid": qid_code,
                    "wikidata_label": label,
                    "image": img_uri or existing.get("image", ""),
                    "commons_category_url": commons_cat_url or existing.get("commons_category_url", ""),
                    "geograph_url": geograph_url or existing.get("geograph_url", ""),
                    "wikipedia_url": wikipedia_url or existing.get("wikipedia_url", ""),
                }
            time.sleep(0.4)
        except Exception as exc:
            print(f"[warn] Wikidata SPARQL batch failed: {exc}")

    return results


def clean_val(row: Dict[str, Any], key: str) -> str:
    val = str(row.get(key, "") or "").strip()
    return "" if val.lower() == "nan" else val


def row_to_linked_art(
    row: Dict[str, Any],
    wd_meta: Dict[str, str],
    person_auth_map: Dict[str, Dict[str, Any]],
    place_auth_map: Dict[str, Dict[str, Any]],
    base_url: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    list_entry = clean_val(row, "List Entry Number") or clean_val(row, "ListEntry")
    raw_name = clean_val(row, "List Entry Name") or clean_val(row, "Name") or "Unnamed Heritage Asset"
    name = title_case_name(raw_name)
    grade = (clean_val(row, "Grade") or "II").upper()
    list_date = parse_he_date(clean_val(row, "Listing date"))
    amend_date = parse_he_date(clean_val(row, "Date of most recent amendment"))
    ngr = clean_val(row, "National Grid Reference")
    capture_scale = clean_val(row, "Capture scale")
    hyperlink = clean_val(row, "NHLE link") or f"https://historicengland.org.uk/listing/the-list/list-entry/{list_entry}"

    summary_text = clean_val(row, "Summary")
    reasons_text = clean_val(row, "Reasons for Designation")
    history_text = clean_val(row, "History")
    details_text = clean_val(row, "Details")
    legacy_text = clean_val(row, "Legacy")
    sources_text = clean_val(row, "Selected Sources")

    lat: Optional[float] = None
    lon: Optional[float] = None
    easting_str = clean_val(row, "Easting")
    northing_str = clean_val(row, "Northing")
    if easting_str and northing_str:
        try:
            lat, lon = osgb36_to_wgs84(float(easting_str), float(northing_str))
        except ValueError:
            pass
    elif clean_val(row, "Latitude") and clean_val(row, "Longitude"):
        lat = float(clean_val(row, "Latitude"))
        lon = float(clean_val(row, "Longitude"))

    locality = normalize_locality(clean_val(row, "Parish")) if clean_val(row, "Parish") else extract_locality_from_details(details_text)
    grade_slug, grade_label = GRADE_CONCEPTS.get(grade, ("listed-building", f"Grade {grade} Listed Building"))
    combined_text = f"{name} {summary_text} {details_text} {reasons_text} {history_text}"

    identifiers: List[Dict[str, Any]] = [
        {
            "type": "Name",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404670", "type": "Type", "_label": "Primary Name"}],
            "content": name,
        },
        {
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "NHLE List Entry Number"}],
            "content": list_entry,
        },
    ]

    if ngr:
        identifiers.append({
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "National Grid Reference (OSGB36)"}],
            "content": ngr,
        })

    legacy_pair = extract_legacy_id(legacy_text)
    if legacy_pair:
        sys_name, leg_num = legacy_pair
        identifiers.append({
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": f"Legacy System Number ({sys_name})"}],
            "content": leg_num,
        })

    if wd_meta.get("wikidata_qid"):
        identifiers.append({
            "type": "Identifier",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "Wikidata Entity ID"}],
            "content": wd_meta["wikidata_qid"],
        })

    place_node: Dict[str, Any] = {
        "id": f"{base_url}/api/place/nhle-{list_entry}",
        "type": "Place",
        "_label": f"{locality} ({ngr})" if ngr else locality,
    }
    if lon is not None and lat is not None:
        place_node["defined_by"] = f"POINT({lon} {lat})"
    if locality in place_auth_map:
        enrich_place_node(place_node, locality, place_auth_map[locality])

    subject_of_links: List[Dict[str, Any]] = [
        {
            "id": hyperlink,
            "type": "LinguisticObject",
            "_label": f"Historic England Official List Entry #{list_entry}",
            "format": "text/html",
        }
    ]
    if wd_meta.get("wikipedia_url"):
        subject_of_links.append({
            "id": wd_meta["wikipedia_url"],
            "type": "LinguisticObject",
            "_label": f"Wikipedia Article: {wd_meta.get('wikidata_label', name)}",
            "format": "text/html",
        })
    if wd_meta.get("commons_category_url"):
        subject_of_links.append({
            "id": wd_meta["commons_category_url"],
            "type": "LinguisticObject",
            "_label": "Wikimedia Commons Media Category",
            "format": "text/html",
        })
    if wd_meta.get("geograph_url"):
        subject_of_links.append({
            "id": wd_meta["geograph_url"],
            "type": "LinguisticObject",
            "_label": "Geograph Britain and Ireland Photograph Page",
            "format": "text/html",
        })

    doc: Dict[str, Any] = {
        "@context": LINKED_ART_CONTEXT,
        "id": f"{base_url}/api/object/{list_entry[:3]}/{list_entry}.json",
        "type": "HumanMadeObject",
        "_label": f"{name} ({locality})" if locality != "Unassigned Locality" else name,
        "classified_as": [
            {
                "id": "http://vocab.getty.edu/aat/300004789",
                "type": "Type",
                "_label": "Building" if grade != "SM" else "Monument",
            },
            {
                "id": f"{base_url}/api/concept/{grade_slug}",
                "type": "Type",
                "_label": grade_label,
                "classified_as": [
                    {"id": "http://vocab.getty.edu/aat/300435443", "type": "Type", "_label": "Type of Work"}
                ],
            },
        ],
        "identified_by": identifiers,
        "subject_to": [
            {
                "type": "Right",
                "_label": f"Statutory Protection: {grade_label}",
                "classified_as": [{"id": "http://vocab.getty.edu/aat/300055547", "type": "Type", "_label": "Legal Status"}],
            }
        ],
        "current_location": place_node,
        "subject_of": subject_of_links,
    }

    if wd_meta.get("wikidata_uri"):
        doc["equivalent"] = [
            {
                "id": wd_meta["wikidata_uri"],
                "type": "HumanMadeObject",
                "_label": f"{wd_meta.get('wikidata_label', name)} ({wd_meta.get('wikidata_qid', 'Wikidata')})",
            }
        ]

    architects = extract_architects(combined_text)
    phases = extract_chronology_phases(combined_text)
    timespan = extract_build_timespan(combined_text)
    if not timespan and phases:
        p0 = phases[0]
        timespan = {
            "type": "TimeSpan",
            "_label": p0["label"],
            "begin_of_the_begin": p0["begin"],
            "end_of_the_end": p0["end"],
        }

    if architects or timespan:
        prod: Dict[str, Any] = {
            "id": f"{base_url}/api/production/nhle-{list_entry}",
            "type": "Production",
            "_label": f"Origin / Construction of {name}" + (f" ({phases[0]['label']})" if phases else ""),
        }
        if architects:
            prod["carried_out_by"] = [
                enrich_person_node(
                    {
                        "id": f"{base_url}/api/person/{slugify(arch)}",
                        "type": "Person",
                        "_label": arch,
                    },
                    person_auth_map.get(arch, {}),
                )
                for arch in architects
            ]
        if timespan:
            prod["timespan"] = timespan
        if locality and locality != "Unassigned Locality":
            prod["took_place_at"] = [place_node]
        doc["produced_by"] = prod

    acquisitions, current_owners = extract_provenance_chain(
        combined_text, name, locality, list_entry, base_url, timespan
    )
    if acquisitions:
        for acq in acquisitions:
            for party_key in ("transferred_title_from", "transferred_title_to"):
                for p_node in acq.get(party_key, []):
                    if p_node.get("type") == "Person" and p_node.get("_label") in person_auth_map:
                        p_node["id"] = f"{base_url}/api/person/{slugify(p_node['_label'])}"
                        enrich_person_node(p_node, person_auth_map[p_node["_label"]])
        doc["changed_ownership_through"] = acquisitions
    if current_owners:
        doc["current_owner"] = current_owners

    # Subsequent historical phases -> Linked Art `modified_by` (`Modification` nodes with `TimeSpan`)
    if len(phases) > 1:
        mods: List[Dict[str, Any]] = []
        for idx, ph in enumerate(phases[1:], start=1):
            mods.append({
                "id": f"{base_url}/api/modification/nhle-{list_entry}-{idx}",
                "type": "Modification",
                "_label": f"{ph['label']}: {ph['note']}",
                "timespan": {
                    "type": "TimeSpan",
                    "_label": ph["label"],
                    "begin_of_the_begin": ph["begin"],
                    "end_of_the_end": ph["end"],
                },
            })
        doc["modified_by"] = mods

    if wd_meta.get("image"):
        img_url = wd_meta["image"]
        doc["representation"] = [
            {
                "id": f"{base_url}/api/visual/nhle-{list_entry}",
                "type": "VisualItem",
                "_label": f"Photograph of {name} (Wikimedia Commons)",
                "digitally_shown_by": [
                    {
                        "id": f"{base_url}/api/digital/nhle-{list_entry}",
                        "type": "DigitalObject",
                        "_label": f"Commons Image for {name}",
                        "format": "image/jpeg",
                        "access_point": [{"id": img_url, "type": "DigitalObject"}],
                    }
                ],
            }
        ]

    materials = extract_materials(combined_text)
    if materials:
        doc["made_of"] = materials

    referred: List[Dict[str, Any]] = []
    if summary_text:
        referred.append({
            "type": "LinguisticObject",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300435416", "type": "Type", "_label": "Summary"}],
            "content": summary_text,
        })
    if details_text:
        referred.append({
            "type": "LinguisticObject",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300435416", "type": "Type", "_label": "Details (Official List Description)"}],
            "content": details_text,
        })
    if reasons_text:
        referred.append({
            "type": "LinguisticObject",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300435422", "type": "Type", "_label": "Reasons for Designation"}],
            "content": reasons_text,
        })
    if history_text:
        referred.append({
            "type": "LinguisticObject",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300435416", "type": "Type", "_label": "History"}],
            "content": history_text,
        })
    if sources_text:
        referred.append({
            "type": "LinguisticObject",
            "classified_as": [{"id": "http://vocab.getty.edu/aat/300026497", "type": "Type", "_label": "Selected Sources"}],
            "content": sources_text,
        })
    if referred:
        doc["referred_to_by"] = referred

    if list_date:
        ts: Dict[str, Any] = {
            "type": "TimeSpan",
            "begin_of_the_begin": f"{list_date}T00:00:00Z",
        }
        if amend_date:
            ts["end_of_the_end"] = f"{amend_date}T23:59:59Z"
        doc["attributed_by"] = [
            {
                "type": "AttributeAssignment",
                "_label": f"Statutory Designation (Capture scale {capture_scale})" if capture_scale else "Statutory Designation",
                "timespan": ts,
            }
        ]

    catalog_entry = {
        "id": list_entry,
        "name": name,
        "grade": grade,
        "place": locality,
        "ngr": ngr,
        "materials": [m["_label"] for m in materials],
        "periods": extract_periods(combined_text),
        "architects": architects,
        "wikidataUri": wd_meta.get("wikidata_uri", ""),
        "wikidataQid": wd_meta.get("wikidata_qid", ""),
        "wikipediaUrl": wd_meta.get("wikipedia_url", ""),
        "commonsCategoryUrl": wd_meta.get("commons_category_url", ""),
        "geographUrl": wd_meta.get("geograph_url", ""),
        "hasImage": bool(wd_meta.get("image")),
        "lat": lat,
        "lon": lon,
        "uri": f"api/object/{list_entry[:3]}/{list_entry}.json",
    }

    return doc, catalog_entry


def main():
    parser = argparse.ArgumentParser(description="Convert pre-scraped NHLE CSV to Linked Art 1.0 JSON-LD shards.")
    parser.add_argument("--input", required=True, help="Path to pre-scraped NHLE CSV file")
    parser.add_argument("--output", default="./api", help="Output API directory")
    parser.add_argument("--base-url", default="https://portableant.github.io/nhle-linked-art", help="Public base URI")
    parser.add_argument("--cache-dir", default="./cache", help="Directory for caching authority reconciliations")
    parser.add_argument("--skip-wikidata", action="store_true", help="Skip live Wikidata / Getty / VIAF / GeoNames SPARQL enrichment")
    args = parser.parse_args()

    out_dir = Path(args.output)
    auth_cache_path = Path(args.cache_dir) / "authority_links.json"
    auth_cache = load_authority_cache(auth_cache_path)

    with open(args.input, newline="", encoding="utf-8-sig") as f:
        rows = [
            r for r in csv.DictReader(f)
            if (clean_val(r, "List Entry Number") or clean_val(r, "ListEntry"))
        ]

    list_entries = [clean_val(r, "List Entry Number") or clean_val(r, "ListEntry") for r in rows]
    wd_map = {} if args.skip_wikidata else fetch_wikidata_exact_matches(list_entries)

    # Collect unique architects, provenance persons, and localities across all rows for batch authority reconciliation
    all_persons: List[str] = []
    all_places: List[str] = []
    for row in rows:
        raw_name = clean_val(row, "List Entry Name") or clean_val(row, "Name")
        details_text = clean_val(row, "Details")
        combined = f"{raw_name} {clean_val(row, 'Summary')} {details_text} {clean_val(row, 'Reasons for Designation')} {clean_val(row, 'History')}"
        all_persons.extend(extract_architects(combined))
        for m in re.finditer(r"\b(?:presented by|given by|gift of|donated by|bequeathed by|left by|inherited from)\s+((?:Sir\s+|Lord\s+|Lady\s+)?[A-Z][a-z]+(?:\s+(?:de|van|von|[A-Z]\.|[A-Z][a-z]+)){0,3})", combined):
            all_persons.append(m.group(1).strip().rstrip(".,;:"))
        loc = normalize_locality(clean_val(row, "Parish")) if clean_val(row, "Parish") else extract_locality_from_details(details_text)
        all_places.append(loc)

    if args.skip_wikidata:
        person_auth_map = auth_cache.get("persons", {})
        place_auth_map = auth_cache.get("places", {})
    else:
        person_auth_map = resolve_person_authorities(all_persons, auth_cache, auth_cache_path)
        place_auth_map = resolve_place_authorities(all_places, auth_cache, auth_cache_path)
        save_authority_cache(auth_cache_path, auth_cache)

    catalog = []

    for row in rows:
        list_entry = clean_val(row, "List Entry Number") or clean_val(row, "ListEntry")
        wd_meta = wd_map.get(list_entry, {})
        la_doc, cat_entry = row_to_linked_art(row, wd_meta, person_auth_map, place_auth_map, args.base_url)

        shard = out_dir / "object" / list_entry[:3]
        shard.mkdir(parents=True, exist_ok=True)
        (shard / f"{list_entry}.json").write_text(json.dumps(la_doc, indent=2, ensure_ascii=False), encoding="utf-8")
        catalog.append(cat_entry)

    index_dir = out_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "catalog.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    wd_hits = sum(1 for c in catalog if c["wikidataUri"])
    img_hits = sum(1 for c in catalog if c["hasImage"])
    print(f"Exported {len(catalog)} Linked Art 1.0 records ({wd_hits} Wikidata exact matches, {img_hits} Commons P18 images).")


if __name__ == "__main__":
    main()