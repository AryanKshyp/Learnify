# PRODUCT_STRATEGY_REVIEW.md — Learnify

**A business and product evaluation of the Learnify vision, measured against the KnowledgeOS
engine that exists today.**
Revised 2026-08-13 against commit `e81cc44` (9 build stages complete, 655 tests green, 566-node
curriculum) **and** the founder's product vision in `Learnify - IDEAS.docx`.

> **Naming.** **Learnify** is the product. **KnowledgeOS** is the engine underneath it — the
> deterministic knowledge-state layer. Externally you sell Learnify; KnowledgeOS is the reason it
> works and the reason it is hard to copy. Both names should appear in a pitch, but never
> interchangeably.

> **Status of this document.** An internal strategy critique, not a spec. It does not override
> [CLAUDE.md](CLAUDE.md), [BUILD_SPEC.md](BUILD_SPEC.md), or [CALC_ENGINE_SPEC.md](CALC_ENGINE_SPEC.md).
> Several parts of the vision *do* conflict with the current constitution; §2 names every conflict
> explicitly and proposes a resolution rather than assuming one. For the outward-facing version, see
> [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md).

---

## 0. Executive summary

**Learnify is an adaptive learning platform whose differentiator is diagnosis, not teaching.**
Everyone can teach now — a general-purpose LLM teaches well and for free. Almost nobody can tell a
learner *what they are missing and why*, with evidence, over months, across decaying knowledge and
prerequisite chains. That capability is what KnowledgeOS already implements and what the market
does not have.

| | Assessment |
|---|---|
| **Core insight** | Strong and genuinely non-obvious. The intrinsic/effective mastery split plus prerequisite propagation is real IP, not a UI over a to-do list. |
| **Engineering quality** | Unusually high. Enforced layer boundaries, a pure deterministic engine, replayable history and 655 tests are what make everything downstream possible. |
| **Vision coherence** | **Much stronger than the build's original framing.** Dropping the readiness score, going voice-native, and pulling assessment in-app each fix a real problem I flagged in the previous version of this review. |
| **The gap** | The vision requires four things the current build forbids or lacks: an integrated tutor, in-app assessment, voice, and user-defined domains. Three of the four are constitutional conflicts (§2). |
| **Biggest strategic change from v1 of this review** | **Unit economics.** Voice + in-app assessment converts a zero-marginal-cost architecture into a real COGS business. This is the right trade, but it must be designed for, not discovered. (§9.) |
| **Biggest risk** | The one the founder already named: large AI companies replicate features fast. The defence is not features — it is the longitudinal knowledge state, which is a data asset that compounds and cannot be copied by shipping a prompt. (§8.4.) |

**The single most important product decision in the vision is the one that sounds smallest: no
readiness score.** It is correct, and correct for a reason worth articulating in every pitch — a
single global percentage is both psychologically destructive and epistemically dishonest, because
its denominator is an arbitrary curriculum. Replacing it with *self-referential evidence* is a
better product **and** it removes three of the hardest problems in the business at once: cross-user
score comparability, gaming, and cohort ranking. §4 works out how to honour it without gutting the
engine, because the machinery still needs a readiness quantity internally.

---

## 1. The vision, stated precisely

From `Learnify - IDEAS.docx` and the founder's direction, six commitments:

1. **Learnify identifies hidden knowledge gaps and personalises learning — for students, not only
   interview candidates.** The one-liner is deliberately broader than the current build.
2. **Assessment is integrated in the product.** Architecturally Layer 4 stays external and
   replaceable; commercially and experientially it is inside the app. There is no clipboard.
3. **Assessment is voice-based.** You talk; it listens, probes and measures.
4. **There is no readiness score.** A single global percentage is subjective and demoralising. The
   product tells you *where you stand* and builds justified confidence from *your own* metrics only.
5. **Tech interviews are the beachhead, not the market.** Consulting, finance, and general courses
   follow. Users set their own metrics; the system generates the curriculum and tutors against it.
6. **The system is an adaptive tutoring system**, grounded in the ET-department literature the
   founder studied — not a scorecard.

### 1.1 What the vision fixes about the current build

Three of the sharpest criticisms in the previous version of this review are answered by the vision
itself, which is a good sign that the founder's product instinct is ahead of the codebase:

| Previous criticism | The vision's answer |
|---|---|
| Six context switches and four clipboard operations per concept — a workflow only its author tolerates | In-app assessment. The clipboard disappears entirely. |
| Readiness pinned near zero by a harmonic mean, motivationally catastrophic in week one | No readiness score at all. Self-referential metrics instead. |
| The user spends 95% of their learning time outside the product; retention lives in the tutor you refuse to build | The tutor comes inside. |

### 1.2 What the vision does *not* yet answer

- **What replaces the readiness number on screen.** "Your standing" is a direction, not a design. §4.
- **Who pays, and how much, once voice makes sessions cost money.** §9.
- **How a user-defined domain gets a correct prerequisite graph.** §11 — this is the hardest
  unsolved problem in the whole vision, and also the most valuable if solved.

