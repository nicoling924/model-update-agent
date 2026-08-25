"""THE DECISION LEDGER (council ruling 2026-08-25, owner-approved).

The agent's judgment calls become case law instead of dice rolls: the
FIRST time a judgment is made it is recorded — keyed by the row and
stamped with a fingerprint of the evidence it was based on — and every
later run (H1, Q1, next year's FY) REPLAYS the decision instead of
re-asking, until the filing's evidence changes, at which point the entry
is invalidated and the agent judges fresh.

Code decides NOTHING here (the 100-failed-runs law): entries are written
by the agent's own outcomes or the analyst's overrides, never by rules.
Flags persist — an ambiguous cell stays visibly ambiguous run after run
instead of outcome-shopping. The analyst deletes or edits an entry to
overrule it permanently.

Storage: companies/<X>/updates/decisions.json (repo-persisted so CI runs
inherit it) merged with the workbook's _SPEC copy.
"""
import hashlib
import json
from pathlib import Path

LEDGER_FILE = "decisions.json"


def evidence_hash(card_text):
    """Fingerprint of the evidence a judgment was based on. The card text
    for the row (its description + evidence lines) IS the judgment's
    world — if the filing changes it, the hash moves and the decision is
    re-made."""
    t = " ".join(str(card_text).split())
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


class DecisionLedger:
    def __init__(self, company_dir=None, spec_d=None):
        self.path = (Path(company_dir) / "updates" / LEDGER_FILE
                     if company_dir else None)
        self.data = {}
        if self.path and self.path.exists():
            try:
                self.data = json.loads(self.path.read_text())
            except Exception:
                self.data = {}
        # the workbook's _SPEC copy rides along (the model carries its
        # memory even outside the repo)
        for k, v in ((spec_d or {}).get("decisions") or {}).items():
            self.data.setdefault(k, v)
        self.replayed = 0
        self.recorded = 0

    @staticmethod
    def key(sheet, row, kind="compile"):
        return f"{sheet}!{row}:{kind}"

    def lookup(self, sheet, row, ehash, kind="compile"):
        d = self.data.get(self.key(sheet, row, kind))
        if d and (d.get("analyst") or d.get("evidence_hash") == ehash):
            # an ANALYST ruling is sticky: it replays until the analyst
            # edits or deletes it, whatever the filing does
            return d
        return None

    def analyst_entries(self):
        """[(sheet, row, entry)] for sticky analyst rulings — applied at
        the TOP of the run, before any deterministic serve (the analyst
        outranks the joins)."""
        out = []
        for k, d in self.data.items():
            if not d.get("analyst"):
                continue
            m = k.split(":", 1)[0]
            sheet, _, row = m.rpartition("!")
            try:
                out.append((sheet, int(row), d))
            except ValueError:
                continue
        return out

    def record(self, sheet, row, ehash, action, payload=None, flag=False,
               why="", kind="compile"):
        prev = self.data.get(self.key(sheet, row, kind))
        if prev and prev.get("analyst"):
            return                      # never overwrite the analyst
        self.data[self.key(sheet, row, kind)] = {
            "evidence_hash": ehash, "action": action,
            "payload": payload, "flag": bool(flag),
            "why": str(why)[:200]}
        self.recorded += 1

    def save(self, spec_d=None):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=1,
                                            ensure_ascii=False))
        if spec_d is not None:
            spec_d["decisions"] = self.data
        return len(self.data)
