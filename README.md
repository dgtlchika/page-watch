# page-watch

A tiny page-change monitor: fetch a public web page, normalize its main text, hash it (SHA-256), and report a unified diff when the content changes.

Built to watch the [IPA Fundamental Information Technology Engineer exam page](https://www.ipa.go.jp/shiken/kubun/fe.html) for syllabus / schedule changes, and to run unattended every morning — first on a local VM, then migrated to a small VPS (systemd timer, 07:29 JST daily).

## How it works

- Targets are listed in `targets.json` (`name`, `slug`, `url`, optional CSS `selector`)
- State per target lives in `state/<slug>.txt` (normalized text snapshot) and `state/<slug>.json` (metadata: title, sha256, updated_at)
- On change, a diff is written to `reports/<slug>-<timestamp>.diff`
- Exit codes: `0` = no change / baseline saved, `2` = change detected, `1` = fetch or config error — cron/timer friendly

## Usage

```bash
pip install "scrapling[fetchers]"
python page_watch.py            # check all targets
python page_watch.py ipa-fe     # check one target
```

First run saves the baseline; later runs compare against it.

## Running it on a timer (systemd, user)

```ini
# ~/.config/systemd/user/page-watch.timer
[Timer]
OnCalendar=07:29
Persistent=true
```

See the Digital Basement build log (Japanese) for the migration story: [note.com/sumaho_lab](https://note.com/sumaho_lab)

## Notes

- Be polite: this is meant for low-frequency checks (daily) of pages you genuinely need to watch.
- Text extraction uses Scrapling's `Fetcher` and ignores `script`/`style` content.
