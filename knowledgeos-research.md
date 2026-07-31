# KnowledgeOS — Related Research

A working bibliography of papers that ground the design decisions in `CALC_ENGINE_SPEC.md` and
`CURRICULUM_BUILD_KIT.md`. Organized by which part of the system each paper supports. Mix of
foundational/classic works (cited for the *concept*) and recent papers (cited for *current practice*).

---

## 1. Knowledge Tracing — modeling what a learner knows over time

The core problem your Layer 2/3 solves (estimating latent mastery from observed performance) is a
well-studied field called Knowledge Tracing.

- **Corbett, A.T. & Anderson, J.R. (1994/1995).** *Knowledge Tracing: Modeling the Acquisition of
  Procedural Knowledge.* User Modeling and User-Adapted Interaction, 4(4), 253–278.
  The foundational Bayesian Knowledge Tracing (BKT) paper — models mastery as a latent binary state
  updated via a Hidden Markov Model with four parameters (prior, learning rate, slip, guess). Direct
  ancestor of your intrinsic-mastery-as-latent-estimate framing.
  https://link.springer.com/article/10.1007/BF01099821

- **Piech, C., Bassen, J., Huang, J., Ganguli, S., Sahami, M., Guibas, L.J., & Sohl-Dickstein, J.
  (2015).** *Deep Knowledge Tracing.* NeurIPS 2015.
  Replaces BKT's hand-crafted HMM with an RNN, letting mastery representation be learned from data
  rather than hard-coded — relevant background even though your engine is deterministic, not learned.
  https://arxiv.org/pdf/1506.05908

- **Abdelrahman, G., Wang, Q., & Nunes, B.P. (2023).** *Knowledge Tracing: A Survey.* ACM Computing
  Surveys, 55(11).
  Broad recent survey covering BKT, deep learning variants (DKVMN, SAKT), and evaluation practices —
  good single citation for "knowledge tracing" as a field.
  https://arxiv.org/pdf/2105.15106

- **Vie, J-J. & Kashima, H. (2019).** *Deep Knowledge Tracing is an Implicit Dynamic Multidimensional
  Item Response Theory Model.*
  Explicitly connects DKT to Item Response Theory, useful if you want to cite the IRT lineage behind
  per-session ability estimation.
  https://arxiv.org/pdf/2309.12334

---

## 2. Knowledge Space Theory & prerequisite structures — the curriculum DAG

The theoretical basis for representing a domain as a prerequisite structure and identifying the
learner's "fringe" (frontier) — directly underlies `CURRICULUM_BUILD_KIT.md`'s DAG and
`CALC_ENGINE_SPEC.md` §9's frontier detection.

- **Doignon, J-P. & Falmagne, J-C. (1985).** *Spaces for the Assessment of Knowledge.* International
  Journal of Man-Machine Studies, 23, 175–196.
  The original Knowledge Space Theory paper: formalizes a domain as items with a surmise (prerequisite)
  relation, and defines the "fringe" — the set of items ready to be learned next. This is the academic
  origin of your frontier concept.

- **Doignon, J-P. & Falmagne, J-C. (2015).** *Knowledge Spaces and Learning Spaces.* (arXiv version of
  a book chapter summarizing the theory.)
  Accessible overview of KST, the Fringe Theorem, and its real-world deployment in the ALEKS adaptive
  learning platform — good citation for "this approach has been deployed at scale."
  https://arxiv.org/abs/1511.06757

---

## 3. Forgetting curves & spaced repetition — retention and decay

Grounds `CALC_ENGINE_SPEC.md` §6 (the simple stability/retention model) and the decision to steal
FSRS's stability/retention/forgetting concepts without adopting its full flashcard-specific machinery.

- **Murre, J.M.J. & Dros, J. (2015).** *Replication and Analysis of Ebbinghaus' Forgetting Curve.*
  PLOS ONE, 10(7).
  Modern replication of Ebbinghaus's 1885 forgetting-curve experiments, confirming the shape of memory
  decay over time — the empirical anchor for any exponential/power-law retention model.
  doi:10.1371/journal.pone.0120644

- **Ye, J., Su, J., & Cao, Y. (2022).** *A Stochastic Shortest Path Algorithm for Optimizing Spaced
  Repetition Scheduling.* Proceedings of the 28th ACM SIGKDD Conference on Knowledge Discovery and Data
  Mining, 4381–4390.
  One of the two core research papers behind the FSRS algorithm — treats review scheduling as an
  optimization problem over long-term memory outcomes.
  https://doi.org/10.1145/3534678.3539081

- **Su, J., Ye, J., Nie, L., Cao, Y., & Chen, Y. (2023).** *Optimizing Spaced Repetition Schedule by
  Capturing the Dynamics of Memory.* IEEE Transactions on Knowledge and Data Engineering.
  The companion FSRS paper, introducing the Difficulty-Stability-Retrievability (DSR) model your
  `CALC_ENGINE_SPEC.md` explicitly draws stability/retention/difficulty from.
  https://doi.org/10.1109/TKDE.2023.3251721

---

## 4. Prerequisite-aware learning path recommendation — closest architectural relatives

