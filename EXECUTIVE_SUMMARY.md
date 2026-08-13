# Learnify — Executive Summary

**Adaptive learning platform that finds the hidden knowledge gaps students don't know they have,
traces each one to its root cause, and closes it through voice tutoring and re-testing.**

| | |
|---|---|
| **Product** | Learnify — the student-facing adaptive learning platform |
| **Technology** | KnowledgeOS — the deterministic knowledge-state engine underneath it |
| **Beachhead** | Final-year engineering students in India preparing for technical placements |
| **Stage** | Working end-to-end system, single-user validated. Pre-revenue, pre-external-users. |
| **Status** | 566-concept knowledge graph · 847 prerequisite links · 6 role tracks · full engine, API and UI · 655 automated tests passing |

---

## 1. The problem

**Students cannot see what is missing from their own preparation.**

They complete the standard resources — problem lists, playlists, courses — and still fail. In the
interview, a question surfaces a conceptual gap they never knew they had. They cannot fix a gap they
cannot name, so the next round of preparation is more of the same, chosen by guesswork.

Three things make this structurally hard, and no current tool addresses any of them:

1. **Gaps are invisible.** You do not know what you do not know, and content-completion is not
   knowledge. Finishing a playlist measures attendance, not understanding.
2. **Gaps have causes upstream.** Failing Naive Bayes is usually not a Naive Bayes problem — it is a
   Probability problem from four months ago. Nothing traces the failure back.
3. **Knowledge decays silently.** What you studied in June is not what you know in November, and
   nothing tells you which parts quietly went.

**Origin.** The founder was rejected by 15+ companies in one internship season despite completing
every standard preparation resource. In almost every interview, a question exposed a conceptual gap
they did not know they had. After two courses in Educational Technology on adaptive tutoring
systems, they built the diagnostic prototype that became this system, and used it on their own
preparation.

---

## 2. The product — what a student actually does

```
1.  Pick your goal        AI Engineer · SDE · Data · Quant  (multiple tracks at once)
2.  Talk for 12 minutes   A voice session probes one concept — it will not hint or flatter
3.  See what it found     "You can state Bayes. You can't derive it. That's blocking 4 things."
4.  Close the gap         The tutor teaches to exactly the depth your target role needs
5.  Prove it              Re-tested by voice. The evidence is yours, and it's recorded.
        ↑                                                                          │
        └────────── the system tracks decay and tells you what needs 20 minutes ────┘
```

**There is no readiness percentage, and this is deliberate.** A single global score is subjective —
its denominator is somebody's arbitrary syllabus — and it damages the learner it is meant to help.
Learnify shows a student their *own* standing: what they have measured, what they have proved, what
they have quietly forgotten, and what one hour tonight is worth most on. Confidence built on your own
evidence, not on a number you cannot check.

---

## 3. Why it works — the one hard idea

Learnify keeps **two** numbers per concept, and the distinction between them is the whole system:

- **What you proved you know** — evidence from an actual assessment. Never altered by time,
  forgetting, or anything else. Evidence is never destroyed.
- **What we can currently trust** = proved × retention × prerequisite health.

So when Probability decays, Naive Bayes becomes *less trustworthy* without the student having
forgotten Naive Bayes — and **restudying Probability restores every dependent concept automatically,
with no re-testing of any of them.**

That single mechanism produces the three things students cannot get anywhere else: **root-cause
diagnosis** (the real problem is upstream), **honest decay** (what you knew in June), and
**effort-optimal sequencing** (the highest-value hour, not the biggest gap).

Every score is computed by deterministic code, not by the language model. The model conducts the
conversation and returns structured observations; **its own self-reported confidence is capped at 20%
of any update**, because language models flatter learners and a flattering score is worse than no
score. Every number is reproducible and can explain how it was calculated.

---

## 4. Why now

1. **The assessor became affordable.** A language model can now conduct a rigorous spoken technical
   examination. Three years ago this product could not exist at any price.
2. **The skill surface changes faster than syllabi.** "AI Engineer" means something different every
   six months. Static lists are structurally unable to keep up; a knowledge graph plus a generator is.
3. **Voice is the interview modality.** Assessing in the same channel as performance is a validity
   argument, not a feature — and it measures hesitation and fluency, which text cannot.

---

## 5. Why a large AI company cannot simply copy this

The honest risk is that frontier labs replicate features quickly. Three reasons that does not close
this gap:

1. **We do not compete on teaching.** Teaching is the commodity we consume, not the product we sell.
   When models get better at explaining, our product improves for free.
2. **The asset is the accumulated state, not the session.** A general assistant answers a question.
   Learnify holds six months of evidence-backed, prerequisite-aware, decaying knowledge state for one
   person. A chat interface is the wrong shape to hold that, and it takes months of a student's real
   work to rebuild elsewhere.
3. **Determinism is an architectural stance, not a feature.** Reproducible scores, computation traces,
   and a deliberate refusal to let the model decide what you know. Labs optimise for capability and
   fluency; the entire premise here is *not trusting the model's judgement*. That gap does not close
   when the next model ships.

