#!/usr/bin/env python3
"""Page-watch prototype: fetch a public page with Scrapling, hash its main
text, and report a diff when the content changes.

Usage:
    page_watch.py                 # check all targets in targets.json
    page_watch.py <slug>          # check one target
    page_watch.py --init <slug>   # (re)save baseline without reporting

State per target:
    state/<slug>.txt   normalized text snapshot (the baseline)
    state/<slug>.json  metadata {name, url, sha256, title, updated_at}
Diffs are written to reports/<slug>-<YYYYmmdd-HHMMSS>.diff and a short
summary is printed to stdout (cron-friendly).

Exit codes: 0 = no change / baseline saved, 2 = change detected,
1 = fetch or config error.
"""
import difflib
import hashlib
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE = BASE / "state"
REPORTS = BASE / "reports"
JST = timezone(timedelta(hours=9))


def normalize(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines) + "\n"


def fetch_text(url: str, selector: str | None) -> tuple[str, str]:
    from scrapling.fetchers import Fetcher

    page = Fetcher.get(url, timeout=30)
    if page.status != 200:
        raise RuntimeError(f"HTTP {page.status} for {url}")
    title = (page.css("title::text").get() or "").strip()
    if selector:
        node = page.css(selector)
        text = node.get_all_text(ignore_tags=("script", "style")) if node else ""
        if not text:
            text = page.get_all_text(ignore_tags=("script", "style"))
    else:
        text = page.get_all_text(ignore_tags=("script", "style"))
    return title, normalize(text)


def save_baseline(slug: str, target: dict, title: str, text: str) -> str:
    STATE.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (STATE / f"{slug}.txt").write_text(text, encoding="utf-8")
    meta = {
        "name": target["name"],
        "url": target["url"],
        "title": title,
        "sha256": digest,
        "updated_at": datetime.now(JST).isoformat(timespec="seconds"),
    }
    (STATE / f"{slug}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return digest


def check(target: dict, init: bool = False) -> int:
    slug = target["slug"]
    title, text = fetch_text(target["url"], target.get("selector"))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    snap_path = STATE / f"{slug}.txt"
    meta_path = STATE / f"{slug}.json"

    if init or not snap_path.exists():
        save_baseline(slug, target, title, text)
        print(f"BASELINE_SAVED {slug} sha256={digest[:12]} title={title}")
        return 0

    old_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    if old_meta.get("sha256") == digest:
        print(f"NO_CHANGE {slug} sha256={digest[:12]}")
        return 0

    old_text = snap_path.read_text(encoding="utf-8")
    diff = list(
        difflib.unified_diff(
            old_text.splitlines(),
            text.splitlines(),
            fromfile=f"{slug} (previous)",
            tofile=f"{slug} (current)",
            lineterm="",
        )
    )
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(JST).strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS / f"{slug}-{stamp}.diff"
    report_path.write_text("\n".join(diff) + "\n", encoding="utf-8")
    save_baseline(slug, target, title, text)
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    print(f"CHANGED {slug} +{added} -{removed} report={report_path}")
    for line in diff[:40]:
        print(line)
    return 2


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    init = "--init" in sys.argv
    targets = json.loads((BASE / "targets.json").read_text(encoding="utf-8"))
    if args:
        targets = [t for t in targets if t["slug"] == args[0]]
        if not targets:
            print(f"unknown slug: {args[0]}", file=sys.stderr)
            return 1
    worst = 0
    for target in targets:
        try:
            rc = check(target, init=init)
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"ERROR {target['slug']}: {e}", file=sys.stderr)
            worst = 1
            continue
        if rc == 2:
            worst = 2
        elif rc != 0 and worst == 0:
            worst = rc
    return worst


if __name__ == "__main__":
    sys.exit(main())
