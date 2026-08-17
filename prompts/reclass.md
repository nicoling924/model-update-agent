# ATOMIC RECLASS — one item is booked in the wrong section

Two key totals are off by the SAME amount with opposite signs. That
signature has one meaning: a single item sits in the wrong section — the
company books it in one place, the model in the other.

Below are BOTH sections' component cells side by side, and the amount.

Answer the single bound question: which specific component's value,
moved from one section to the other, closes BOTH residuals? Name the two
cells and the signed amount that should LEAVE the from-cell. Cite the
printed line that says where the company books it, if you can see it.

The move is ATOMIC: both legs are applied together and verified against
both keys — if the keys do not both tie afterward, nothing is written.
If you cannot name the specific item, flag instead; never guess a swap
just to make the math work.

Respond with ONE JSON object:
{"move": {"from": "Sheet!U203", "to": "Sheet!U216", "amount": 593.5,
          "why": "p101: <the line naming where this item is booked>"}}
or
{"flag": "<why the item cannot be named from the evidence>"}
