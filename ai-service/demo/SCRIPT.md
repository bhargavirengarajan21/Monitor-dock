# Incident Memory — 3-minute demo script

**How to record:** open `demo/slides.html` fullscreen (press `F`), and have the app running
(`SEED_DEMO=1 python -m incident_backend`, then `http://localhost:8000`). Screen-record, read the
narration, and switch from slides to the app at the **[LIVE DEMO]** cue. Arrow keys / click advance slides.

Target: ~3:00. Word counts are tuned to ~150 wpm.

---

### [0:00–0:20] Slide 1 — Title
> "Hi — this is **Incident Memory**. When a production incident happens, the real fix gets worked
> out live on a call… and then it's gone. The next time the same error fires, someone spends an hour
> rediscovering it. Incident Memory makes that knowledge stick."

### [0:20–0:45] Slide 2 — The problem
> "You might think 'just chat with your docs.' But that misses **exact error codes** like
> ERR_PAYMENT_409 — vector search matches meaning, not strings. It quotes **stale runbooks**, it can
> leak answers **across teams**, and worst of all it **invents a fix** when it has nothing. In an
> incident, a confident wrong answer is dangerous."

### [0:45–1:10] Slide 3 — The solution
> "Incident Memory has two paths. **Capture**: an incident call is transcribed, the Meta model —
> Muse Spark — drafts a structured postmortem, and an engineer **approves it in one click**. Only
> approved postmortems become memory. **Recall**: when the alert fires again, it finds the past
> incident, checks live errors and recent deploys, and answers in seconds — **with citations**. A
> human approves everything, so an AI mistake never becomes team knowledge."

### [1:10–1:30] Slide 4 — How recall works
> "Recall is five steps: an alert arrives and is **normalized**; we apply the **team permission
> filter before retrieval**; we run **hybrid search** — keyword for exact codes, vectors for meaning,
> merged with reciprocal rank fusion; we **check the score** — and if it's too low we stop and say so;
> then Muse Spark writes the fix with **every claim cited**."

### [1:30–1:45] Slide 5 — Architecture
> "Same shape in code: webhook, permission filter, hybrid search, threshold, cited answer. On the
> capture side, approving publishes a Kafka event; an indexer chunks, embeds, and tags each chunk with
> its team into Postgres with pgvector. And every monitoring tool plugs in through **one connector
> contract** — New Relic, Prometheus, anything — without touching the core."

### [1:45–2:35] Slide 6 — [LIVE DEMO]  → switch to the app
> "Let's see it." *(switch to the browser)*
> - *Recall tab, click Payments 409, Fire:* "The alert fires. **Facts first** — the matching incident
>   at 0.9 similarity, the live error count — then the **cited answer**: the cause, and the fix that
>   worked, linked to the pull request."
> - *Switch team to `web`, fire the same alert:* "Now I'm the **web** team. Same error — but I get
>   **no match**, because that postmortem belongs to payments. Permissions are enforced."
> - *Never-seen error, Fire:* "A brand-new error? It says **'No similar incident found'** — it doesn't
>   guess."
> - *Review drafts → approve one:* "And capture: a draft postmortem, **approved** by a human — now it's
>   searchable memory."

### [2:35–2:50] Slide 8 — Tech & status
> "It's all built and working — backend, data, and frontend — **58 tests passing**, 90% hit-rate on
> our synthetic eval, sub-second answers, and it runs **fully offline with no API keys**. The
> in-memory stores swap for Postgres and Kafka in production without a rewrite."

### [2:50–3:00] Slide 9 — Closing
> "Incident Memory: the fix your team found last month, recalled in seconds — with citations,
> permissions, and the honesty to say 'I don't know.' Thank you."

---

**Tips**
- Rehearse the app clicks once so the demo section is smooth.
- If recording audio is hard, add these lines as on-screen captions instead.
- Export the deck to PDF with `P` if you need slides as a file.