These are the papers most structurally similar to what you're building: a prerequisite knowledge graph
plus a learner-state overlay driving recommendations. Good for a "related work" section.

- **(2026).** *Personalized Learning Path Recommendation Based on Knowledge Graphs: A Survey.*
  Electronics (MDPI), 15(1), 238.
  Recent survey of the exact pattern you're implementing — mapping mastery onto graph nodes via
  knowledge tracing/cognitive diagnosis, then using graph structure to drive path recommendation.
  Explicitly frames the tension between pure data-driven approaches and strict educational-theory
  constraints, which mirrors your intrinsic/effective mastery design debate.
  https://www.mdpi.com/2079-9292/15/1/238

- **(2025).** *Learning Path Recommendation Based on Forgetting Factors and Knowledge Graph Awareness*
  (FKGRec). ScienceDirect.
  Combines a forgetting-factor model with knowledge-graph structure to decide when learners should
  revisit forgotten prerequisite concepts — very close to your retention-decay-triggers-prerequisite-
  review design.
  https://www.sciencedirect.com/science/article/abs/pii/S0306457325003346

- **(2025).** *Education-Oriented Graph Retrieval-Augmented Generation for Learning Path Recommendation*
  (DLELP).
  Argues that prerequisite relationships alone are an incomplete knowledge structure and proposes
  combining them with concept-similarity relationships — relevant if you extend beyond pure
  prerequisite edges later.
  https://arxiv.org/html/2506.22303v1

---

## 5. Deep learning / transformer foundations — grounds the `deep-learning` and `nlp-llms` sections

- **Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A.N., Kaiser, Ł., &
  Polosukhin, I. (2017).** *Attention Is All You Need.* NeurIPS 2017.
  The original Transformer paper — self-attention, multi-head attention, and positional encoding.
  Directly underlies the `dl-attention`, `dl-multihead-attention`, and `dl-transformer-architecture`
  nodes and their prerequisite chain.
  https://arxiv.org/abs/1706.03762

---

## 6. Post-training & alignment — grounds the `post-training-llms` section

Since this section goes deliberately deeper (per your instruction), these are the primary sources
behind its RLHF/DPO/safety nodes.

- **Ouyang, L., et al. (2022).** *Training Language Models to Follow Instructions with Human Feedback.*
  NeurIPS 2022 (the InstructGPT paper).
  Establishes the three-stage RLHF pipeline (SFT → reward modeling → PPO) that
  `pt-rlhf-pipeline` is modeled on.
  https://arxiv.org/abs/2203.02155 (commonly cited arXiv id; also NeurIPS proceedings)

- **Rafailov, R., Sharma, A., Mitchell, E., Ermon, S., Manning, C.D., & Finn, C. (2023).** *Direct
  Preference Optimization: Your Language Model is Secretly a Reward Model.* NeurIPS 2023.
  Derives a closed-form policy from the KL-regularized RLHF objective, collapsing reward modeling + RL
  into a single classification loss — the direct source for your `pt-dpo` and `pt-kl-objective` nodes.
  https://arxiv.org/abs/2305.18290

- **Shao, Z., et al. (2024).** *DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open
  Language Models.*
  Introduces Group Relative Policy Optimization (GRPO) — a critic-free, group-normalized variant of PPO
  — the source for your `pt-grpo` node.
  https://arxiv.org/pdf/2402.03300

- **Burns, C., et al. (2023).** *Weak-to-Strong Generalization: Eliciting Strong Capabilities With Weak
  Supervision.* OpenAI Superalignment team.
  Studies whether a strong model can generalize beyond the mistakes of a much weaker supervisor — the
  direct source for your `pt-weak-to-strong` node.
  https://openai.com/index/weak-to-strong-generalization/

- **Bricken, T., et al. (2023).** *Towards Monosemanticity: Decomposing Language Models With
  Dictionary Learning.* Transformer Circuits / Anthropic.
  Introduces sparse autoencoders as a tool for extracting interpretable features from superposed
  neural activations — the source for your `pt-sae` node.
  https://transformer-circuits.pub/2023/monosemantic-features

- **Templeton, A., et al. (2024).** *Scaling Monosemanticity: Extracting Interpretable Features from
  Claude 3 Sonnet.* Transformer Circuits / Anthropic.
  Scales sparse-autoencoder interpretability to a production-size model, showing the technique holds up
  beyond toy transformers — good follow-up citation alongside the paper above.
  https://transformer-circuits.pub/2024/scaling-monosemanticity/

---

## Notes on using these

- For a formal write-up (thesis, report, or README "Related Work" section), Sections 1–4 are your
  strongest citations — they justify the *architecture itself* (knowledge tracing, prerequisite graphs,
  forgetting curves, learning-path recommendation), independent of which domain you apply it to.
- Section 6 papers ground the *content* of one curriculum section, not the engine — cite them if
  you write about why `post-training-llms` was scoped the way it was, not when discussing the
  calculation engine.
- Several entries (the MDPI survey, DLELP, FKGRec) are from 2025–2026 and represent live, active
  research areas — worth a fresh search closer to when you write anything citing them, since this
  space moves quickly.