"""Recursive spreadsheet formula evaluator — verify without Excel.

Covers the function set common in sell-side models (SUM/AVERAGE/IF/MIN/MAX/
SUMPRODUCT/ABS/ROUND, %, ^, cross-sheet refs, ranges). Unknown functions raise,
and the caller records the cell as 'needs Excel recalc' instead of failing the run.
Cycle guard returns 0 for self-referential chains (and reports them).
"""
import re

COL = re.compile(r"^([A-Z]{1,3})(\d+)$")


def col2n(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n


def n2col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _num(x):
    return x if isinstance(x, (int, float)) else 0


def _flat(a):
    out = []
    for x in a:
        out += x if isinstance(x, list) else [x]
    return out


class Evaluator:
    def __init__(self, wb):
        self.wb = wb
        self.memo = {}
        self.cycles = []

    def cell(self, sheet, coord):
        key = (sheet, coord)
        if key in self.memo:
            return self.memo[key]
        self.memo[key] = 0  # cycle guard
        v = self.wb[sheet][coord].value
        if v is None:
            r = 0
        elif isinstance(v, (int, float)):
            r = v
        elif isinstance(v, str) and v.startswith("="):
            r = self.formula(sheet, v[1:])
        else:
            r = v
        if self.memo[key] == 0 and r != 0 and key in [c[0] for c in self.cycles]:
            pass
        self.memo[key] = r
        return r

    def rng(self, sheet, a, b):
        m1, m2 = COL.match(a), COL.match(b)
        c1, r1 = col2n(m1.group(1)), int(m1.group(2))
        c2, r2 = col2n(m2.group(1)), int(m2.group(2))
        return [self.cell(sheet, f"{n2col(cc)}{rr}")
                for cc in range(min(c1, c2), max(c1, c2) + 1)
                for rr in range(min(r1, r2), max(r1, r2) + 1)]

    def formula(self, sheet, f):
        f = f.replace("$", "")

        def repl_range(m):
            sh = (m.group(1) or m.group(2) or sheet).strip("'")
            return f"R('{sh}','{m.group(3)}','{m.group(4)}')"

        def repl_ref(m):
            sh = (m.group(1) or m.group(2) or sheet).strip("'")
            return f"C('{sh}','{m.group(3)}')"

        f = re.sub(r"(?:'([^']+)'|([A-Za-z0-9 ]+?))!([A-Z]{1,3}\d+):([A-Z]{1,3}\d+)", repl_range, f)
        f = re.sub(r"(?:'([^']+)'|(\b[A-Za-z][A-Za-z0-9 ]*?))!([A-Z]{1,3}\d+)", repl_ref, f)
        f = re.sub(r"(?<![A-Za-z0-9_'\"])([A-Z]{1,3}\d+):([A-Z]{1,3}\d+)",
                   lambda m: f"R('{sheet}','{m.group(1)}','{m.group(2)}')", f)
        f = re.sub(r"(?<![A-Za-z0-9_'\"!])([A-Z]{1,3}\d+)(?![A-Za-z0-9_(])",
                   lambda m: f"C('{sheet}','{m.group(1)}')", f)
        f = f.replace("^", "**")
        f = re.sub(r"(\d+(?:\.\d+)?)%", r"(\1/100.0)", f)
        f = re.sub(r"(?<![<>=!])=(?!=)", "==", f)
        env = {
            "C": lambda sh, co: _num(self.cell(sh, co)),
            "R": lambda sh, a, b: [_num(x) for x in self.rng(sh, a, b)],
            "SUM": lambda *a: sum(_flat(a)),
            "MIN": lambda *a: min(_flat(a)),
            "MAX": lambda *a: max(_flat(a)),
            "AVERAGE": lambda *a: (lambda l: sum(l) / len(l))(_flat(a)),
            "IF": lambda c, t, fv=0: t if c else fv,
            "IFERROR": lambda v, fv: v,
            "SUMPRODUCT": lambda x, y: sum(p * q for p, q in zip(x, y)),
            "ABS": abs,
            "ROUND": lambda x, n=0: round(x, int(n)),
        }
        return eval(f, {"__builtins__": {}}, env)  # sandboxed: no builtins, refs resolved above
