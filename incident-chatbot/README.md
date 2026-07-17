# Incident Assist — Helix SRE Chatbot Prototype

A proof-of-concept AI assistant for incident management, built to demonstrate
the **hybrid model** proposed for the Helix SRE project: predefined
quick-question suggestions + free-text queries, both answered by pulling
summarized answers and next steps from historical tickets and KB docs.

This is a **demo-quality prototype**, meant to show the concept end-to-end
and support a conversation with your manager about a production build — not
a production system itself. See "From prototype to production" below for
what changes.

---

## What it does

- **Predefined suggestions (popup):** derived automatically from the most
  common ticket categories in the sample data — mirrors "suggestions derived
  from previous queries and stored documents" in the original proposal.
- **Free-text question box:** user describes a symptom or error; the backend
  searches historical tickets + KB docs and returns:
  - a summarized answer (what likely happened / how it was resolved)
  - a confidence level (high / medium / low)
  - suggested next steps (pulled from the matched ticket's resolution steps)
  - the source tickets/docs it drew from, for transparency and traceability
- **No external API or internet dependency.** Retrieval uses TF-IDF +
  cosine similarity (scikit-learn), so it runs fully offline — useful given
  the office network's outbound restrictions.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python + Flask | Lightweight, matches Python skills already in use (JWT/Flask ticket in the sample data), easy to later wrap with Jira/JSM REST calls |
| Retrieval | scikit-learn TF-IDF + cosine similarity | No API key, no GPU, fast, deterministic, explainable — good for a first demo |
| Frontend | Plain HTML/CSS/JS served by Flask | Zero build step, runs anywhere Python runs, easy to screen-share/demo |
| Data | Synthetic JSON (`data/tickets.json`, `data/kb_docs.json`) | Stand-ins for real historical JSM tickets/KB articles; swap for exports later |

## Project structure

```
incident-chatbot/
├── app.py                 # Flask backend + retrieval/answer logic
├── requirements.txt
├── data/
│   ├── tickets.json        # 21 synthetic historical incident tickets
│   └── kb_docs.json         # 8 synthetic KB articles
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── script.js
```

## Running it locally

```bash
cd incident-chatbot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000** in a browser.

## API endpoints (for reference / future integration)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/suggestions` | Returns predefined popup questions |
| POST | `/api/query` | Body: `{"query": "..."}` → returns summary, confidence, sources, next steps |
| GET | `/api/stats` | Returns indexed ticket/doc counts + categories (useful in a demo to show what it's drawing from) |

---

## How this maps to the original proposal

- **Hybrid model (predefined Qs + user queries):** implemented — sidebar
  chips are predefined, the composer box handles free text, both go through
  the same retrieval/answer pipeline.
- **Instant answers pulling from data docs / historical tickets:** implemented
  via the TF-IDF search over `tickets.json` + `kb_docs.json`.
- **Summarized answers + proposed next steps:** implemented — each answer
  includes a plain-language summary and a short list of next steps sourced
  from the matched ticket's actual resolution steps.
- **Three-sprint iteration:** see roadmap in the companion design document.

## From prototype to production

This demo intentionally skips things a production rollout would need:

1. **Real data, not synthetic.** Pull historical tickets via the Jira REST
   API (`/rest/api/3/search` with JQL against `HLXSREINP`) instead of a
   static JSON file. Requires read access — no admin permissions needed for
   this part.
2. **Better retrieval / generation.** TF-IDF is fast and explainable but
   limited on paraphrased questions. A natural next step is swapping in
   embeddings + an LLM (e.g. Claude via the Anthropic API) for the
   summarization step, while keeping the same retrieval-then-summarize
   architecture — this is the "separate AI feature track for deeper
   capabilities" mentioned in the proposal.
3. **Live ticket creation / escalation from the chat.** Currently read-only;
   a production version could let a user create a ticket, attach the chat
   transcript, or notify the on-call channel directly, using the same
   Jira REST / webhook patterns already used in the ART Team Automation Flow.
4. **Access control & auditability.** Tie into existing SSO, log every
   query/answer pair for audit (mirrors the audit-log pattern already used
   for JSM automation), and restrict which ticket fields are visible per
   role.
5. **Hosting.** Containerize (Docker) and deploy to the existing AWS/EKS
   setup already used for other services, rather than running the Flask dev
   server — the same CI/CD pipeline (GitHub Actions → Docker Hub → EKS)
   already proven out could be reused as-is.
6. **Feedback loop.** Let users flag "not helpful" answers; route those into
   a queue for KB authors to close the gap — this is what turns the bot's
   answers into a growing, self-improving KB rather than a static snapshot.

## Known limitations of this prototype

- Sample data is synthetic — realistic in shape, but not real ticket history.
- TF-IDF retrieval matches on wording/vocabulary overlap; it won't handle
  heavily paraphrased or vague questions as well as an LLM-based approach
  would.
- No authentication, no persistence of conversation history, no write-back
  to Jira — all by design, to keep the demo simple and safe to run anywhere.