---

## 6. Market

**Beachhead — technical placements in India.** ~1.5M engineering graduates a year, of whom several
hundred thousand prepare seriously for technical roles across 2–3 overlapping tracks. At ₹2,000 per
placement season that is a **~₹300 crore annual TAM** for the beachhead alone, with **~₹100 crore
serviceable** among serious preparers.

**Adjacent, without new technology:** MSc/MCA and PhD-to-industry candidates; international students
at $15–25/month; campus placement cells at ₹2–15 lakh/year.

**Expansion, same engine:** finance and quant (concepts and prerequisite chains already partly
built), consulting, and eventually any domain where a learner can state a goal and the system
generates and validates the curriculum for it. **The engine is domain-agnostic by construction** —
the curriculum is data, and the graph builder already validates any new one for structural
correctness before it can be used.

---

## 7. Business model

| Tier | Price | Notes |
|---|---|---|
| **Free** | ₹0 | Text-based assessment. A genuinely useful product, not a demo — and zero marginal cost. |
| **Voice** | ₹699–999 / month | The differentiated capability sits exactly on the paywall. |
| **Placement-season pass** | ₹1,999–2,999 | Matches how demand actually behaves — intense for four months, then gone. |
| **Institutions** | ₹2–15 lakh / year | Cohort *bottleneck* reports — "61% of this batch is blocked on the same four concepts." Concepts are compared, never students. |

**Unit economics.** Voice assessment has real cost (~₹10–40 per session at a speech-to-text →
language-model → speech pipeline, which is ~10× cheaper than speech-to-speech and keeps the scoring
rubric inspectable). Short, frequent sessions of 8–15 minutes are better pedagogy *and* roughly halve
cost. The free text tier carries no marginal cost at all, so the model scales down cleanly for
price-sensitive students.

---

## 8. Where it stands today

**Built and working:**

- **566 concepts, 847 prerequisite links, 6 role tracks, 16 subject areas** — validated for
  structural correctness: no duplicate concepts, no dangling links, no circular prerequisites.
- **The full deterministic engine** — measurement, forgetting, prerequisite propagation, root-cause
  detection, effort-optimal sequencing. 655 automated tests; the core evidence-preservation guarantee
  is locked by a regression test.
- **API and web application** — browse the graph, see recommendations, run a session end to end.
- **Assessment prompts owned by the application**, including calibrated anti-inflation scoring — the
  work that stops a model from rating a mediocre answer highly.

**Not yet built:** voice sessions, multi-user accounts, mobile. These are the next two quarters.

**Honest position:** validated on one user — the founder, through their own preparation. External
validation is the immediate next milestone, not a claim being made now.

---

## 9. Next 12 months

| Quarter | Milestone |
|---|---|
| **Q1** | **Voice assessment in-app.** A 12-minute first session that surfaces a real gap the student did not know they had — the activation event the whole funnel runs through. 20–30 students on one campus. |
| **Q2** | **Multi-user accounts, mobile, and pricing launch.** First institutional pilot with one placement cell. |
| **Q3** | **Finance/quant as the second domain** — proves the engine is domain-agnostic on content that already partly exists. |
| **Q4** | **User-defined goals → generated curriculum.** The platform step: a student states a goal, the system generates the concept graph and validates it automatically before use. |

---

## 10. Key risks and how they are handled

| Risk | Response |
|---|---|
| **Large AI companies replicate features** | Compete on accumulated knowledge state and determinism, not on teaching quality. See §5. |
| **Voice cost breaks the student price point** | Speech-to-text → model → speech (not speech-to-speech); 8–15 minute sessions; free text tier; measured from day one before pricing is set. |
| **Speech recognition on Indian-accented English** | Vendor testing on real students before commitment; low-confidence transcripts are not scored. |
| **Does closing gaps actually change outcomes?** | Outcome journal from day one — every real interview logged against the state at the time. This is the evidence the company is built on, and it starts accumulating immediately. |
| **Students churn once they get an offer** | Structural to the category. Priced in via the seasonal pass; the multi-domain roadmap and decay-driven upkeep make the relationship durable. |

---

## 11. The ask

*(To be set by the founder — the shape below is a template, not a recommendation of amount.)*

**Seeking:** [incubation / pre-seed of ₹__] to fund [__ months] of runway.

**Use of funds:** voice infrastructure and per-session costs · one engineer · campus pilots across
[__] institutions · design.

**What that buys, in verifiable milestones:** voice sessions live · [200] active students ·
measured cost per session · first institutional pilot signed · first outcome data linking diagnosed
gaps to interview results.

---

# Appendix A — Application form answers

Drafted to the character limits in the incubator form. Counts are exact.

**Describe your idea in one clear sentence**
> Learnify is an adaptive learning platform that finds the hidden knowledge gaps students don't know
> they have, traces each gap to the prerequisite concept that caused it, and closes it through voice
> tutoring and re-testing.

**What specific pain point does your solution address?** *(≤150)*
> Students can't see the conceptual gaps that fail them in interviews — they find out what was
> missing only after they've already been rejected. **(143)**

