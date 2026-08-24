# COMMENTARY — one line per key figure, for the analyst's report page

You are writing the "why" column of a results summary an equity analyst
will skim in ten seconds per line. For each key figure below you get the
actual, the prior year, and the model's previous estimate, plus the
period's largest segment/driver moves as context.

Write ONE short factual sentence per key figure explaining the move,
built ONLY from the numbers and segment moves given — no speculation, no
adjectives, no outlook. House style: "Sales +12.8% YoY, largely volume
(+15%) offset by ASP (−2%)" / "NP fell 8% on the one-off impairment;
recurring NP flat". Under 120 characters each. If the context genuinely
does not explain a move, say what moved arithmetically ("GP margin fell
2.1pp on cost of sales +18%") — never invent causes.

Respond with ONE JSON object mapping key name -> sentence:
{"revenue": "…", "net profit": "…"}
