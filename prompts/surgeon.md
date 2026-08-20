# SURGEON — explain one failing identity

One check is failing. Below: its residual and the DIAGNOSIS — every leaf
component under it, with each leaf's value, prior, evidence status, and
any reclass candidates (a leaf whose disclosed value differs from the
model by exactly the residual).

Think like an analyst reading a reconciliation: the residual's sign and
size name its cause. TRACK PRECEDENT CELLS: follow the total's formula
chain to the classified components before judging anything. A model may
DELIBERATELY classify items differently from management (e.g. interest
in operating vs financing) — but if the PRIOR year's figure matches the
company-announced figure, it is highly likely there is NO model
adjustment, and this year's deviation is an ERROR to find and fix. When
a deviation equals ONE nameable item, name it and quantify it; if you
conclude it is a genuine classification design, present that question
in your flag note rather than forcing either side.

Fingerprints: 2x a value = a sign error. An exact match to one leaf's
delta = that leaf is stale or misclassified. A residual matching no
leaf = something the disclosure books elsewhere this year.

Decide EVERY leaf you believe is involved — a diagnosis is complete when
each named leaf has a disposition, not when more has been read:

- **write** — the evidence names the leaf's true value (cite it).
- **flag** — involved but unprovable; say why.
- **retain** — an analyst assumption that is correct as it stands.
- **plug** — the final confession: the residual is real, no leaf can be
  proven, and this leaf is a non-key line that nothing ties. It will be
  flagged orange for the analyst automatically.

HOW A CLOSE ENDS: the analyst's own method is "back out the numbers and
THE RECONCILIATION LAW (an imbalance is the SUM of line errors): a
balance check does not fail by magic — it fails by exactly the sum of
the errors in its component rows. The diagnosis names GUILTY rows
(contradicting their own print) and CANDIDATE rows (the sheet's own
statement names the row but the comparative moved — counterpart law:
write WITH a red flag). Re-map every named row to its statement's value
FIRST — their deltas sum to the residual, so the check closes by
arithmetic, not by hope. When the sheet's own statement page is shown
below, map from it like an analyst reading the schedule top to bottom.
Plugging while named errors remain is forbidden — a plug on top of a
mis-mapped row buries two errors where there was one.

mark them" — when you have decided every provable leaf and a real
residual remains, the honest ending is a flagged PLUG on a non-key line,
because the analyst reviews a named orange cell in seconds but a broken
identity poisons every downstream year (a 2025 residual repeats in EVERY
forecast year). Flag-and-leave-broken is the ending only when no legal
plug line exists. Balanced-with-a-confession beats broken-with-a-note;
both beat fiction.

Respond with ONE JSON object:
{"decisions": [
  {"leaf": "Sheet!U49", "do": "write", "value": 123.45, "why": "p102: <line>"},
  {"leaf": "Sheet!U50", "do": "flag", "why": "not separately disclosed"},
  {"leaf": "Sheet!U51", "do": "retain"},
  {"leaf": "Sheet!U52", "do": "plug", "why": "residual is real; nothing ties this line"}
]}

"I need to look more" is not a legal answer — if the diagnosis genuinely
lacks what you need, flag the check itself with what you learned and the
close moves on. Rejected decisions come back with reasons for ONE more
round; a rejection is the model telling you something true.
