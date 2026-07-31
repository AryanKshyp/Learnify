# CURRICULUM_BUILD_KIT.md — Authoring Contract & Research Prompts

> **What this is.** Everything needed to produce the static Knowledge Graph (Layer 1) for KnowledgeOS. It fixes the section taxonomy, the authoring output schema, the scoring rubrics, and the deduplication rules — then gives you a copy-paste deep-research prompt whose output drops directly into the graph contracts (`BUILD_SPEC.md` C.1–C.3).
>
> **Workflow.**
> 1. Review **Part 2 (Section Taxonomy)** — this is the one thing worth your eyes before running research. Changing sections later means re-tagging every node.
> 2. Run the **Part 7 research prompt**. It returns a single JSON dataset.
> 3. Hand the JSON back to me. I validate it (DAG, referential integrity, dedup), fix issues, and convert it into the fixture curriculum (Stage 1) and the seed curriculum (Stage 6).
>
> **Decisions locked:** medium/sub-topic granularity · AI Engineer is the template role · all 6 roles covered, shared foundations first · shared concepts are single nodes with multiple role tags.

---

## PART 1 — ROLES (fixed registry)

Research does **not** invent roles. These are the six, with the user's priority rank (`BUILD_SPEC.md` C.3):

| role_id | name | priority_rank |
|---|---|---|
| `ai-research` | AI Research | 1 |
| `ai-engineer` | AI Engineer | 2 |
| `data-science` | Data Science | 3 |
| `software-engineering` | Software Engineering | 4 |
| `product-management` | Product Management | 5 |
| `finance-quant` | Finance / Quantitative | 6 |

---

## PART 2 — SECTION TAXONOMY  ← review this first

Sections are the top-level grouping every node belongs to (`BUILD_SPEC.md` C.1 `section`). They match how you browse ("view by section") and maximize sharing across roles. Fixed ids and abbreviations (the abbreviation prefixes every node_id in that section):

| section_id | abbrev | scope |
|---|---|---|
| `probability` | `prob` | combinatorics, distributions, Bayes, expectation, stochastic processes |
| `statistics` | `stat` | estimation, hypothesis testing, regression, experimentation, time series |
| `linear-algebra` | `linalg` | vectors/matrices, eigen, decompositions, projections |
| `calculus-optimization` | `opt` | derivatives/gradients, chain rule, convexity, gradient descent, Lagrangians |
| `dsa` | `dsa` | data structures, algorithms, complexity, patterns |
| `cs-fundamentals` | `cs` | operating systems, networks, databases, concurrency |
| `system-design` | `sysd` | scalability, caching, load balancing, storage, ML system design |
| `classical-ml` | `ml` | supervised/unsupervised, trees/ensembles, SVM, evaluation, feature engineering |
| `deep-learning` | `dl` | neural nets, backprop, CNNs, RNNs, attention/transformers, training dynamics |
| `nlp-llms` | `llm` | tokenization, embeddings, transformer LMs, fine-tuning, RAG, inference optimization, alignment |
| `post-training-llms` | `pt` | **AI-research only.** RLHF, DPO/RLAIF, instruction tuning, reward modeling; AI-safety topics (alignment, interpretability, scalable oversight, red-teaming); and the underlying math (KL-regularized objectives, policy-gradient/PPO, DPO derivation) |
| `ml-systems-mlops` | `mlops` | data/feature pipelines, serving, monitoring, distributed training, experimentation infra |
| `data-science-analytics` | `ds` | EDA, A/B testing, causal inference, metrics, SQL/wrangling, storytelling |
| `product-management` | `pm` | product sense, metrics, prioritization, strategy, execution, estimation |
| `finance-quant` | `fq` | financial math, derivatives/pricing, market microstructure, mental math/brainteasers, quant programming |
| `behavioral` | `beh` | STAR stories, leadership principles, conflict, communication (shared by ALL roles) |

**Section → role coverage matrix** (which sections each role draws from — this scopes the research per role):

| section | ai-research | ai-engineer | data-science | swe | product | finance-quant |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| probability | ● | ● | ● | ○ | ○ | ● |
| statistics | ● | ● | ● | | ○ | ● |
| linear-algebra | ● | ● | ○ | | | ○ |
| calculus-optimization | ● | ● | ○ | | | ● |
| dsa | ○ | ● | ○ | ● | | ● |
| cs-fundamentals | | ● | | ● | ○ | ○ |
| system-design | ○ | ● | | ● | ○ | |
| classical-ml | ● | ● | ● | | | ○ |
| deep-learning | ● | ● | ○ | | | |
| nlp-llms | ● | ● | | | | |
| post-training-llms | ● | | | | | |
| ml-systems-mlops | ○ | ● | ○ | | | |
| data-science-analytics | | ○ | ● | | ● | |
| product-management | | | ○ | | ● | |
| finance-quant | | | | | | ● |
| behavioral | ● | ● | ● | ● | ● | ● |

