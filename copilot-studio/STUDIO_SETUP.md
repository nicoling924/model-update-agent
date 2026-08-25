# Copilot Studio transfer — feasibility study and install guide

## The study, honestly (read this first)

Copilot Studio is a conversational-agent platform: topics, generative
answers, connector actions, and Power Automate flows. It does not run
long-lived custom Python, cannot manipulate .xlsx at formula/format
fidelity (the Excel connectors are table-oriented), has no equivalent of
our 144-test regression museum or the arithmetic guard layer, and its
flows are not diffable or version-controlled. Rebuilding the agent
NATIVELY in Studio would therefore discard the referee (Police), the
evidence guards, the decision ledger, and the test discipline — the
exact architecture that failed a hundred runs before this design.

**The supported pattern that preserves everything:** the engine stays
exactly as it is, packaged in a container and deployed to Azure; Copilot
Studio becomes the FRONT DOOR. An analyst types "update DFE for FY25" in
Studio (or Teams); Studio calls the engine through a custom connector;
the engine runs with every guard, gate, and memory intact; Studio
returns the status and the finished workbook. Studio contributes what it
is actually good at — chat UX, Teams surface, Entra ID auth, tenant
governance, DLP — and the engine keeps what it is good at.

Functionality preserved: 100% (same code, same objectives, same laws).
What changes: where it runs (Azure container instead of GitHub Actions)
and how it's invoked (chat instead of a workflow button). GitHub remains
the source of truth for code, tests, and case-law commits; the container
redeploys from it.

Verify in your tenant (features vary by license/region): custom
connectors allowed in your environment; connector timeout policy (long
runs are handled by polling, so the 2-minute action limit does not bite);
whether MCP connectors are enabled (an alternative wiring, same
architecture).

## The package (this folder)

- `api.py` — HTTP wrapper around the unchanged engine (start run / poll
  status / download model), API-key protected
- `Dockerfile` — builds the whole agent into one container
- `openapi.yaml` — the custom-connector definition Studio imports
- this guide

## Install — five steps

1. **Deploy the container** (IT, ~15 min). From the repo root:
   `az containerapp up --name model-update-agent --source . --ingress external --target-port 8080`
   (or any container host). Set env vars: `LLM_API_KEY` (OpenRouter or
   internal gateway; plus `LLM_BASE_URL` if internal) and `API_KEY`
   (any secret string for the connector). Note the HTTPS hostname.
2. **Import the connector.** Power Apps / Power Automate → Custom
   connectors → Import from OpenAPI file → `openapi.yaml` → replace the
   host with your container hostname → set the security API key →
   Create. Test the `StartUpdate` action once from the connector tester.
3. **Create the agent in Copilot Studio.** New agent → name it (e.g.
   "Model Update Agent"). Instructions: "You start and track equity
   model update runs. When the user asks to update a company for a
   period, call StartUpdate with the company code and period, tell them
   the run takes 30-60 minutes, and when asked for progress call
   GetRunStatus. When a run is done, offer the DownloadModel link and
   remind them to review the _REPORT tab (first sheet): red = review,
   orange = derived."
4. **Add the three actions** (Agent → Tools/Actions → add from the
   custom connector): StartUpdate, GetRunStatus, DownloadModel. Allow
   the agent to use them dynamically, or wire a topic with trigger
   phrases like "update &lt;company&gt; &lt;period&gt;".
5. **Publish** to your channels (Teams / web). Done: "update DFE FY25"
   in Teams now presses the same button the GitHub workflow did.

## What stays in GitHub

Code, prompts, the 144-test museum, the offline benchmark gate, and the
decision-ledger commits. The deployment flow is: change → tests green →
push → redeploy container. Studio never contains logic — it contains the
doorway. This is deliberate: it is the property that kept this agent
alive where the rule-based approach died.

## Input documents

The container image ships with the staged companies. For new periods,
drop PDFs into `companies/<X>/disclosures/<PERIOD>/` and redeploy — or
mount an Azure Files share at `/app/companies` so analysts update
documents without redeploying (recommended for production).

## Relay mode — the "all-Studio brain" test version (owner request)

Set the container env var `LLM_MODE=relay` and the engine stops calling
any LLM API: it queues each judgment question, and YOUR STUDIO FLOW
answers with the built-in GPT. Wiring (Power Automate, ~30 min):

1. Recurrence trigger: every 1 minute (only while a run is active).
2. Action `GetQuestions` (custom connector). For each item in `pending`:
3. AI Builder / Copilot "Create text with GPT using a prompt" step —
   Instructions = the question's `system` + `instructions`;
   Input = the question's `user`.
4. Action `AnswerQuestion` with the question `id` and the GPT reply as
   `answer`. The engine validates; a bad reply simply comes back as a
   fresh question with the correction attached.

Honest limits of the test version: page-image (vision) reading is off in
relay mode (text extraction still covers the statements); each question
consumes Copilot message quota; very large evidence cards may exceed the
prompt step's input limit — if a question never gets answered, the run
times out on that question and reports it. This mode is for EVALUATING
the built-in GPT as a brain — production stays on a direct model API.
