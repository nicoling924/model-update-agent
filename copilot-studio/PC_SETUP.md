# PC edition — run the whole agent from your Windows machine + Copilot Studio

Everything stays inside three places you already have: **your Windows PC**
(runs the engine), **SharePoint** (the shared folder is the interface), and
**Copilot Studio** (its built-in GPT-5.6 Reasoning is the brain, via the
relay queue). No Azure, no GitHub, no external API key required.

```
Analyst                SharePoint folder                 Your PC
  |  drop RUN file  ->   inbox/                           |
  |                      companies/<X>/disclosures/  <-- PDFs
  |                      relay/   <--- questions ---  engine (Python)
  |   Copilot Studio Workflow answers each question
  |                      relay/   ---- answers ---->  engine continues
  |  updated model  <-   outbox/  <-- model + STATUS  engine finishes
```

## Part 1 — the engine on your PC (15 min)

1. **Python**: install "Python 3.12" from the **Microsoft Store** (usually
   allowed on corporate PCs — no admin rights needed). If the Store is
   blocked, ask IT for Python 3.10+; nothing else is needed.
2. **Unzip** `agent-package-windows.zip` anywhere, e.g. `C:\Users\<you>\agent\`.
3. Double-click **`copilot-studio\setup-windows.bat`** (installs 5 Python
   libraries into your user profile — no admin).
4. **Sync the SharePoint folder**: create a folder (e.g. `ModelUpdateAgent`)
   in your SharePoint site / OneDrive, click **Sync** so it appears in File
   Explorer. Put its local path into `.env` as `WATCH_DIR`.
5. Keep `LLM_MODE=relay` in `.env` (Studio is the brain). If you have a
   usable API key instead, switch to the `api` block — faster, and vision
   reading works.
6. Double-click **`copilot-studio\start-agent.bat`**. Leave the window open —
   that's the agent, serving the folder.

**Smoke test without Studio** (proves Part 1 alone): with `LLM_MODE=relay`,
drop `RUN DFE FY25.txt` into `inbox\`. Question files appear in `relay\` —
that's the engine asking its first judgment questions. (You can even answer
one by hand to see the loop move: copy a question into any GPT chat, save the
reply as `<id>.answer.json` with content `{"answer": "<the reply>"}`.)

## Part 2 — Copilot Studio as the brain (the relay Workflow)

In Copilot Studio (the screen you screenshotted) → **Workflows** → new flow:

1. **Trigger**: *When a file is created in a folder* (SharePoint) — pick your
   site and the `relay` folder.
2. **Condition**: file name ends with `.question.json` (ignore answer files —
   this prevents a loop).
3. **Get file content** (SharePoint).
4. **Parse JSON** on the content. Schema:
   ```json
   {"type":"object","properties":{"id":{"type":"string"},
    "system":{"type":"string"},"user":{"type":"string"},
    "instructions":{"type":"string"}}}
   ```
5. **Run a prompt** (the AI prompt action — this is where the built-in
   GPT-5.6 Reasoning does the thinking). Prompt text:
   > You are answering one question for a financial model-update engine.
   > Follow the SYSTEM and USER sections exactly. Reply with ONE JSON object
   > only — no prose, no markdown fences.
   >
   > SYSTEM: `[system from Parse JSON]`
   > USER: `[user from Parse JSON]`
6. **Create file** (SharePoint) in the same `relay` folder:
   - Name: `[id].answer.json`
   - Content (expression — this JSON-escapes the model's reply safely):
     `string(setProperty(json('{}'), 'answer', outputs('Run_a_prompt')?['body/responsev2/predictionOutput/text']))`
     *(pick the prompt action's Text output from the dynamic-content list if
     the path differs)*

That's the whole brain. The engine polls `relay\`, sees the answer, deletes
both files, and moves on. A full run asks ~40–60 questions; the proof run
completed 52 this way.

## Part 3 (optional) — Teams as the front desk

Give the Studio **agent** (Build tab) these Instructions, plus SharePoint
tools, so analysts never touch the folder:

> You operate the Model Update Agent. When the user asks to update a model
> (e.g. "run DFE FY25"), create an EMPTY file named "RUN <COMPANY>
> <PERIOD>.txt" in the SharePoint folder "ModelUpdateAgent/inbox". To report
> progress, read the newest "STATUS-*.txt" in "ModelUpdateAgent/outbox" and
> summarise it in one sentence. When status says DONE, give the user the
> link to the model file in outbox and remind them: open the _REPORT tab
> first; red cells need analyst review. You never edit models yourself, and
> you never invent statuses — only report what the STATUS file says.

Publish to Teams, and the analyst experience is: chat "run DFE FY25" → get
the updated model back with the _REPORT tab on top.

## Test ladder (do them in this order)

| Step | Proves | How |
|---|---|---|
| 1 | Engine runs on Windows | `setup-windows.bat`, then drop `RUN DFE FY25.txt`, watch `relay\` fill |
| 2 | Studio answers questions | Build the Part 2 Workflow, re-drop the RUN file, watch answers appear |
| 3 | Full confined run | Leave it ~1–2 h (relay is slower than API); model lands in `outbox\` |
| 4 | Teams front desk | Part 3 agent, chat "run DFE FY25" |

## Known limits of relay mode (by design, test version)

- **Slower**: each question waits for the flow (sync + flow run), so a run
  takes 1–2 h instead of 30–60 min.
- **No vision**: scanned-image pages fall back to text channels.
- **Flow quotas**: Power Platform daily action limits apply; ~60 questions ×
  ~6 actions is well within personal limits.
- Your PC must stay on (not sleeping) for the duration of a run.