● = core coverage · ○ = partial/lighter coverage · blank = out of scope for that role. Note how heavily `probability`, `dsa`, and `behavioral` are shared — those are your leverage sections.

---

## PART 3 — GRANULARITY (medium / sub-topic)

Each **assessable** node is a **sub-topic** — something assessable in a focused 30–60 minute session.

| Level | Example | Use as a node? |
|---|---|---|
| Whole topic | "Transformers", "Sorting", "Hypothesis Testing" | ✗ too coarse → this is a `competency`, not a node |
| **Sub-topic** | "Self-Attention", "KV Cache", "Merge Sort", "t-test", "Bias-Variance Tradeoff" | ✓ **this is the assessable node** |
| Atomic fact | "why divide by √d_k", "why merge sort is stable" | ✗ too fine → fold into the sub-topic node |

`competency` (`BUILD_SPEC.md` C.1) is the whole-topic grouping the sub-topic sits under (e.g. node "Self-Attention" → competency "transformers" → section "deep-learning").

---

## PART 4 — AUTHORING OUTPUT SCHEMA

Research returns one JSON object with two arrays: `nodes` and `edges`. Shapes match `BUILD_SPEC.md` C.1–C.2 exactly.

**Node:**
```jsonc
{
  "node_id": "dl-self-attention",        // lowercase-hyphenated, PREFIXED with section abbrev; globally unique
  "type": "assessable",                  // "assessable" (sub-topic, can be assessed) or "concept" (grouping only)
  "name": "Self-Attention",
  "section": "deep-learning",            // from Part 2
  "competency": "transformers",          // whole-topic grouping within the section
  "description": "Scaled dot-product attention: Q/K/V, weighting, and why it enables context mixing.",
  "roles": [                             // ONE entry per role this concept matters to (see dedup rule, Part 6)
    { "role_id": "ai-research", "importance": 0.95, "required_depth": "derivation" },
    { "role_id": "ai-engineer", "importance": 0.85, "required_depth": "deep" }
  ],
  "tags": ["math-heavy"]                 // optional, freeform, for filtering only
}
```

**Edge:**
```jsonc
{
  "from_node_id": "dl-self-attention",   // the dependent
  "to_node_id": "linalg-matrix-multiplication",  // the prerequisite / parent
  "type": "prerequisite",                // "prerequisite" (to_node before from_node) or "part_of" (hierarchy)
  "weight": 1.0                          // dependency strength (Part 5); part_of always 1.0
}
```

`node_id` slug convention: `{section-abbrev}-{concept-slug}` — e.g. `prob-bayes-theorem`, `dsa-binary-search`, `llm-kv-cache`, `beh-conflict-resolution`.

---

## PART 5 — RUBRICS

**Importance (0..1, per role)** — how much this concept matters *for that role's* interviews:
| Band | Meaning |
|---|---|
| 0.90–1.00 | Core — almost always tested; failing it likely fails the interview |
| 0.75–0.89 | High — frequently tested; expected to know well |
| 0.60–0.74 | Medium — sometimes tested; good to know |
| 0.40–0.59 | Low — occasionally relevant |
| below 0.40 | Peripheral — **omit the role tag entirely** rather than adding a low one |

**Required depth (the depth ladder, `BUILD_SPEC.md` C.4)** — the *same concept* may need different depth for different roles:
| depth | Meaning |
|---|---|
| `awareness` | Can define it; knows it exists and roughly what it's for |
| `working` | Can apply it correctly in standard settings |
| `deep` | Understands the mechanism, tradeoffs, and edge cases |
| `derivation` | Can derive from first principles / prove / implement from scratch |

Example: Probability → `derivation` for finance-quant, `working` for software-engineering.

**Edge weight (0..1, prerequisite strength)** — used by the engine's prerequisite propagation:
| weight | Meaning |
|---|---|
| 1.0 | Hard prerequisite — cannot understand the dependent without it |
| 0.7 | Strong — significantly harder without it |
| 0.4 | Helpful — aids understanding but not blocking |
`part_of` edges: always weight 1.0 (not used in propagation).

---

## PART 6 — AUTHORING RULES (non-negotiable)

