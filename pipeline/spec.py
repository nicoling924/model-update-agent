"""The run spec — everything company-specific, as DATA, never as code.

Genericity law (owner mandate): the department's models differ in language,
format, style, company, industry. Code must not know any of them. What a
run needs to know about one model — the year axis, check rows, key rows,
backout rules, aliases — is data, loaded in priority order:

1. `spec.yaml` in the company folder (analyst-reviewed; `draft: true`
   refuses to run);
2. the workbook's own hidden `_SPEC` tab (the model carries its memory —
   it travels with the file, per the house design);
3. neither -> the run stops with a clear message: cold-start discovery is
   an analyst/LLM step, not something deterministic code may guess.

The `_SPEC` tab is text-only and small: a JSON document in column A,
chunked across rows (Excel cells cap at 32k chars). After a run, the
updated spec (new anchors, resolved mappings, carried flags) is written
back so the next run is a warm run.
"""
import json
from pathlib import Path

SPEC_SHEET = "_SPEC"
_CHUNK = 30000

REQUIRED = ("year_axis",)


class SpecError(RuntimeError):
    pass


def validate(spec):
    missing = [k for k in REQUIRED if not spec.get(k)]
    if missing:
        raise SpecError(f"spec missing required keys: {missing}")
    if spec.get("draft"):
        raise SpecError("spec is a draft — an analyst must review it and "
                        "set draft: false before a run may use it")
    return spec


def load(company_dir, wb=None):
    """Spec for a run: spec.yaml first, then the workbook's _SPEC tab."""
    company_dir = Path(company_dir)
    y = company_dir / "spec.yaml"
    if y.exists():
        import yaml
        return validate(yaml.safe_load(y.read_text(encoding="utf-8")) or {})
    j = company_dir / "spec.json"
    if j.exists():
        return validate(json.loads(j.read_text(encoding="utf-8")))
    if wb is not None and SPEC_SHEET in wb.sheetnames:
        spec = read_spec_tab(wb)
        if spec:
            return validate(spec)
    raise SpecError(
        f"no spec found for {company_dir.name}: provide spec.yaml/spec.json "
        f"or a _SPEC tab in the workbook (cold-start discovery is a "
        f"reviewed step, never a runtime guess)")


def read_spec_tab(wb):
    ws = wb[SPEC_SHEET]
    parts = []
    for r in range(2, min(ws.max_row, 200) + 1):
        v = ws[f"A{r}"].value
        if isinstance(v, str):
            parts.append(v)
    text = "".join(parts).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def write_spec_tab(wb, spec):
    """Write the spec back into the workbook (hidden, text-only, small)."""
    if SPEC_SHEET in wb.sheetnames:
        ws = wb[SPEC_SHEET]
        for row in ws.iter_rows():
            for c in row:
                c.value = None
    else:
        ws = wb.create_sheet(SPEC_SHEET)
    ws.sheet_state = "hidden"
    ws["A1"] = ("_SPEC (auto-managed): per-company run knowledge as JSON. "
                "Text only — never paste data or formatting here.")
    text = json.dumps(spec, ensure_ascii=False, separators=(",", ":"))
    for i in range(0, len(text), _CHUNK):
        ws[f"A{2 + i // _CHUNK}"] = text[i:i + _CHUNK]
    return ws