---

## 2. Constitutional conflicts — name them before building

The vision contradicts [CLAUDE.md](CLAUDE.md) in four specific places. Each is resolvable, but
resolving them silently would corrupt the one thing that makes the product defensible. **The
governing principle to preserve is not "no tutor" — it is that the thing which teaches must never be
the thing which decides what you know.**

| # | Vision requires | Constitution says | Severity | Resolution |
|---|---|---|---|---|
| **C1** | An adaptive tutoring system | A.4 / ARCH §11: "not an AI tutor… do not build these even when convenient" | **High** | Amend A.4. Split "teaching" from "scoring" as separate layers rather than banning teaching outright: the tutor is a Layer 4 *sibling*, and it may **never** write to knowledge state. Only a validated Schema B does. The invariant survives intact; the ban does not need to. |
| **C2** | Assessment integrated in-app | A.5.2: "teaching, questioning and evaluation are external" | **Low** | Already compatible. "External" is about *authority*, not *hosting*. The app owning the prompt, the rubric and the depth targets — which `prompts.py` already does — is the actual boundary. Hosting the session changes the transport, not the contract. State this explicitly in ARCHITECTURE §3 so nobody re-litigates it. |
| **C3** | No readiness score | `CALC_ENGINE_SPEC.md` §11 computes `Readiness_r`; §14 computes a single `Health` number; both are surfaced in the UI's Readiness tab | **Medium** | Keep both as **internal** quantities — ERG (§12) is *defined* as a readiness difference, so deleting readiness would delete the ranking engine. Remove them from the interface. §4 details this. |
| **C4** | Users define their own metrics and domains | ARCH §2: Layer 1 is static, authored, user-independent; "each concept exists exactly once" | **High** | Multi-tenant curricula: a shared canonical graph plus per-user or per-org generated graphs, each validated by the existing `build_graph.py` validator before it can be used. §11. |

**Recommendation:** amend `CLAUDE.md` §3 and A.4 *deliberately, in one commit, with the reasoning
written down* — exactly the way the mid-design critique was handled. The project's habit of
recording why a decision changed is one of its genuine assets; do not break it here.

---

## 3. Value proposition

### 3.1 The claim

> *"You studied everything and still failed. Learnify finds the gap you didn't know you had, shows
> you the prerequisite that caused it, and lets you prove — in your own voice — that you've closed
> it."*

Four promises, in descending order of defensibility:

| Promise | Strength | Why |
|---|---|---|
| **Prerequisite-cause detection** — "you failed Naive Bayes because Probability decayed" | **Very strong** | Nothing on the market does this. Causally satisfying, immediately actionable, structurally impossible without a DAG. **This is the demo.** |
| **Non-destructive decay** — restudy one concept, five dependents recover with zero reassessment | **Strong** | Correct *and* delightful. Thirty seconds to show, already passing as a golden test (`CALC_ENGINE_SPEC.md` §15). **This is the second demo.** |
| **Calibrated, inflation-resistant measurement** | **Strong, and undersold** | The reason "ask ChatGPT to quiz me" fails is sycophancy. 443 lines of `prompts.py` exist to fight it. Voice strengthens this further (§5.2). |
| **Effort-optimal sequencing** — what one hour tonight is worth most | **Moderate** | Intellectually right; the user cannot verify it directly. Sell it as a *felt* experience ("it never wastes your evening"), not as a formula. |

### 3.2 What it is worth

For a final-year student, an offer is worth several years of salary differential and a career
trajectory. A tool that measurably improves conversion is trivially worth ₹500–2,000/month or a
one-time seasonal fee. **The constraint is not value — it is belief.** Which is precisely why §4
matters: a number the user does not believe is worth nothing, and a number that makes them feel
hopeless is worth less than nothing.

### 3.3 The uncomfortable question, restated for the vision

The founding story attributes 15+ rejections to a knowledge-model problem. It may also have been
communication, speed under pressure, résumé screening, or luck. **Learnify addresses one of those.**

The vision's "no readiness score" stance makes this *less* dangerous than it was: you are no longer
claiming to predict interview outcomes, only to show a learner their own knowledge honestly. That is
a claim you can actually substantiate. **But you still need evidence that closing diagnosed gaps
changes outcomes**, because that is what a student is buying and what an investor will ask. §14 R1.

---

## 4. The "no readiness score" principle — how to honour it properly

This deserves its own section because it is the most opinionated decision in the product and the
easiest to implement badly.

### 4.1 Why the founder is right

- **The denominator is arbitrary.** "62% ready" means 62% of a curriculum someone authored. The
  student hears "38% likely to fail." Those are not the same statement and only one of them is true.
- **A bottleneck harmonic mean makes it worse.** With `ε = 0.05`, a single unassessed critical node
  pins the score near zero for weeks. Mathematically correct, motivationally catastrophic.
- **It invites comparison**, and comparison against other students is the fastest way to make an
  anxious user quit.
- **It is unfalsifiable to the user.** They cannot check it, so they either over-trust it or dismiss
  it. Neither builds confidence.

