"""The self-announcing toolbox — no tool may fail silently.

Scar-tissue guard (BUILD_PLAN §1): the learner served ZERO rows for five
straight runs on an `int(page)` type bug and nothing noticed. Under this
registry every tool reports attempted/served counts each turn; a tool that
was tried and served nothing is SURFACED to the loop as a line in its state
block — the agent investigates or routes around it, but it always KNOWS.

Pure stdlib. The loop registers callables; this wrapper only counts and
formats — it never alters a result.
"""


class Tool:
    def __init__(self, name, fn, kind="query"):
        self.name = name
        self.fn = fn
        self.kind = kind          # "query" | "write" | "control"
        self.attempted = 0
        self.served = 0

    def __call__(self, args):
        self.attempted += 1
        result = self.fn(args)
        text = str(result or "")
        if not (text.startswith("MISS") or text.startswith("REFUSED")
                or text.startswith("TOOL ERROR") or text.startswith("REVERTED")):
            self.served += 1
        return result


class Toolbox:
    def __init__(self):
        self.tools = {}

    def register(self, name, fn, kind="query"):
        self.tools[name] = Tool(name, fn, kind)

    def names(self):
        return sorted(self.tools)

    def call(self, name, args):
        if name not in self.tools:
            return f"MISS: unknown tool '{name}' (have: {', '.join(self.names())})"
        try:
            return self.tools[name](args)
        except Exception as e:
            return f"TOOL ERROR: {e}"

    def announcements(self):
        """The self-announce block: serve rates, with dead tools called out."""
        lines = []
        for t in sorted(self.tools.values(), key=lambda t: t.name):
            if not t.attempted:
                continue
            mark = ""
            if t.served == 0 and t.attempted >= 3 and t.kind != "control":
                mark = "  <== SERVING NOTHING — investigate or route around it"
            lines.append(f"  {t.name}: {t.served}/{t.attempted} served{mark}")
        return lines
