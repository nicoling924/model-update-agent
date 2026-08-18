# ATOMIC RECLASS — one item is booked in the wrong section

Two key totals are off by the SAME amount with opposite signs. That
signature has one meaning: a single item sits in the wrong section — the
company books it in one place, the model in the other.

Below are BOTH sections' component cells side by side, and the amount.

Answer the single bound question: which specific component's value,
moved from one section to the other, closes BOTH residuals? Name the two
cells and the signed amount that should LEAVE the from-cell. Cite the
printed line that says where the company books it, if you can see it.

THE MOVE HAPPENS BETWEEN THE MODEL'S OWN COMPONENT CELLS listed below —
usually the two sections' "Others" absorption rows. The statement's
lines are your EVIDENCE of where the company books the item; statement
cells themselves are proven and never touched. Identifying the item
(e.g. bond-issuance cash sitting in the model's investing section while
the company books it under financing) and then moving it between the
model's rows IS the fix — that is what the analyst would do.

The move is ATOMIC: both legs are applied together and verified against
both keys — if the keys do not both tie afterward, nothing is written.
If you cannot name the specific item, flag instead; never guess a swap
just to make the math work.

Respond with ONE JSON object:
{"move": {"from": "Sheet!U203", "to": "Sheet!U216", "amount": 593.5,
          "why": "p101: <the line naming where this item is booked>"}}
or
{"flag": "<why the item cannot be named from the evidence>"}