### 4.2 What to keep internally (important — do not delete the machinery)

`Readiness_r` is not decoration. `ERG` — the entire recommendation objective — is **defined** as a
difference of readiness values (`CALC_ENGINE_SPEC.md` §12). Remove readiness and the ranking engine
dies with it.

**So: readiness and Health become internal quantities that drive ordering and are never rendered as
a headline number.** No spec change, no engine change — an interface change. Concretely:

- Delete the "Readiness" tab as a scoreboard.
- Keep `GET /readiness` as an internal/debug endpoint, out of the product surface.
- The bottleneck node that readiness already identifies (`argmin EM`) is *extremely* valuable and
  should be surfaced — as **a thing to do**, never as a score.

### 4.3 What the user sees instead

Self-referential, verifiable, and every one of these is computable from data the engine already
produces:

| Surface | Says | Backed by |
|---|---|---|
| **Coverage** | "You've measured 84 of the ~210 concepts that matter for the roles you picked." | `session_count > 0` over role nodes |
| **Standing per area** | "Probability: solid. Optimisation: shaky. Transformers: unmeasured." | Banded `EM`, never a percentage |
| **Gaps found and closed** | "14 hidden gaps found. 9 closed. 5 open." | `last_gaps` history |
| **What decayed** | "3 things you knew in June need 20 minutes this week." | `next_review_at`, `retention` |
| **Why this, next** | "Softmax — because it's blocking 4 things you're trying to learn." | `is_frontier`, `CPV`, bottleneck |
| **Your own trajectory** | "Six weeks ago you couldn't derive this. Here's the recording." | append-only `session_history` |
| **Uncertainty, honestly** | "We've only tested this once — don't trust it yet." | `engine_confidence`, `σ²` |

**The last row is the trust-builder and almost nothing else in the market does it.** Saying "we're
not sure yet" is what makes the confident statements credible. It is also free — `engine_confidence`
and `assessment_variance` are already computed and stored.

### 4.4 What this trades away — be honest about it

Dropping the score forfeits **cross-student benchmarking** ("you vs. people who got offers"), which
was a compounding data moat, and it forfeits **cohort ranking** as an institutional product. That is
a real cost.

**What survives, and is compatible with the principle: cohort *bottleneck* analysis.** "61% of this
batch is blocked on the same four probability concepts" compares concepts, not students. It is a
curriculum-defect report for a placement cell, it is worth real money, and it requires no student to
be ranked against another. **This is the version of the institutional business to sell.** (§9.4.)

---

## 5. Voice — the highest-leverage decision in the vision

### 5.1 Why voice is right, not a gimmick

- **It is the actual interview modality.** Nobody types answers in a technical interview. Assessment
  in the same channel as performance is a genuine validity argument, not a feature.
- **It defeats the lookup problem.** Typed assessment competes with a browser tab. Spoken assessment
  under time pressure measures retrieval, not search.
- **It surfaces the thing students most need and least get: how they sound.** Hesitation,
  hand-waving, and confident-but-wrong are all audible and all invisible in text.
- **It converts a guessed input into a measured one.** `response_time_rating` (`CALC_ENGINE_SPEC.md`
  §3) is currently an LLM's *opinion* about fluency. In voice it becomes an **actual measurement** —
  latency to first token, pause structure, filler-word density, self-correction rate. **This is a
  genuine engine-level upgrade that only voice makes possible**, and it strengthens the observation
  model rather than merely repackaging it.

### 5.2 Voice also mostly solves the gaming problem

With copy-paste, a user can fabricate a Schema B. Harmless when you are only cheating yourself,
fatal for any institutional use. **When the app runs the session, the evidence is produced inside the
system.** Combined with §4's refusal to publish comparable scores, this moves gaming from a
credibility risk to a non-issue for the use cases that matter.

### 5.3 What voice costs — the thing that changes the business

This is the single biggest economic change from the previous version of this review, and it must not
be discovered after pricing is set.

| Architecture | Rough cost per 30-min session | Latency | Quality |
|---|---|---|---|
| Realtime speech-to-speech model | **High** — order of ₹80–250 / $1–3 | Best | Best |
| STT → text LLM → TTS pipeline | **Low** — order of ₹10–40 / $0.15–0.50 | Good enough with streaming | Very good |
| Text-only (today's build) | ~0 (user's own chat) | — | Weakest |

*(Estimates, not quotes. Measure them in week one — this table decides your pricing, not the other
way round.)*

**Recommendation: build the STT → LLM → TTS pipeline, not speech-to-speech**, for three reasons that
compound:

1. **~10× cheaper**, which is the difference between a viable student price point in India and a
   subsidised one.
2. **The text layer stays inspectable.** You keep the transcript, you keep `prompts.py` in control of
   the rubric, and you keep the anti-inflation calibration you already built. A speech-to-speech
   model swallows all of that into an opaque box — and an opaque box is exactly what
   [CLAUDE.md](CLAUDE.md) §2 exists to prevent.
