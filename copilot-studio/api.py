"""HTTP wrapper for the model-update engine — the Copilot Studio front door.

The engine is unchanged (same updater/, same guards, same tests); this
wrapper exposes it as three endpoints a Copilot Studio custom connector
can call:

    POST /update            {"company": "DFE", "period": "FY25"} -> {run_id}
    GET  /runs/{run_id}     -> {status, summary, police, artifact_url}
    GET  /runs/{run_id}/model  -> the updated .xlsx (binary)

Auth: X-API-Key header (set API_KEY env var). Runs execute in a
background thread; state is kept on disk under runs/ so the container
can answer status polls cheaply. One run at a time per company (the
one-run-one-hour law).
"""
import json
import os
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
RUNS.mkdir(exist_ok=True)
app = FastAPI(title="Model Update Agent", version="1.0")
_lock = threading.Lock()
_active = set()


def _auth(key):
    want = os.environ.get("API_KEY")
    if want and key != want:
        raise HTTPException(401, "bad API key")


def _run(run_id, company, period):
    state = {"status": "running", "company": company, "period": period,
             "started": time.time()}
    sp = RUNS / f"{run_id}.json"
    sp.write_text(json.dumps(state))
    log_lines = []
    try:
        import sys
        sys.path.insert(0, str(ROOT))
        from updater.cli import main as updater_main
        yy = "".join(c for c in period if c.isdigit())[-2:]
        code = updater_main([str(ROOT / "companies" / company), period,
                             f"20{yy}"])
        state["status"] = "done" if code in (0, None) else (
            "paused" if code == 3 else "failed")
    except SystemExit as e:
        state["status"] = ("done" if e.code in (0, None)
                           else "paused" if e.code == 3 else "failed")
    except Exception as e:
        state["status"] = "failed"
        state["error"] = str(e)[:300]
    finally:
        model_dir = ROOT / "companies" / company / "model"
        arts = sorted(model_dir.glob(f"*{period}*(updater).xlsx"))
        if arts:
            state["model_path"] = str(arts[-1])
        state["finished"] = time.time()
        state["log_tail"] = log_lines[-20:]
        sp.write_text(json.dumps(state))
        with _lock:
            _active.discard(company)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/update")
def update(body: dict, x_api_key: str = Header(default="")):
    _auth(x_api_key)
    company = str(body.get("company", "")).strip()
    period = str(body.get("period", "")).strip()
    if not (ROOT / "companies" / company).exists():
        raise HTTPException(404, f"unknown company '{company}'")
    if not (ROOT / "companies" / company / "disclosures" / period).exists():
        raise HTTPException(404, f"no disclosures for period '{period}'")
    with _lock:
        if company in _active:
            raise HTTPException(409, f"a run for {company} is already "
                                     f"in progress (one run at a time)")
        _active.add(company)
    run_id = uuid.uuid4().hex[:12]
    threading.Thread(target=_run, args=(run_id, company, period),
                     daemon=True).start()
    return {"run_id": run_id, "status": "running",
            "note": "poll GET /runs/{run_id}; a run takes 30-60 minutes"}


@app.get("/runs/{run_id}")
def run_status(run_id: str, x_api_key: str = Header(default="")):
    _auth(x_api_key)
    sp = RUNS / f"{run_id}.json"
    if not sp.exists():
        raise HTTPException(404, "unknown run")
    return json.loads(sp.read_text())


@app.get("/runs/{run_id}/model")
def run_model(run_id: str, x_api_key: str = Header(default="")):
    _auth(x_api_key)
    sp = RUNS / f"{run_id}.json"
    if not sp.exists():
        raise HTTPException(404, "unknown run")
    st = json.loads(sp.read_text())
    p = st.get("model_path")
    if not p or not Path(p).exists():
        raise HTTPException(404, "no model artifact for this run")
    return FileResponse(p, filename=Path(p).name)
