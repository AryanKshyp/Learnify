# DEEPEN_GRAPH.md — Orchestration plan for parallel section deepening

This is the prompt/plan for using the `section-author` and `graph-integrator` subagents in Claude Code
to expand the KnowledgeOS curriculum graph from its ~183-node skeleton to a fuller ~350–450 nodes,
**without** breaking the global dedup / acyclicity constraints.

## Why waves, not all-at-once
Section authors run in isolated context windows and cannot see each other. If all 16 run at once, two
can independently create the same concept, or introduce a cross-section cycle neither can see. So we run
in **dependency-ordered waves**: foundations first (committed + validated), then sections that build on
them referencing the now-fixed foundation ids. An integrator pass closes each wave.

## Preconditions
- `build_graph.py`, `CURRICULUM_BUILD_KIT.md`, and `curriculum_graph.json` are at the repo root.
- The two subagent files are in `.claude/agents/`.
- Run `/agents` once to confirm `section-author` and `graph-integrator` are both listed.
- Recommended: commit the current graph to git first, so each wave is a reviewable diff and you can roll back.

## The waves

**Wave 1 — Foundations (no cross-section prereqs to worry about).**
Sections: `probability`, `statistics`, `linear-algebra`, `calculus-optimization`, `dsa`,
`cs-fundamentals`, `behavioral`.

**Wave 2 — Mid-layer (may reference Wave 1).**
Sections: `system-design`, `classical-ml`.

**Wave 3 — ML depth (references Waves 1–2).**
Sections: `deep-learning`, `nlp-llms`, `ml-systems-mlops`.

**Wave 4 — Specialist depth (references everything above).**
Sections: `post-training-llms`, `data-science-analytics`, `product-management`, `finance-quant`.

Run each wave, integrate, commit, then start the next. Within a wave the sections are independent enough
to author in parallel.

## Orchestration prompt (paste into the main Claude Code session, one wave at a time)

> We are deepening the KnowledgeOS curriculum graph in `build_graph.py`. Do NOT edit the file yourself.
> For this wave, launch one `section-author` subagent per section listed below, in parallel. Give each
> subagent exactly one section_id and nothing else — it knows its contract from
> `CURRICULUM_BUILD_KIT.md`. Wait for all of them to finish.
>
> Sections for this wave: **[paste the wave's section list]**
>
> When they have all returned, launch the `graph-integrator` subagent to reconcile the combined result
> and drive `python3 build_graph.py` to `ERRORS: 0`. Then show me: the integrator's summary of any
> merges/fixes, the final per-section node counts, and the git diff stat. Do not proceed to the next
> wave until I confirm.

## After the final wave
1. `python3 build_graph.py` → confirm `ERRORS: 0` and review the per-section counts and role tag totals.
2. Regenerate the fixture: `python3 make_fixture.py` (if you kept it) or ask Claude to refresh it.
3. Commit the expanded `curriculum_graph.json`.
4. Spot-check a few sections by eye — the validator guarantees structural integrity, not that the
   *content* is complete or that importance calls match your judgment. Adjust any you disagree with;
   re-running the validator keeps you safe.

## Cost / time note
Each subagent is a full model session with its own context, so a wave of 7 authors + 1 integrator is
7–8 concurrent sessions. That is fast in wall-clock but real in tokens. If your budget is tight, run the
sections sequentially instead of in parallel (same subagents, one at a time) — slower, cheaper, identical
result. Sonnet is the right model here; you don't need Opus for curriculum authoring.
