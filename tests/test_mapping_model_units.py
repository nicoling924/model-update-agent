import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.mapping import verdict


def _loop():
    ns = runpy.run_path(str(Path(__file__).with_name("test_pipeline_museum.py")))
    loop, pages, _ = ns["_map_model"]()
    return loop, pages


def test_verified_quote_accepts_explicit_model_units_as_red():
    loop, pages = _loop()
    loop.ledger.items = []
    value, plain, why, evidence = verdict(
        loop,
        {"sheet": "Final", "coord": "C9", "printed": 460.0,
         "value": 0.46, "doc": "ar.pdf", "page": 23,
         "line": "Other gains, net 460 420",
         "because": "The page is in thousands; divide by 1,000 for model Rmb m."},
        pages, {"ar.pdf"}, lambda *_: None)
    assert value == 0.46 and plain is False
    assert evidence["doc"] == "ar.pdf" and evidence["page"] == 23
    assert "comparative reconciliation remains unresolved" in why


def test_absent_quote_still_refuses_explicit_model_units():
    loop, pages = _loop()
    value, plain, why, evidence = verdict(
        loop,
        {"sheet": "Final", "coord": "C9", "printed": 999999999.0,
         "value": 999.0, "doc": "ar.pdf", "page": 23,
         "line": "Other gains, net 999999999 888888888",
         "because": "Explicit conversion to model units."},
        pages, {"ar.pdf"}, lambda *_: None)
    assert value is None and plain is False
    assert "absent" in why
    assert evidence == {}


def test_zero_semantics_refuse_without_printed_nil_even_with_model_value():
    loop, pages = _loop()
    value, plain, why, evidence = verdict(
        loop,
        {"sheet": "Final", "coord": "C3", "printed": 0.0,
         "value": 0.0, "doc": "ar.pdf", "page": 23,
         "line": "Other gains, net 0 420",
         "because": "The source is in model units."},
        pages, {"ar.pdf"}, lambda *_: None)
    assert value is None and plain is False
    assert "no line on file prints a nil" in why
    assert evidence == {}


def test_explicit_model_units_override_conflicting_automatic_scale_as_red():
    loop, pages = _loop()
    loop.ledger.items = []
    loop.__dict__["_map_scales"] = {("ar.pdf", 23): 100.0}
    pages = dict(pages)
    pages[("ar.pdf", 23)] = "Other gains, net 64534400 54908265.5522"
    value, plain, why, evidence = verdict(
        loop,
        {"sheet": "Final", "coord": "C9", "printed": 64534400.0,
         "value": 6453.44004842, "doc": "ar.pdf", "page": 23,
         "line": "Other gains, net 64534400 54908265.5522",
         "because": "The explicit model-unit value is in Rmb m; the page scale is incompatible."},
        pages, {"ar.pdf"}, lambda *_: None)
    assert value == 6453.44004842 and plain is False
    assert "conflicts with automatic conversion" in why
    assert evidence["automatic_model_value"] == -645344.0


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().copy().items()
             if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print("PASS", name)
    print(f"{len(tests)} tests passed")