1. **Each concept exactly once.** A concept that serves multiple roles is **one node** with multiple entries in its `roles[]` array. Never create `prob-bayes-theorem-for-ai` and `prob-bayes-theorem-for-finance` — create `prob-bayes-theorem` with both role tags. This is the single most important rule.
2. **Reference by id.** When a role needs a shared concept, tag the existing node; do not redefine it.
3. **Prerequisite subgraph is a DAG.** `prerequisite` edges must contain **no cycles**. (`part_of` is hierarchy and also acyclic.)
4. **Cross-section prerequisites are expected.** e.g. `dl-self-attention` → requires `linalg-matrix-multiplication`; `ml-logistic-regression` → requires `opt-gradient-descent` and `prob-bayes-theorem`.
5. **Foundations before dependents.** Emit shared foundational sections first so later nodes can reference them.
6. **Medium granularity only** (Part 3). Don't emit whole-topic nodes or atomic-fact nodes.
7. **Depth and importance are per-role**, set from the rubrics — not global constants.

---

## PART 7 — DEEP RESEARCH PROMPT

Copy the block below into a deep-research session. It is self-contained (restates the rules so the research tool needs nothing else). It attempts all six roles in one pass, foundations first.

> **One honest caution about "one shot":** all six roles at sub-topic granularity is a large output and a single run may truncate. If the JSON comes back cut off or thin, use the **phased fallback** in Part 7B — it produces a more complete, cleaner graph. Either way the output format is identical, so nothing is wasted.

### 7A — Master prompt (attempt all 6 in one pass)

```
You are constructing the complete curriculum knowledge graph for an interview-preparation
system covering six target roles. Output ONE JSON object with two arrays: "nodes" and "edges".
Return ONLY the JSON — no prose, no markdown fences, no commentary.

TARGET LEVEL: internship-level interviews at top employers — FAANG-tier companies and top AI
research labs for technical/AI roles; top investment banks and quantitative hedge funds for the
finance/quant role.

ROLES (use these exact role_ids; priority rank in parentheses, 1 = highest):
  ai-research (1), ai-engineer (2), data-science (3),
  software-engineering (4), product-management (5), finance-quant (6)

SECTIONS (every node belongs to exactly one; use these exact section_ids, with the abbreviation
that must PREFIX every node_id in that section):
  probability (prob), statistics (stat), linear-algebra (linalg), calculus-optimization (opt),
  dsa (dsa), cs-fundamentals (cs), system-design (sysd), classical-ml (ml), deep-learning (dl),
  nlp-llms (llm), post-training-llms (pt), ml-systems-mlops (mlops), data-science-analytics (ds),
  product-management (pm), finance-quant (fq), behavioral (beh)

WHICH SECTIONS EACH ROLE COVERS (● core, ○ lighter; blank = skip for that role):
  probability:            research●  ai-eng●  ds●  swe○  pm○  finance●
  statistics:             research●  ai-eng●  ds●          pm○  finance●
  linear-algebra:         research●  ai-eng●  ds○               finance○
  calculus-optimization:  research●  ai-eng●  ds○               finance●
  dsa:                    research○  ai-eng●  ds○  swe●        finance●
  cs-fundamentals:                   ai-eng●       swe●  pm○  finance○
  system-design:          research○  ai-eng●       swe●  pm○
  classical-ml:           research●  ai-eng●  ds●               finance○
  deep-learning:          research●  ai-eng●  ds○
  nlp-llms:               research●  ai-eng●
  post-training-llms:     research●
  ml-systems-mlops:       research○  ai-eng●  ds○
  data-science-analytics:            ai-eng○  ds●         pm●
  product-management:                         ds○         pm●
  finance-quant:                                               finance●
  behavioral:             research●  ai-eng●  ds●  swe●  pm●  finance●

GRANULARITY (critical): each node is a SUB-TOPIC assessable in a focused 30–60 minute session —
e.g. "Self-Attention", "KV Cache", "Bayes Theorem", "Binary Search", "Bias-Variance Tradeoff".
NOT whole topics ("Transformers", "Sorting") and NOT atomic single facts ("why divide by sqrt(d_k)").
Fold atomic facts into their sub-topic node.

NODE SHAPE:
  {
    "node_id": "<sectionAbbrev>-<slug>",   // lowercase-hyphenated, globally unique
    "type": "assessable",                   // or "concept" for a pure grouping node
    "name": "<display name>",
    "section": "<section_id>",
    "competency": "<whole-topic grouping within the section, e.g. transformers>",
    "description": "<one sentence>",
    "roles": [ { "role_id": "<role_id>", "importance": <0..1>, "required_depth": "<depth>" }, ... ],
    "tags": [ ]
  }

EDGE SHAPE:
  {
    "from_node_id": "<dependent node_id>",
    "to_node_id": "<prerequisite or parent node_id>",
    "type": "prerequisite",                 // to_node must be understood before from_node; or "part_of"
    "weight": <0..1>
  }

RUBRICS:
  importance: 0.90–1.00 core (failing likely fails the interview) | 0.75–0.89 high |
              0.60–0.74 medium | 0.40–0.59 low | below 0.40 → OMIT the role tag entirely.
  required_depth: awareness (can define) | working (can apply) |
                  deep (understands mechanism/tradeoffs/edge cases) |
                  derivation (can derive/prove/implement from scratch).
  edge weight: 1.0 hard prerequisite | 0.7 strong | 0.4 helpful. part_of edges: weight 1.0.

RULES (non-negotiable):
  1. Define each concept EXACTLY ONCE. If it matters to multiple roles, add MULTIPLE entries to that
     one node's roles[] array. NEVER create duplicate nodes for the same concept. Shared concepts
     (probability, dsa, behavioral, etc.) are single nodes with several role tags.
  2. The SAME concept may carry different importance and required_depth per role
     (e.g. probability = derivation for finance-quant, working for software-engineering).
  3. prerequisite edges must form a DAG — NO cycles.
  4. Cross-section prerequisites are expected and encouraged
     (e.g. dl-self-attention requires linalg-matrix-multiplication;
      ml-logistic-regression requires opt-gradient-descent and prob-bayes-theorem).
  5. Emit the shared foundational sections FIRST (probability, statistics, linear-algebra,
     calculus-optimization, dsa, cs-fundamentals, system-design, behavioral), then the ML sections
     (classical-ml, deep-learning, nlp-llms, post-training-llms, ml-systems-mlops), then the role-specific sections
     (data-science-analytics, product-management, finance-quant). This guarantees shared nodes exist
     before other nodes reference them.

COVERAGE: cover all six roles. Prefer correct STRUCTURE and complete breadth of core sub-topics over
exhaustive depth — moderately shallow per role is acceptable as long as (a) every core sub-topic is
present, (b) shared concepts are single multi-role nodes, and (c) prerequisite edges are correct and
acyclic. Aim for roughly 15–35 nodes per major section.

For post-training-llms (ai-research ONLY), go DEEPER than other sections: treat both the mathematical
formulations and the AI-safety topics as first-class assessable nodes — e.g. the KL-regularized RLHF
reward objective, policy-gradient/PPO for language models, the DPO derivation and its equivalence to
RLHF, reward modeling, RLAIF/constitutional AI, plus alignment, mechanistic interpretability, scalable
oversight, and red-teaming. Use required_depth "deep" or "derivation" for the mathematical nodes.

Return ONLY the JSON object.
```