3. **Provider independence.** STT, LLM and TTS are three swappable commodities. Speech-to-speech is
   one vendor lock-in.

**Tiering that follows directly:** text-mode free (zero marginal cost, and it is a genuinely useful
product), voice paid. The economics do the segmentation for you.

### 5.4 Voice risks to plan for

- **Indian-accented English STT accuracy.** Non-negotiable for the beachhead market. Test on real
  users before committing to a vendor — a transcription error becomes a wrong mastery score, which is
  the one failure the whole architecture exists to prevent.
- **Code and mathematics are hard to speak.** "Sum over i of w i x i" is painful. Needs a hybrid
  surface: voice for explanation and reasoning, a scratchpad or shared editor for symbols. Design
  this early; it is not a polish item.
- **Voice raises the barrier to starting.** Some users will not talk to a computer, in a shared room,
  at 11pm. Keep text mode as a permanent first-class fallback, not a degraded one.
- **Session length.** A 45-minute voice assessment is a serious commitment. Target 8–15 minutes and
  assess more often — which also produces more, fresher evidence and better `engine_confidence`.

---

## 6. Target users

### 6.1 Segments, ranked

| # | Segment | Fit | Verdict |
|---|---|---|---|
| **1** | **Final-year engineering / MSc students in India preparing for placements and internships** (the founder's own segment) | **Excellent** — multi-track, deep-prerequisite, "studied everything" pain; high density, reachable through campus channels | **Beachhead. Do not widen yet.** |
| **2** | **PhD / research candidates moving to industry** | **Excellent** — deep in one cone, unknown gaps everywhere else; the DAG is genuinely diagnostic; high willingness to pay | **Highest-value niche.** Small, evangelical, great for testimonials. |
| 3 | Working engineers switching into AI/ML | Strong — now reachable, because the vision includes teaching | Second wave. |
| 4 | **Campus placement cells / training & placement offices** | **Strong** — judged on placement rates, currently measuring attendance and vibes | **The institutional wedge** (§9.4), in the bottleneck-report form only. |
| 5 | Consulting / finance candidates (case, quant) | Unproven — different assessment shape (structured cases, mental maths) | Expansion, ~12 months out. §11. |
| 6 | General self-directed learners with user-defined goals | The largest market and the least proven | The long-term vision. Do not build for it yet. |
| 7 | Employers, as a hiring signal | **Poor** | **Never.** It corrupts the incentive to be honest with the learner, which is the entire product. |

### 6.2 The anti-user, and why the vision handles them better

Someone who wants to *feel* productive. The system's job is to tell them they have quietly forgotten
things and that their favourite topic is not worth studying. **The old design shouted that in a
single red number. The new design says it one concrete, fixable gap at a time** — which is the
difference between a product that self-selects for a robust minority and one a normal anxious
final-year student can actually use. §4 is not a UX nicety; it is what makes the market larger than
one person.

---

## 7. Market and timing

### 7.1 The market is real and the category is short of the right thing

Interview and skills preparation spans problem banks (LeetCode, InterviewBit), cohort programmes
(Scaler, Interview Kickstart, Exponent), mock interviews, and general LLM chat. **The market is not
short of content or of teaching. It is short of diagnosis.** Every incumbent answers "what should I
practise?" with the same static list for everybody.

The sober counterweight: knowledge-graph adaptive learning has a long history of technically
impressive systems that could not sustain direct-to-consumer businesses and ended up selling into
institutions or dying. **Treat that as the base rate.** The two things that make Learnify's odds
different are that the assessment engine is now free-ish (LLMs) and that distribution can be
campus-led rather than paid-ads-led. Both are new; neither is guaranteed.

### 7.2 Why now

1. **The assessor became affordable.** An LLM can conduct a derivation-depth technical viva by voice.
   Three years ago this product could not exist at any price.
2. **The skill surface is changing faster than curricula.** "AI Engineer" means something different
   every six months. Static lists are structurally unable to keep up; a graph plus a generator is.
3. **Half-life of technical knowledge is shrinking**, which makes *decay modelling* — the least
   glamorous part of the engine — increasingly the most valuable part.

### 7.3 Where fit is weakest

- **Time-to-value.** Must be under 15 minutes. One short voice session that surfaces one real gap the
  student did not know they had is the entire activation event. Design the funnel around producing
  exactly that moment. (§14 R2.)
- **Seasonality and churn-on-success.** Placement season peaks; users leave on offer acceptance.
  Structural. Price it in (seasonal pass) rather than fighting it — or convert to upkeep, which the
  decay model makes natural and which the multi-domain vision makes durable.
- **Price sensitivity in the beachhead.** Indian students are price-sensitive and voice has real
  COGS. This tension is the central business-model constraint. §9.

---

## 8. Differentiation

### 8.1 Landscape

| Alternative | What they model | What they miss | Learnify's edge |
|---|---|---|---|
| **LeetCode / InterviewBit / HackerRank** | Problem-level pass/fail | No concept model, no prerequisites, no forgetting, no *why* | Diagnosis, not volume |
| **Scaler / Interview Kickstart / Exponent** | Curriculum and cohorts | One static path for everyone; measurement is self-report or quiz score; expensive | Personalised, evidence-based, a fraction of the price |
| **Anki / SuperMemo** | Item-level retention, very well | Items not concepts; no DAG; no importance; no role targeting | Concept-level decay *with propagation* |
| **ChatGPT / Gemini as a tutor** | Nothing persistent | No memory of what you knew, no decay model, **and it flatters you** | Persistence + calibration + anti-inflation |
| **AI mock-interview tools** | A performance, scored once | No knowledge model between sessions; no prerequisite causality | Longitudinal state, not an event |

### 8.2 What actually holds

1. **The prerequisite DAG with non-destructive propagation.** Hard to bolt onto an existing product;
   needs authored curriculum *and* a correct engine. The §15 golden test is the proof it works.
2. **Calibrated, inflation-resistant measurement**, now with a voice channel that makes the fluency
   signal real rather than inferred.
3. **The longitudinal state itself.** Six months of a student's evidence is not a feature. It is a
   switching cost and a data asset.

### 8.3 What does not hold

- **The 566-node curriculum.** Reproducible by a competent team in a quarter. Do not build the pitch
  on it. (It *is* excellent proof of execution — pitch it as evidence you can build, not as the moat.)
- **"AI-powered learning."** Meaningless in 2026 and actively damaging as positioning.
- **The graph visualisation.** Beautiful — `curriculum_graph.html` is a genuinely good artifact — but
  visualisation is table stakes.

### 8.4 The founder's stated risk, answered

> *"Large AI companies have the resources to replicate features quickly, so simply building an AI
> tutor isn't enough."*

Correct, and the strongest sentence in the application draft. The answer has three parts, and it
should be memorised for investor Q&A:

1. **We are not competing on teaching.** Teaching is the commodity we consume, not the product we
   sell. If frontier models get better at explaining, our product improves for free.
2. **The moat is the state, not the session.** A general assistant answers a question. Learnify
   maintains a six-month, evidence-backed, prerequisite-aware, decaying model of one person's
   knowledge. That is an accumulating asset, and a chat interface is structurally the wrong shape to
   hold it.
3. **Determinism is a feature they will not copy.** Reproducible scores, computation traces, an LLM
   confidence capped at 20% of any update. Big labs optimise for capability and fluency; the whole
   point here is *not trusting the model's judgement*. That is an architectural stance, not a feature
   gap — which is why it does not close when the next model ships.

---

## 9. Business model and unit economics

### 9.1 Economics changed, and this is the most important revision in this document

The current build has **no marginal cost** — the user brings their own LLM chat. Voice plus in-app
assessment ends that. Rough shape at the STT→LLM→TTS architecture (§5.3):

- **Cost:** order of ₹10–40 (~$0.15–0.50) per 30-minute voice session. **Verify in week one.**
- **A committed student:** 3–6 sessions/week → roughly ₹150–900/month of COGS.
- **At ₹499/month that is uncomfortable. At ₹999/month it works. Free text-mode is genuinely free.**

**Design implications, in order of importance:**

1. **Shorter sessions (8–15 min), more often.** Better pedagogy, better evidence freshness, and
   roughly halves COGS. Everything points the same direction.
2. **Text mode is the free tier**, and it is not crippleware — it is the existing, working product.
3. **Session budgets, not unlimited plans.** Unlimited voice against a metered backend is how
   learning startups die.
4. **Cache aggressively.** Study content per (node, depth) is identical across users and can be
   generated once. Only assessment is genuinely per-user.

### 9.2 B2C

| Model | Price (India) | Assessment |
|---|---|---|
| **Freemium: text free, voice paid** | ₹0 / ₹699–999 per month | **Recommended.** The paywall sits exactly on the expensive, differentiated capability. Free tier is a real product, not a demo. |
| **Placement-season pass** (4 months) | ₹1,999–2,999 | Matches actual demand shape; prices churn-on-success in rather than fighting it. **Strong second, possibly first for students.** |
| Per-session credits | ₹49–99 | Aligns price with cost perfectly; risks users under-assessing to save money, which corrupts the evidence. Use only as a top-up. |

International pricing at $15–25/month for the same tiers; the engine and curriculum are shared, so
this is pure margin expansion.

### 9.3 What not to do

- **Do not sell to employers as a hiring signal.** It corrupts the incentive to be honest with the
  learner, which is the entire product.
- **Do not sell curriculum content.** Commodity; drags you into a content treadmill with the wrong
  margins.
- **Do not add ads or a job board.** Same reason as the first.

### 9.4 Institutional (B2B2C) — the version compatible with the vision

Placement cells and training programmes are judged on outcomes and measure attendance. Sell them
**cohort bottleneck reports**, not student rankings:

- *"61% of this batch is blocked on the same four probability concepts."* → a curriculum-defect
  report, worth real money, and no student is ranked against another.
- *"Coverage across the batch is 40% for SDE and 8% for data roles."* → a resourcing decision.
- Longitudinal evidence of improvement for their own reporting.

Order of magnitude: ₹2–15 lakh/year per institution. Two or three contracts likely exceed year-one
B2C revenue with a fraction of the support load. **Requires multi-user (§10) and nothing else** — and
notably it does *not* require the cross-user score comparability that §4 gave up, which is a real
strategic simplification.

### 9.5 The long-horizon option: sell the engine

*Knowledge-state-as-a-service.* Any learning platform, L&D tool, or ed-tech company could POST
evidence and GET back mastery, decay, prerequisite diagnosis, and ranked recommendations, with their
own curriculum. **The four-layer boundary discipline, built for correctness, turns out to be a
packaging decision.** Highest ceiling, longest horizon. Do not chase it now; do not architect it away
either.

---

## 10. Scaling: single-user → multi-user

Verified against the code. [PROJECT_STATE.md](PROJECT_STATE.md) closes with *"scoping would be added
at the storage layer only"* — **true of the contracts, false of the system.**

**10.1 Storage — mechanical.** `knowledge_state` has `node_id` as its sole primary key
([tables.py:38](backend/knowledgeos/state/tables.py#L38)). Needs composite `(user_id, node_id)`,
`user_id` on `session_history`, indexes on every access path, and — on Supabase, where clients reach
Postgres directly — **row-level security as the actual security boundary**, not an extra.

**10.2 The singleton is the real blocker.** `app.state.service` and `app.state.curriculum`
([dependencies.py](backend/knowledgeos/api/dependencies.py)) are built once at startup and shared by
every request; `AssessmentService` holds both repositories. There is no seam for a user identity.
The sharp edge is `StateOverlay._stored()` — the bulk read that fixed the N+1 problem (known issue
#13, 635ms → 8ms). **If its scoping is missed it does not error; it silently returns another user's
knowledge state.** Highest-severity migration risk; needs a dedicated cross-tenant isolation suite,
not code review.

The curriculum staying a shared in-memory singleton is, by contrast, a gift: 10,000 users share one
566-node graph at zero incremental memory. That 2026-08-01 decision ages extremely well — until §11
introduces per-user graphs, which is exactly where it needs revisiting.

**10.3 Compute is the ceiling.** The snapshot recomputes **per request** (~60ms/566 nodes);
`/recommendations` at 228ms of CPU-bound Python is roughly 4 req/s/core, and ERG cost grows with
*candidates × nodes*, so doubling the curriculum roughly quadruples it. Fix in this order:
(1) **persist-and-invalidate** rather than recompute — the state columns already exist as a cache and
append-only history makes rebuilding safe; (2) a **nightly decay pass** instead of per-request
retention; (3) leave Python only if 1–2 prove insufficient, which below ~10k users they will not.

**None of this touches the engine. Its purity is what makes caching safe** — same inputs, same
outputs, so a cached value is indistinguishable from a fresh one. The determinism guarantee, built
for correctness, is what makes this scale.

**10.4 Sensor drift replaces sensor comparability.** §4 removed cross-user comparison, which removes
most of the comparability problem — a large, quiet win. What remains is **within-user drift over
time**: a model upgrade mid-preparation silently shifts the scale, and a student's own six-month
trajectory is the product. Mitigation: **record model + version on every Schema B** (`schema_b` is
`jsonb`; no shape migration needed). Do it now — retroactively it is gone forever. Add a small
anchor-item set to detect drift when providers update.

**10.5 Verdict.** ~4–6 weeks to a safe multi-tenant system, dominated by threading user context and
isolation testing rather than schema work. The architecture makes this possible where most codebases
would make it painful. **The layer discipline pays for itself precisely here.**

---

## 11. The multi-domain bet — the hardest and most valuable part of the vision

*"In future it will contain consulting, finance, and maybe courses. People can set their own metrics
and it will generate stuff."*

This is where Learnify becomes a platform rather than a product, and where it can most easily break.

### 11.1 The problem

Layer 1 is currently **authored** — 566 nodes, hand-judged importance and depth, built by 16
subagents across four dependency-ordered waves, gated by a validator. A user typing *"I want to
prepare for consulting case interviews"* needs a prerequisite DAG that is acyclic, deduplicated,
correctly sequenced, and correctly depth-rated. **A naively LLM-generated graph will be plausible and
subtly wrong**, and a wrong prerequisite edge produces confidently wrong diagnosis — the exact
failure the whole architecture exists to prevent.

### 11.2 You have already built the solution and may not have noticed

`build_graph.py` + `make_fixture.py` + [DEEPEN_GRAPH.md](DEEPEN_GRAPH.md) is not a one-off content
script. **It is a curriculum factory with a machine-checkable quality gate**: unique
section-prefixed ids, referential integrity, Kahn acyclicity, duplicate-concept detection, rubric
range validation. That validator is precisely what makes generated curricula safe to use.

**The productisation:**

```
user goal statement
  → LLM generates candidate nodes + prerequisite edges + depth/importance ratings
  → build_graph.py validator (hard gate: ERRORS must be 0)
  → dedup against the canonical shared graph — reuse Probability, don't re-author it
  → publish as a user/org curriculum, versioned
  → first N learners' evidence flags mis-rated nodes for review
```

Three properties worth pitching:

1. **The gate is machine-checkable**, so generated curricula are structurally trustworthy without a
   human reading 500 nodes.
2. **Shared foundations are reused, not duplicated** — the "each concept exists exactly once"
   invariant (A.5.4) becomes a *cost advantage* at scale: consulting and finance both need
   probability, and probability is authored once.
3. **Evidence corrects the content.** If 80% of learners fail a node whose prerequisites are all
   green, the *edge* is probably wrong, not the learners. This is a self-improving curriculum and it
   is unique to having an evidence model underneath.

### 11.3 The order to expand in

**Finance/quant before consulting.** Finance is knowledge-shaped: definable concepts, real
prerequisite chains, assessable by voice, and 40 nodes already exist in the graph. Consulting case
interviews are *skill*-shaped — structuring, hypothesis-driven communication, mental maths under
pressure — which the observation model (`recall`/`depth`/`transfer`) does not cleanly fit. **Expanding
into consulting requires a new observation type, not just new content.** That is a genuine research
task; schedule it as one, and note that `CALC_ENGINE_SPEC.md` §3 explicitly anticipates additional
observation types plugging in at that point.

### 11.4 What must not break

The invariant that makes any of this trustworthy: **the thing that teaches never decides what you
know.** As domains multiply and content is generated, keep the generated tutor on one side of Schema
A/B and the deterministic engine on the other. Everything else is negotiable.

---

## 12. UX — what the product needs that it does not have

| # | Feature | Why it matters | Effort |
|---|---|---|---|
| **F1** | **In-app voice session** (STT → LLM → TTS, app-owned prompts, still emitting Schema B) | The vision's core experience; removes the clipboard entirely. | **L** |
| **F2** | **Replace the readiness tab with the standing surface** (§4.3) | The single most differentiating *product* decision. Mostly re-presentation of existing data. | M |
| **F3** | **Study plan / weekly schedule** (goal date + hours per week → dated plan mixing new work and due reviews) | Converts diagnosis into behaviour. `learning_cost` (hours) and `next_review_at` already exist and are discarded at the API boundary. | M |
| **F4** | **Goal date in the UI** | `date_factor` exists in the engine (`CALC_ENGINE_SPEC.md` §10) and **nothing can set it.** The engine models urgency; the product has no concept of a deadline. | **XS** |
| **F5** | **Due-review queue** ("3 concepts need 20 minutes today") | Cheapest recurring-engagement hook available; data already computed and stored. | S |
| **F6** | **Outcome journal** — log real interviews, questions asked, result | The validity loop, and the only tuning signal for known issues #10/#11. | S |
| **F7** | **Multi-user: auth, tenancy, isolation** | Precondition for every business model. §10. | L |
| **F8** | **Session recordings + transcripts** | Voice makes this free and it is the emotional payoff: "six weeks ago you couldn't explain this." | S |
| **F9** | **Mobile** | Short voice reviews are a phone-shaped activity; the beachhead is mobile-first. | L |
| **F10** | **User-defined goals → generated curriculum** (§11) | The platform bet. | L |
| **F11** | **Curriculum freshness process** — versioning, dated review, deprecation | 566 hand-authored AI nodes rot within ~12 months; no owner or cadence exists. | M |

**Two small notes with outsized effect:** `GET /graph` returns all 566 nodes to the client (fine at
one user, a payload problem on mobile at scale), and there is no draft-saving on a rejected
submission — losing a session's result after 45 minutes of work is a catastrophic experience, and
voice makes the session even more expensive to lose.

---

## 13. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| **1** | **Big AI companies replicate the surface** (founder's own stated risk) | **High** | §8.4. Compete on accumulated state and determinism, not on teaching quality. Consume model improvements rather than competing with them. |
| **2** | **Validity** — does closing diagnosed gaps change outcomes? | **High** | F6 outcome journal from day one. §4's framing means you no longer *have* to predict outcomes, which lowers the severity considerably — but not to zero, because students buy outcomes. |
| **3** | **Voice unit economics** break the student price point | **High** | STT→LLM→TTS not speech-to-speech; 8–15 min sessions; free text tier; session budgets. §9.1. Measure before pricing. |
| **4** | **STT accuracy on Indian-accented English** turns transcription errors into wrong mastery scores | **High** | Vendor bake-off on real users before committing. Confidence-gate low-quality transcripts rather than scoring them. |
| **5** | **Generated curricula are plausible and subtly wrong** | **High**, once §11 ships | The existing validator as a hard gate; canonical-graph dedup; evidence-driven correction; human review for flagship domains. |
| **6** | **Model drift within a user's own timeline** | Medium | Record model+version per session now; anchor items. §10.4. |
| **7** | **Cross-tenant leakage during the multi-user migration** — silent, no error | **High**, once F7 starts | Dedicated isolation suite; RLS as second line; never rely on application-level scoping alone. |
| **8** | **Content rot** in fast-moving AI tracks | Medium | F11: versioning, dated review, deprecation. Before the first institutional customer, not after. |
| **9** | **Churn on success** — users leave on offer acceptance | Medium | Structural. Price it in (seasonal pass); the multi-domain vision plus decay-driven upkeep is the durable answer. |
| **10** | **Consulting doesn't fit the observation model** | Medium | Treat as a research task with a new observation type, not a content task. §11.3. Do finance first. |
| **11** | **Key-person dependency on curriculum judgement** | Medium | Document the authoring rubric beyond structural rules; recruit domain reviewers before scaling content. |

---

## 14. Recommendations

### Phase 1 — Make it usable by someone who is not you (0–3 months)

| | Action | Why |
|---|---|---|
| **R1** | **Ship the voice session (F1) in its cheapest working form** — STT → LLM → TTS, app-owned prompts, still emitting a Schema B into the existing pipeline. Instrument cost per session from the first day. | This *is* the product. Everything else is a wrapper around it, and the cost number determines the business model. |
| **R2** | **Build the 12-minute first-session experience.** One short voice assessment on a high-leverage concept that surfaces one real gap the student did not know they had. | This is the activation event and the demo. Nothing else matters if this moment does not land. |
| **R3** | **Replace the readiness tab with the standing surface (F2), plus goal date (F4) and due reviews (F5).** | Honours the vision's central product decision and adds the two cheapest engagement hooks. F4 is hours of work. |
| **R4** | **Ship the study plan (F3) and the outcome journal (F6).** | Diagnosis without a plan is a more sophisticated version of the anxiety this was built to cure. The journal is the only evidence loop you will ever have. |
| **R5** | **Get 20–30 students who are not you.** Campus, one batch, watch first sessions silently. | You will learn more from one observed session than a month of reasoning. Expect voice comfort and session length to be the surprises. |

**Phase 1 gate:** ≥20 non-founder users completing ≥5 voice sessions each, measured cost per session,
and at least directional evidence that diagnosed gaps get closed and stay closed.

### Phase 2 — Make it a business (3–6 months)

| | Action |
|---|---|
| **R6** | **Multi-user: auth, tenancy, isolation (F7)** per §10.1–10.2, with a cross-tenant isolation suite. |
| **R7** | **Persist-and-invalidate + nightly decay pass** (§10.3). Do this *with* R6 — retrofitting caching onto live multi-tenancy is far worse. |
| **R8** | **Record model + version on every Schema B** (§10.4). Cheap now, impossible retroactively. |
| **R9** | **Launch pricing:** text free, voice paid, placement-season pass alongside monthly. Let the market choose. |
| **R10** | **Mobile (F9)** — the beachhead is phone-first and short voice reviews are phone-shaped. |
| **R11** | **One institutional pilot** — cohort bottleneck report only, no student rankings (§9.4). Price it low; the reference matters more than the revenue. |

### Phase 3 — Make it a platform (6–12 months)

| | Action |
|---|---|
| **R12** | **User-defined goals → generated curriculum (F10)**, gated by the existing validator. §11.2. |
| **R13** | **Finance/quant as the second domain** — knowledge-shaped, 40 nodes already exist, validates the expansion thesis cheaply. |
| **R14** | **Consulting as a research task** — new observation type for structuring and communication, not just new content. §11.3. |
| **R15** | **Evidence-driven curriculum correction** — mis-rated nodes flagged by aggregate learner evidence. The self-improving loop, and a genuine long-term moat. |
| **R16** | **Curriculum operations (F11)** — versioning, review cadence, domain reviewers. |

### Positioning

Not an interview-prep tool, and not an AI tutor:

> **"Learnify finds the gaps you don't know you have — and proves you've closed them."**

Lead every demo with prerequisite-cause detection: *restudy Probability, watch five downstream
concepts recover without touching them.* Thirty seconds, nothing else on the market can produce it,
and it already passes as a golden regression test.

---

## 15. Summary judgement

**The vision is stronger than the build, and the build is stronger than most seed-stage teams'.**

The engine is real, correct, and hard to reproduce. The three vision decisions that changed since the
original spec — no readiness score, integrated assessment, voice — each fix a genuine flaw, and
together they turn a founder's private instrument into something a normal anxious final-year student
could actually use. That is not a cosmetic change; it is the difference between an N=1 tool and a
market.

Three things now determine whether Learnify becomes a company:

1. **Voice has to work, cheaply.** It is the product and it is the cost structure. Measure it in week
   one, not month six.
2. **The gap-discovery moment has to land in twelve minutes.** Everything about acquisition,
   activation and word-of-mouth on a campus runs through one student saying *"it found something I
   didn't know I was missing."*
3. **The state has to compound.** A session is a commodity; six months of evidence is not. Every
   design decision should be judged by whether it makes the knowledge state richer, more trusted, and
   more expensive to leave behind.

Get those right and multi-user, multi-domain, and institutional sales are implementation work on an
architecture that — unusually, and to the founder's credit — was already built to receive them.
