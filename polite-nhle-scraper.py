from __future__ import annotations

import csv
import json
import random
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup
from curl_cffi import requests

# --- Configuration ---
INPUT_FILE = "dacorum.csv"
CHECKPOINT_JSONL = "historic_england_checkpoint.jsonl"
OUTPUT_CSV = "historic_england_with_descriptions.csv"
SAMPLE_CSV = "historic_england_sample_10th.csv"
SAMPLE_EVERY = 10

PROXY_URL: Optional[str] = None

# Conservative Pacing Settings
MIN_DELAY = 6.0
MAX_DELAY = 14.0
LONG_READ_PROBABILITY = 0.15       # 15% chance of pausing as if reading a long entry
LONG_READ_RANGE = (20.0, 45.0)

BATCH_BREAK_EVERY = 40             # Take a longer break every 40 requests
BATCH_BREAK_RANGE = (120.0, 300.0) # 2 to 5 minute break

MAX_REQUESTS_PER_HOUR = 300        # Hard hourly ceiling
OFF_PEAK_ONLY = False              # Set True to only scrape between 22:00 and 07:00 local time

MAX_RETRIES = 2
CONSECUTIVE_BLOCK_LIMIT = 2        # Stop quickly if blocked so IP reputation stays clean

# Stick to one realistic desktop profile per IP rather than flipping fingerprints
IMPERSONATE_PROFILE = "chrome"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

STOP_REQUESTED = False


def _handle_sigint(signum, frame) -> None:
    global STOP_REQUESTED
    if STOP_REQUESTED:
        print("\nForce quitting immediately.")
        sys.exit(1)
    STOP_REQUESTED = True
    print("\nCtrl+C detected: finishing current record and saving CSVs safely...")


signal.signal(signal.SIGINT, _handle_sigint)


def create_warmed_session(proxy_url: Optional[str] = None) -> requests.Session:
    """Creates a session and visits the main list landing page to acquire baseline cookies."""
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    session = requests.Session(impersonate=IMPERSONATE_PROFILE, proxies=proxies)
    session.headers.update(HEADERS)

    try:
        landing_url = "https://historicengland.org.uk/listing/the-list/"
        resp = session.get(
            landing_url,
            headers={"Sec-Fetch-Site": "none"},
            timeout=25,
        )
        if resp.status_code == 200:
            time.sleep(random.uniform(2.5, 5.0))
    except Exception as exc:
        print(f"  [!] Session warm-up warning: {exc}")

    return session


