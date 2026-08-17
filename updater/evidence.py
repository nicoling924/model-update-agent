"""Evidence-graded writes — provenance bookkeeping that makes flags automatic.

BUILD_PLAN §3.1 (owner-approved): every number written carries a grade; the
flag falls out of the grade, so a flag can never be forgotten — it is not a
separate act.

    A  checksummed read / deterministic join      -> clean, no flag
    B  derived with an arithmetic tie             -> clean, listed in _REPORT
       (implied-prior, back-out formula that reconciles, inferred
       adjustment replicated from the model's own logic)
    C  inferred / uncertain / estimate            -> FFC7CE red "look here"
    D  plug / back-out without a tie              -> FFC000 orange, true-up

House colors are the CLAUDE.md two-tier convention. "Not disclosed" is NOT
a grade — it is a claim, and it requires a recorded exhausted search
(non_disclosure log) before it may be made (owner guard, 2026-08-17: past
agents lazily wrote "not disclosed" for figures that were in the document).

Pure stdlib, no I/O.
"""
from dataclasses import dataclass, field, asdict

GRADES = ("A", "B", "C", "D")
FLAG_FOR_GRADE = {"A": None, "B": None, "C": "red", "D": "orange"}


@dataclass
class Provenance:
    ref: str                 # "Sheet!U49"
    grade: str               # A/B/C/D
    method: str              # "join" / "checksum_read" / "implied_prior" / ...
    citation: str = ""       # "doc p102: line ..." — REQUIRED for A/B
    note: str = ""


@dataclass
class SearchTrail:
    """The proof behind a 'not disclosed' claim: where the agent looked."""
    row: str                 # "Sheet!49 'label'"
    looked: list = field(default_factory=list)   # human-readable steps
    verdict: str = "not_disclosed"


class EvidenceBook:
    """The run's provenance registry. One entry per written cell; the
    writer consults FLAG_FOR_GRADE so grade C/D can never ship unflagged."""

    def __init__(self):
        self.entries = {}            # ref -> Provenance
        self.non_disclosure = []     # [SearchTrail]

    def record(self, ref, grade, method, citation="", note=""):
        if grade not in GRADES:
            raise ValueError(f"unknown evidence grade {grade!r}")
        if grade in ("A", "B") and not citation:
            raise ValueError(f"grade {grade} requires a citation ({ref})")
        self.entries[ref] = Provenance(ref, grade, method, citation, note)
        return FLAG_FOR_GRADE[grade]

    def claim_not_disclosed(self, row, looked):
        """A non-disclosure claim is only accepted WITH its search trail —
        at least the direct find, the prior-value triangulation, and one
        more distinct place (statement/note/summary) must have been tried."""
        steps = [str(s) for s in (looked or []) if str(s).strip()]
        if len(steps) < 3:
            raise ValueError(
                "not-disclosed refused: record the exhausted search first "
                "(>=3 distinct places looked; 'could not find' != 'not disclosed')")
        t = SearchTrail(row=row, looked=steps)
        self.non_disclosure.append(t)
        return t

    def by_grade(self, grade):
        return [p for p in self.entries.values() if p.grade == grade]

    def dump(self):
        return {"entries": {r: asdict(p) for r, p in self.entries.items()},
                "non_disclosure": [asdict(t) for t in self.non_disclosure]}
