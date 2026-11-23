import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CATALOG_PATH = Path("api/index/catalog.json")
OUT_DIR = Path("api/ugc")
API_TEMPLATE = "https://ugcapi.historicengland.org.uk/api/media/{nhle_id}"
USER_AGENT = "nhle-linked-art-shard-builder/1.0 (+https://github.com/portableant/nhle-linked-art)"


def fetch_media_for_id(nhle_id: str, timeout: float = 15.0) -> list | None:
    url = API_TEMPLATE.format(nhle_id=nhle_id)
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            payload = json.loads(resp.read().decode("utf-8"))
            return payload if isinstance(payload, list) else None
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[warn] NHLE #{nhle_id}: {exc}")
        return None


def main() -> None:
    if not CATALOG_PATH.exists():
        raise SystemExit(f"Catalog not found: {CATALOG_PATH}")

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ids = []
    seen = set()
    for entry in catalog:
        nhle_id = str(entry.get("id", "")).strip()
        if nhle_id and nhle_id not in seen:
            seen.add(nhle_id)
            ids.append(nhle_id)

    written = 0
    empty = 0

    for idx, nhle_id in enumerate(ids, start=1):
        items = fetch_media_for_id(nhle_id)
        if items:
            out_file = OUT_DIR / f"{nhle_id}.json"
            out_file.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            written += 1
        else:
            empty += 1

        if idx % 50 == 0 or idx == len(ids):
            print(f"Processed {idx}/{len(ids)} (written={written}, none={empty})")

        # Polite delay so we don't hammer Historic England's UGC API
        time.sleep(0.15)


if __name__ == "__main__":
    main()