def build_official_entry_url(raw_url: str, entry_id: str) -> str:
    if not raw_url:
        return f"https://historicengland.org.uk/listing/the-list/list-entry/{entry_id}?section=official-list-entry"

    parsed = urlparse(raw_url.strip())
    query = parse_qs(parsed.query)
    query["section"] = ["official-list-entry"]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def parse_listing_html(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    page_title = soup.title.get_text(strip=True) if soup.title else ""
    if "Just a moment" in page_title or "Attention Required" in page_title:
        raise PermissionError("Challenge interstitial returned.")

    target_headings = {
        "Summary",
        "Reasons for Designation",
        "History",
        "Details",
        "Selected Sources",
        "Legacy",
    }
    sections: Dict[str, str] = {}

    for heading in soup.find_all(["h2", "h3"]):
        heading_text = heading.get_text(strip=True)
        if heading_text in target_headings:
            paragraphs: List[str] = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ["h2", "h3", "section"]:
                    break
                text = sibling.get_text(" ", strip=True)
                if text:
                    paragraphs.append(text)
            if paragraphs:
                sections[heading_text] = "\n\n".join(paragraphs)

    if not sections:
        main = soup.find("main")
        if main:
            sections["Details"] = main.get_text("\n", strip=True)

    return sections


def fetch_politely(
    session: requests.Session,
    url: str,
    referer: str,
    proxy_url: Optional[str] = None,
) -> Tuple[str, requests.Session]:
    """Fetches a listing with realistic Referer chaining and long cooldowns on 429/403."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(
                url,
                headers={"Referer": referer},
                timeout=30,
            )

            if resp.status_code == 200:
                if "Just a moment..." in resp.text[:1500]:
                    raise PermissionError("Challenge page returned on 200 status.")
                return resp.text, session

            if resp.status_code == 404:
                raise FileNotFoundError(f"404 Not Found: {url}")

            if resp.status_code in (403, 429, 503):
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait_seconds = float(retry_after) + random.uniform(15.0, 45.0)
                else:
                    # Long, cautious cooldown (5 to 12 minutes)
                    wait_seconds = (300.0 * attempt) + random.uniform(30.0, 120.0)

                if attempt == MAX_RETRIES:
                    raise PermissionError(f"HTTP {resp.status_code} persisted after cooldown.")

                print(f"  [!] HTTP {resp.status_code} received. Cooling down {wait_seconds / 60:.1f} mins before retry...")
                session.close()
                time.sleep(wait_seconds)
                session = create_warmed_session(proxy_url)
                continue

            resp.raise_for_status()

        except (FileNotFoundError, PermissionError):
            raise
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Network error after {MAX_RETRIES} attempts: {exc}") from exc
            wait_seconds = 60.0 * attempt + random.uniform(10.0, 30.0)
            print(f"  [!] Transient network error ({exc}). Waiting {wait_seconds:.0f}s...")
            time.sleep(wait_seconds)

    raise RuntimeError("Exhausted retries")


def human_sleep() -> None:
    """Simulates natural reading variance between page views."""
    if random.random() < LONG_READ_PROBABILITY:
        delay = random.uniform(*LONG_READ_RANGE)
    else:
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
    time.sleep(delay)


def wait_for_off_peak_if_enabled() -> None:
    """Pauses execution during daytime hours when OFF_PEAK_ONLY is True."""
    if not OFF_PEAK_ONLY:
        return
    while not STOP_REQUESTED:
        hour = datetime.now().hour
        if hour >= 22 or hour < 7:
            return
        print(f"  [~] Daytime pause ({datetime.now().strftime('%H:%M')}). Waiting 15 mins for off-peak window (22:00-07:00)...")
        time.sleep(900)


def load_checkpoint(jsonl_path: str) -> Dict[str, dict]:
    records: Dict[str, dict] = {}
    path = Path(jsonl_path)
    if not path.exists():
        return records

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item.get("status") in ("ok", "not_found"):
                    records[str(item["id"])] = item
    return records


def detect_delimiter(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8-sig") as f:
        first_line = f.readline()
    return "\t" if "\t" in first_line else ","


def print_sample_preview(record: dict, row: dict, count: int) -> None:
    secs = record.get("sections", {})
    preview_text = secs.get("Details") or secs.get("Summary") or secs.get("Legacy") or "(No text extracted)"
    snippet = preview_text.replace("\n", " ")[:240]
    found_keys = ", ".join(secs.keys()) if secs else "None"

    print(f"\n--- SAMPLE #{count} | ID: {record['id']} | {row.get('List Entry Name', '')} ---")
    print(f"Sections found: [{found_keys}]")
    print(f"Excerpt: {snippet}...\n")


def export_csvs(
    rows: List[dict],
    original_headers: List[str],
    completed: Dict[str, dict],
    output_path: str,
    sample_path: str,
    sample_every: int,
) -> int:
    new_columns = [
        "Summary",
        "Reasons for Designation",
        "History",
        "Details",
        "Legacy",
        "Selected Sources",
        "Scrape Status",
    ]
    out_headers = original_headers + new_columns
    ok_counter = 0
    sample_count = 0

    with open(output_path, "w", encoding="utf-8-sig", newline="") as full_file, open(
        sample_path, "w", encoding="utf-8-sig", newline=""
    ) as sample_file:
        full_writer = csv.DictWriter(full_file, fieldnames=out_headers)
        sample_writer = csv.DictWriter(sample_file, fieldnames=out_headers)

        full_writer.writeheader()
        sample_writer.writeheader()

        for row in rows:
            out_row = dict(row)
            entry_id = out_row["List Entry Number"].strip()
            cached = completed.get(entry_id)

            if cached and cached.get("status") == "ok":
                ok_counter += 1
                secs = cached.get("sections", {})
                out_row["Summary"] = secs.get("Summary", "")
                out_row["Reasons for Designation"] = secs.get("Reasons for Designation", "")
                out_row["History"] = secs.get("History", "")
                out_row["Details"] = secs.get("Details", "")
                out_row["Legacy"] = secs.get("Legacy", "")
                out_row["Selected Sources"] = secs.get("Selected Sources", "")
                out_row["Scrape Status"] = "ok"

                if ok_counter % sample_every == 0:
                    sample_writer.writerow(out_row)
                    sample_count += 1
            elif cached and cached.get("status") == "not_found":
                for col in new_columns[:-1]:
                    out_row[col] = ""
                out_row["Scrape Status"] = "404_not_found"
            else:
                for col in new_columns[:-1]:
                    out_row[col] = ""
                out_row["Scrape Status"] = "pending_or_error"

            full_writer.writerow(out_row)

    return sample_count


def run() -> None:
    delimiter = detect_delimiter(INPUT_FILE)
    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.DictReader(infile, delimiter=delimiter)
        rows = list(reader)
        original_headers = list(reader.fieldnames) if reader.fieldnames else []

    if "List Entry Number" not in original_headers or "NHLE link" not in original_headers:
        raise ValueError(f"Missing required columns. Found: {original_headers}")

    completed = load_checkpoint(CHECKPOINT_JSONL)
    total = len(rows)
    print(f"Loaded {total:,} rows | Already completed: {len(completed):,} | Remaining: {total - len(completed):,}")

    session = create_warmed_session(PROXY_URL)
    last_url = "https://historicengland.org.uk/listing/the-list/"
    consecutive_blocks = 0
    processed_this_run = 0

    hour_window_start = time.monotonic()
    requests_in_current_hour = 0

    try:
        with open(CHECKPOINT_JSONL, "a", encoding="utf-8") as ckpt_file:
            for idx, row in enumerate(rows, start=1):
                if STOP_REQUESTED:
                    break

                wait_for_off_peak_if_enabled()
                if STOP_REQUESTED:
                    break

                entry_id = row["List Entry Number"].strip()
                raw_url = row["NHLE link"].strip()

                if not entry_id or entry_id in completed:
                    continue

                # Enforce strict hourly request budget
                elapsed_hour = time.monotonic() - hour_window_start
                if elapsed_hour >= 3600:
                    hour_window_start = time.monotonic()
                    requests_in_current_hour = 0
                elif requests_in_current_hour >= MAX_REQUESTS_PER_HOUR:
                    sleep_for = (3600 - elapsed_hour) + random.uniform(15.0, 45.0)
                    print(f"--- Hourly cap ({MAX_REQUESTS_PER_HOUR}/hr) reached. Sleeping {sleep_for / 60:.1f} mins ---")
                    time.sleep(sleep_for)
                    hour_window_start = time.monotonic()
                    requests_in_current_hour = 0

                target_url = build_official_entry_url(raw_url, entry_id)

                try:
                    requests_in_current_hour += 1
                    html, session = fetch_politely(session, target_url, last_url, PROXY_URL)
                    last_url = target_url
                    sections = parse_listing_html(html)

                    record = {
                        "id": entry_id,
                        "url": target_url,
                        "sections": sections,
                        "status": "ok",
                    }
                    ckpt_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    ckpt_file.flush()
                    completed[entry_id] = record

                    consecutive_blocks = 0
                    processed_this_run += 1
                    print(f"[{idx}/{total}] OK {entry_id} - {row.get('List Entry Name', '')[:45]}")

                    if processed_this_run % SAMPLE_EVERY == 0:
                        print_sample_preview(record, row, processed_this_run)

                except FileNotFoundError:
                    record = {"id": entry_id, "url": target_url, "status": "not_found"}
                    ckpt_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    ckpt_file.flush()
                    completed[entry_id] = record
                    consecutive_blocks = 0
                    print(f"[{idx}/{total}] 404 {entry_id} (marked not_found)")

                except Exception as exc:
                    consecutive_blocks += 1
                    err_record = {
                        "id": entry_id,
                        "url": target_url,
                        "status": "error",
                        "error": str(exc),
                    }
                    ckpt_file.write(json.dumps(err_record, ensure_ascii=False) + "\n")
                    ckpt_file.flush()
                    print(f"[{idx}/{total}] ERROR {entry_id}: {exc}")

                    if consecutive_blocks >= CONSECUTIVE_BLOCK_LIMIT:
                        print(f"\nStopping early after {CONSECUTIVE_BLOCK_LIMIT} consecutive blocks to protect IP.")
                        break

                if not STOP_REQUESTED:
                    human_sleep()
                    if processed_this_run > 0 and processed_this_run % BATCH_BREAK_EVERY == 0:
                        pause = random.uniform(*BATCH_BREAK_RANGE)
                        print(f"--- Taking a {pause / 60:.1f} min break after {processed_this_run} records ---")
                        time.sleep(pause)
    finally:
        session.close()
        sample_count = export_csvs(rows, original_headers, completed, OUTPUT_CSV, SAMPLE_CSV, SAMPLE_EVERY)
        print(f"Saved {len(completed):,}/{total:,} records to {OUTPUT_CSV}.")
        print(f"Saved {sample_count:,} every-{SAMPLE_EVERY}th sample records to {SAMPLE_CSV}.")


if __name__ == "__main__":
    run()
