"""SharePoint-native edition — the folder IS the interface.

Point WATCH_DIR at a locally-synced SharePoint/OneDrive folder. Analysts
(or a Studio flow) drop a request file; the engine runs; results land
back in the same folder. No API, no server, no terminal for users.

Folder layout (created automatically):
    WATCH_DIR/
      inbox/                    <- drop request files here
        RUN DFE FY25.txt        <- filename IS the command (content ignored)
      companies/<X>/disclosures/<PERIOD>/   <- drop the period's PDFs
      outbox/                   <- updated models + status files appear here

Run on the engine machine:   python3 copilot-studio/sharepoint_watcher.py
Environment: WATCH_DIR (the synced folder), plus the usual engine vars.
One run at a time; a STATUS-*.txt in outbox/ narrates progress.

Brain selection (PC edition):
  LLM_MODE=api    -> direct LLM API (needs LLM_BASE_URL/LLM_API_KEY/LLM_MODEL)
  LLM_MODE=relay  -> Copilot Studio's built-in GPT answers via the queue in
                     WATCH_DIR/relay/ (a Studio Workflow works the folder);
                     no API key leaves the machine.
"""
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from updater.cli import _load_env  # noqa: E402
_load_env()

WATCH = Path(os.environ.get("WATCH_DIR", str(ROOT / "sharepoint"))).expanduser()

if os.environ.get("LLM_MODE", "").lower() == "relay":
    # queue lives INSIDE the synced folder so the Studio flow can see it,
    # and the RelayClient replaces the API client before first import.
    os.environ.setdefault("RELAY_DIR", str(WATCH / "relay"))
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        os.environ.setdefault(k, "relay")   # satisfy cli's live-run gate
    from updater import llm as _llm
    from updater.relay import RelayClient
    _llm.Client = lambda *a, **k: RelayClient()
REQ_RE = re.compile(r"^RUN[ _-]+([A-Za-z0-9]+)[ _-]+([A-Za-z0-9]+)",
                    re.I)
POLL = 15


def log_status(name, text):
    (WATCH / "outbox").mkdir(parents=True, exist_ok=True)
    (WATCH / "outbox" / f"STATUS-{name}.txt").write_text(text)


def serve_forever():
    for sub in ("inbox", "outbox", "companies"):
        (WATCH / sub).mkdir(parents=True, exist_ok=True)
    print(f"[watcher] serving {WATCH} (drop 'RUN <COMPANY> <PERIOD>.txt' "
          f"into inbox/)", flush=True)
    while True:
        for req in sorted((WATCH / "inbox").glob("*.txt")):
            m = REQ_RE.match(req.stem.strip())
            if not m:
                req.rename(WATCH / "outbox" / f"REJECTED-{req.name}")
                continue
            company, period = m.group(1).upper(), m.group(2).upper()
            name = f"{company}-{period}-{int(time.time())}"
            req.unlink()
            log_status(name, f"RUNNING {company} {period} — started "
                             f"{time.strftime('%H:%M')}, expect 30-60 min")
            print(f"[watcher] run {name}", flush=True)
            try:
                # documents: SharePoint copy wins if present
                sp_co = WATCH / "companies" / company
                eng_co = ROOT / "companies" / company
                if (sp_co / "disclosures" / period).exists():
                    dst = eng_co / "disclosures" / period
                    dst.mkdir(parents=True, exist_ok=True)
                    for f in (sp_co / "disclosures" / period).glob("*.pdf"):
                        shutil.copy2(f, dst / f.name)
                from updater.cli import main as updater_main
                yy = "".join(c for c in period if c.isdigit())[-2:]
                try:
                    code = updater_main([str(eng_co), period, f"20{yy}"])
                except SystemExit as e:
                    code = e.code
                arts = sorted((eng_co / "model").glob(
                    f"*{period}*(updater).xlsx"))
                if arts:
                    out = WATCH / "outbox" / arts[-1].name
                    shutil.copy2(arts[-1], out)
                    log_status(name, f"DONE {company} {period} — model: "
                                     f"outbox/{out.name}. Open the _REPORT "
                                     f"tab first (red = review).")
                elif code == 3:
                    log_status(name, f"PAUSED {company} {period} — "
                                     f"restatement question for the "
                                     f"analyst (see updates/).")
                else:
                    log_status(name, f"FAILED {company} {period} "
                                     f"(exit {code}) — see engine logs.")
            except Exception as e:
                log_status(name, f"FAILED {company} {period}: "
                                 f"{str(e)[:200]}")
            print(f"[watcher] finished {name}", flush=True)
        time.sleep(POLL)


if __name__ == "__main__":
    serve_forever()
