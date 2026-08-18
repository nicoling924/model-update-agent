# REDESIGN — the thinking agent (council synthesis, 2026-08-18)

**Status: PROPOSAL — owner approval required before any code changes.**
Sources: RETHINK.md (self-diagnosis), the council session (transcript in
council/2026-08-18-thinking-question-council.md; rankings C > A > B, all
four members unanimous on the core diagnosis).

## The council's unanimous diagnosis

The one-action-per-turn global loop plus a 15-law prompt turned a decent
diagnostic model into "a lost formula-tourist": compliance classification
each turn, no case ownership, no durable plan, exploration as cheap as
completion. The guards were right; using rules to steer behavior was the
patch spiral. The fix is to change the UNIT OF WORK, not add rules.

## The redesign (what gets built)

### 1. Packetized two-level loop (replaces the global loop)

The deterministic layer publishes a **packet queue** — the only source of
objectives, derived generically from the workbook itself (inventory,
checks, ledger coverage, Police findings — no per-company logic):

    ground                     — rollover, join, headline locks
    compile:<statement>:<year> — fill one statement's open column
    seam:<name>                — NI->RE, cash roll, WC ties
    residual:<check_id>        — one failing check
    repair:<police_law>        — police findings
    deliver                    — finish honestly

- **L0 planner (rare, ~10-15 calls):** sees the scorecard, the queue, the
  last packet report. Writes a short situation + picks the next packet
  (may reorder/skip; may request a bounded "expand neighborhood" packet —
  Terra's caveat — but cannot invent free-roam exploration).
- **L1 closer (focused):** sees ONLY the packet card + a state slice
  (that statement/section, its open cells, prior anchors, ledger hits,
  the 5 standing rules). Never sees the full history, other statements,
  or a law book.

### 2. Two worker modes (the conversion engine)

- **Compiler** (`compile` packets): ONE call emits the whole open column
  as a write array — every value cited or flagged `not_disclosed` — the
  frontier clean-room method made mechanical. The chokepoint applies each
  write transactionally and returns an APPLY REPORT (accepted / rejected:
  reason / still open). One repair pass on the remainder, then the packet
  closes; identity failures become `residual` packets. Compile packets
  have NO inspect tools.
- **Surgeon** (`seam`/`residual`/`repair` packets): the runtime
  AUTO-SURFACES the diagnostic leaf tree (depth-1 components, which are
  stale/tied/assumption, sign and magnitude vs the residual — including
  reclass candidates). The next output MUST be a `decisions[]` array —
  write / flag / retain / plug per leaf. "I looked" is schema-invalid.
  Inspect (`inspect_leaf`, depth-1) exists only here, once per cell per
  packet unless the apply report introduced a new fact (defined
  deterministically: a rejection reason, a new ledger hit, or a changed
  residual).

Every case ends in one of five dispositions (Response A's taxonomy —
this also becomes the _REPORT vocabulary): cited actual · correct
derivation · retained analyst assumption · flagged uncertainty · flagged
plug on a designated non-key line.

### 3. The prompt: a method, not a rulebook

The 15 laws are deleted. The L1 prompt teaches the analyst's epistemology
(the council's method text, adapted): facts are not levers; adjustments
stay unless replaced; computed cells move through inputs; residuals are
information (sign/size/path name the missing leaf); a plug is a confession
of incompleteness, flagged, on a designated non-key line; unbalanced and
honest beats balanced and fictional. Order of work: ground -> fill by
statement top-to-bottom at full precision -> seams -> residual decisions
-> deliver honestly.

**Five standing rules survive (nothing else):**
1. Truth outranks balance — never move a disclosed/tied value to satisfy
   an identity.
2. No key without a citation — otherwise flag it.
3. Analyst adjustments are read-only unless the disclosure replaces them.
4. Plug only a designated non-key line, always flagged.
5. Always deliver; every remaining uncertainty carries a visible flag.

### 4. Call budget (~250 available, target ~150 used)

L0 10-15 · compile 30-40 · surgeon 50-70 · police repair 25-30 · slack 20.
Act : plan : reflect ≈ 80 : 12 : 8. Reflection lives only in L0.

## What is DELETED

- The one-action-per-turn global JSON loop.
- The 15-law prompt: walk-away, third-look-is-a-plug, steering nudges,
  plug casuistry, trace caps — all of it.
- Free-roam `trace_cell` and full formula-chain dumps.
- The full action-history/global state block re-rendered every turn.
- Agent-invented objectives ("understand the model better").

## What is KEPT (unchanged, now SILENT)

- The deterministic substrate: ledger, joins, checksummed/vision reads,
  scale doctrine, anatomy discovery, restatement pause.
- The ONE write chokepoint with every guard (transactional revert,
  world band, truth-guard/tie-lock, key protection, plug-once,
  check-rows-only) — as chokepoint REJECTION REASONS in apply reports,
  never as prompt text. Mid-tier learns from this run's rejections, not
  a cemetery of past failures.
- The Police (4 laws), structural honesty (stale auto-flag, failing-check
  marks, pre-finish auto-flagging), always-deliver, _REPORT/_SPEC,
  evidence grades, the museum + replay + dry-run discipline.

## Why this is not another patch

Every prior fix reshaped the agent's behavior inside an unchanged loop.
This changes the loop to match how the job is actually done (fill a
statement; explain a residual; decide each leaf once) and deletes the
accumulated steering. The guards that remain are invisible until touched.
It is also MORE generic, not less: packets derive from any workbook's own
checks and inventory; nothing in the design knows a company, a language,
or a layout.

## Build plan (on approval — no dispatches until dry-proven)

1. `packets.py` — queue derivation (generic, deterministic) + state
   slicing per packet type.
2. `closer.py` — L1 compile/surgeon sessions, apply reports, decisions[]
   schema gate; `planner.py` — L0.
3. Rewrite `prompts/` as method + five rules (+ compile/surgeon cards).
4. Auto-surfaced diagnostic leaf trees (from the existing diagnose logic,
   inverted: pushed to the agent, not pulled by it).
5. Museum: new exhibits for the schema gate, packet closure, apply-report
   contract; ALL existing substrate exhibits stay green.
6. Dry runs on DFE + CLP; then ONE live run, report card first.

Estimated effort: the agent layer only (~2 focused sessions); the
substrate is untouched.

## 2026-08-18 (night) — EXTRACTION-FIRST (council #5, owner-directed fundamental fix)

Owner: "a half edited agent shouldnt waste my time... if u think its a
fundamental issue then fix it fundamentally." Council unanimous: the
evidence channels were a patch spiral; the cut is ONE reading stage whose
output is complete and PROVEN before mapping starts.

Built: updater/reading.py (manifest/entity quarantine -> spine read +
closure + articulation with bounded live repair -> demand-driven notes ->
sufficiency inventory, ridden into _REPORT). Parent-company pages evicted
by banner + anchor arbitration (run-24 police had cited a parent CF page
as "print"). Face vocabulary bug fixed everywhere (pl, not is — the CF
face was invisible to closure AND the statements transcript). Barrier law
in closure (活动净额 rows end sections). tools/benchmark.py = gate v2:
every paid-for failure class scored OFFLINE on the live run's own world
(replay-ledger vision seeding); no head dispatches without the WHOLE
benchmark green. Pins that only agent judgment can cover are watch-listed,
not gated — the benchmark never lies about what code proved.

Result on DFE (offline): 144 rows served deterministically (was 50);
282/339 priors located; CFI/CFF twin dead (proven zero SERVED by the
join); all coverage + pins green; museum 91.
