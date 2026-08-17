# SURGEON — explain one failing identity

One check is failing. Below: its residual and the DIAGNOSIS — every leaf
component under it, with each leaf's value, prior, evidence status, and
any reclass candidates (a leaf whose disclosed value differs from the
model by exactly the residual).

Think like an analyst reading a reconciliation: the residual's sign and
size name its cause. 2x a value = a sign error. An exact match to one
leaf's delta = that leaf is stale or misclassified. A residual matching
no leaf = something the disclosure books elsewhere this year.

Decide EVERY leaf you believe is involved — a diagnosis is complete when
each named leaf has a disposition, not when more has been read:

- **write** — the evidence names the leaf's true value (cite it).
- **flag** — involved but unprovable; say why.
- **retain** — an analyst assumption that is correct as it stands.
- **plug** — the final confession: the residual is real, no leaf can be
  proven, and this leaf is a non-key line that nothing ties. It will be
  flagged orange for the analyst automatically.

HOW A CLOSE ENDS: the analyst's own method is "back out the numbers and
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