**Provide evidence showing this is a real problem** *(≤500)*
> I was rejected by 15+ companies in one internship season despite completing every standard
> preparation resource. In almost every interview, a question exposed a conceptual gap I did not know
> I had. In a survey of 50 final-year students, 72% could not name a specific gap in their own
> preparation, and 68% judged readiness by how much content they had finished rather than what they
> could do. India produces ~1.5 million engineering graduates a year, with technical placement rates
> reported below 50%. **(499)**
>
> ⚠️ **The 50 / 72% / 68% figures are placeholders sized to fit the limit. Replace them with your own
> real survey numbers before submitting** — and cite the source and year for the graduate and
> placement figures. See Appendix B.

**Describe your target users and customers** *(≤450)*
> Final-year engineering and MSc students and recent graduates in India preparing for AI/ML,
> software, data and quant roles. They prepare for 4-9 months across 2-3 overlapping job tracks, use
> free resources, and measure progress only by how many videos or problems they have finished.
> Secondary: PhD and research candidates moving into industry, and campus placement cells
> accountable for placement outcomes. **(406)**

**If your solution did not exist, how would users solve this today?** *(≤200)*
> They grind problem lists and video playlists, ask ChatGPT to quiz them — which flatters them — and
> judge readiness by content finished rather than by what they can actually do. **(176)**

**What is the primary benefit your idea provides?** *(≤300)*
> Learnify finds the specific concept a student never knew was missing, traces it to the prerequisite
> that caused it, and closes it through voice tutoring and re-testing — replacing undirected revision
> with evidence of exactly where they stand. **(242)**

**Discuss the future impact of this problem** *(≤450)*
> Required skills for technical roles now change faster than any fixed syllabus can follow — what an
> AI Engineer must know shifts every few months — so static preparation lists lose value each year
> and the half-life of technical knowledge keeps shrinking. As AI raises the hiring bar and graduate
> numbers keep growing, the gap widens between studying more and knowing what to study. Diagnosis,
> not content, becomes the scarce resource. **(433)**

**What is your key innovation?** *(≤150)*
> A knowledge graph that separates what you proved you know from what we can still trust, so
> forgotten foundations surface before an interview does. **(146)**

**Estimate the potential market size** *(≤450)*
> India produces roughly 1.5 million engineering graduates a year. At ₹2,000 per placement season
> that is a ₹300 crore annual market for technical interview preparation alone, of which the ~500,000
> who prepare seriously for technical roles represent ₹100 crore serviceable. Beyond this:
> international students at $15-25 a month, placement cells at ₹2-15 lakh a year, and expansion into
> finance, consulting and general courses on the same engine. **(443)**

**List current alternatives or competitors** *(≤500)*
> LeetCode and InterviewBit give problem volume but no concept model — they tell you a solution
> failed, never why. Scaler and Interview Kickstart give a fixed cohort curriculum, identical for
> every student and priced in lakhs. ChatGPT teaches well but remembers nothing, models no
> forgetting, and flatters the learner. None maintains a persistent, prerequisite-aware model of what
> a student knows. Our innovation is that diagnostic layer: a knowledge graph and engine that trace a
> failure to its cause. **(500)**

**What is the biggest risk in your idea?**
> The biggest risk is competing in a space that is evolving extremely fast. Large AI companies can
> replicate features quickly, so simply building an AI tutor isn't enough. Our defence is that we
> don't compete on teaching — teaching is the commodity we consume. We compete on the accumulated
> model of a student's knowledge, built over months of evidence, which a chat interface is
> structurally the wrong shape to hold. We still have to prove that diagnosis produces measurably
> better outcomes than a general-purpose assistant, and that is what our campus pilots are designed
> to measure.

---

# Appendix B — Verify before you pitch

These are the claims a mentor or investor will test first. **Do not submit the form until the
starred ones are real numbers.**

| | Claim | Action |
|---|---|---|
| ★ | Survey of final-year students ([N], [X], [Y] in the evidence answer) | **Run it. 50 students, 5 questions, one week.** This is the single most credible thing you can add, and its absence is the most likely reason a form gets marked down. |
| ★ | Cost per voice session (₹10–40) | Build one session and measure it. Every pricing claim depends on this number. |
| ★ | Graduate and placement-rate figures | Cite the current AICTE / official source with a year. Order-of-magnitude reasoning is fine; an uncited precise number is not. |
| | Competitor pricing (Scaler, Interview Kickstart) | Check current public pricing before quoting "priced in lakhs". |
| | Market-size arithmetic | Walk through it once out loud. 1.5M × ₹2,000 = ₹300 crore; 500k × ₹2,000 = ₹100 crore. Investors check this. |
| | The 30-second demo | Show root-cause detection live: restudy one concept, watch several downstream concepts recover untouched. Nothing else on the market can produce this moment — make sure it runs on your laptop, offline, first try. |

**One framing note for the room.** Do not open by describing the technology. Open with the story: 15+
rejections, and every interview exposing something you didn't know you didn't know. Then show the
demo. The architecture is what makes the answer credible under questioning — it is not the pitch.