### 7B — Phased fallback (use if 7A truncates)

Run these as separate sessions; identical schema and rubrics, smaller each.

**Run 1 — Foundations.** Take prompt 7A but restrict SECTIONS to: `probability, statistics, linear-algebra, calculus-optimization, dsa, cs-fundamentals, system-design, behavioral`, and add every applicable role tag to each node. Save the returned `node_id`s.

**Runs 2–7 — one role at a time** (start with **ai-engineer**, the template). Use this wrapper:
```
[Paste prompt 7A's schema, rubrics, and rules sections here — unchanged.]

ADDITIONAL CONTEXT: The following foundational node_ids already exist. Do NOT redefine them —
reference them by id in edges, and where this role needs one, I will add the role tag separately.

<paste the list of foundation node_ids from Run 1>

TASK: Produce nodes and edges ONLY for the sections this role covers that are NOT already in the
foundation list, for role: <role_id>. Also list, separately under a "role_tag_additions" array,
any EXISTING foundation node_ids this role should be tagged onto, each with
{ node_id, role_id, importance, required_depth }. Return ONLY JSON with keys:
"nodes", "edges", "role_tag_additions".
```

---

## PART 8 — WHAT HAPPENS NEXT (my side)

When you return the JSON, I will:
1. **Validate** — check every `node_id` is unique and section-prefixed; every edge references existing nodes; the `prerequisite` subgraph is acyclic (report any cycle by name); no duplicate concepts; rubric values in range.
2. **Reconcile dedup** — merge any accidental duplicates into single multi-role nodes.
3. **Emit the fixture** — a trimmed ~8-node slice for Stage 1 testing (`BUILD_SPEC.md` Stage 1).
4. **Emit the seed** — the full validated curriculum data files for Stage 6, ready for the loader.
5. **Flag gaps** — any missing prerequisites, orphan nodes, or roles whose core sub-topics look thin, for a targeted follow-up research run.
