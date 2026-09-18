import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.mapping import _numeric_operands, literal_template


def test_signed_numeric_literals_keep_formula_shape():
    assert literal_template("=+-2254+235") == literal_template("=-1860+194")
    assert literal_template("=94-AI29-AI28") == literal_template("=-441-AI29-AI28")
    assert _numeric_operands("=+-2254+235") == [-2254.0, 235.0]
    assert _numeric_operands("=-1860+194") == [-1860.0, 194.0]


def test_reference_signs_and_binary_operators_remain_structural():
    assert literal_template("=A1-B1") != literal_template("=A1+B1")
    assert literal_template("=A1-B1") != literal_template("=A1-(-B1)")
    assert literal_template("=94-AI29-AI28") != literal_template("=94+AI29-AI28")


def test_prefix_sign_on_reference_is_not_treated_as_numeric_literal_sign():
    assert literal_template("=-AI29") != literal_template("=AI29")



def test_numeric_compositions_can_change_without_rewiring_outputs():
    import runpy
    from pipeline.mapping import verdict, is_constant_expression
    fixture = runpy.run_path(str(Path(__file__).with_name("test_pipeline_museum.py")))
    loop, pages, _ = fixture["_map_model"]()
    loop.wb["Final"]["C4"] = "=10-3+2"
    value, *_ = verdict(loop, {"sheet":"Final", "coord":"C4", "formula":"=12-4-5+1"}, pages, {"ar.pdf"}, lambda *a:None)
    assert value == "=12-4-5+1"
    loop.wb["Final"]["C4"] = "=C2-C3"
    value, *_ = verdict(loop, {"sheet":"Final", "coord":"C4", "formula":"=12-4-5+1"}, pages, {"ar.pdf"}, lambda *a:None)
    assert value is None
    assert not is_constant_expression("=10-C2")
    assert not is_constant_expression('=HYPERLINK("x",1)')

if __name__ == "__main__":
    tests = [(name, fn) for name, fn in globals().copy().items() if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print("PASS", name)
    print(f"{len(tests)} tests passed")
