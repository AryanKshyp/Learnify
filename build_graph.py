#!/usr/bin/env python3
"""
Constructs the KnowledgeOS curriculum knowledge graph, validates it against the
CURRICULUM_BUILD_KIT contracts, and emits curriculum_graph.json.

Validation performed:
  - every node_id unique and prefixed with its section abbreviation
  - every edge references existing nodes
  - prerequisite subgraph is acyclic (Kahn's algorithm)
  - no duplicate concepts (name collisions flagged)
  - importance in [0,1]; required_depth in the depth ladder; edge weight in [0,1]
  - role_ids and section_ids valid
"""

import json, os, sys
from collections import defaultdict, deque

# ---- fixed registries ------------------------------------------------------
ROLES = [
    {"role_id": "ai-research", "name": "AI Research", "priority_rank": 1},
    {"role_id": "ai-engineer", "name": "AI Engineer", "priority_rank": 2},
    {"role_id": "data-science", "name": "Data Science", "priority_rank": 3},
    {"role_id": "software-engineering", "name": "Software Engineering", "priority_rank": 4},
    {"role_id": "product-management", "name": "Product Management", "priority_rank": 5},
    {"role_id": "finance-quant", "name": "Finance / Quantitative", "priority_rank": 6},
]
ROLE_IDS = {r["role_id"] for r in ROLES}

SECTION_ABBREV = {
    "probability": "prob", "statistics": "stat", "linear-algebra": "linalg",
    "calculus-optimization": "opt", "dsa": "dsa", "cs-fundamentals": "cs",
    "system-design": "sysd", "classical-ml": "ml", "deep-learning": "dl",
    "nlp-llms": "llm", "post-training-llms": "pt", "ml-systems-mlops": "mlops",
    "data-science-analytics": "ds", "product-management": "pm",
    "finance-quant": "fq", "behavioral": "beh",
}
DEPTHS = {"awareness", "working", "deep", "derivation"}

# role shorthands
R, E, D, S, P, F = ("ai-research", "ai-engineer", "data-science",
                    "software-engineering", "product-management", "finance-quant")
AW, WK, DP, DV = "awareness", "working", "deep", "derivation"

NODES = []
EDGES = []

def n(nid, name, section, comp, desc, roles, ntype="assessable", tags=None):
    NODES.append({
        "node_id": nid, "type": ntype, "name": name, "section": section,
        "competency": comp, "description": desc,
        "roles": [{"role_id": r, "importance": imp, "required_depth": d} for (r, imp, d) in roles],
        "tags": tags or [],
    })

def e(frm, to, w=1.0, etype="prerequisite"):
    EDGES.append({"from_node_id": frm, "to_node_id": to, "type": etype, "weight": w})

# ===========================================================================
# FOUNDATIONAL SECTIONS
# ===========================================================================

# ---- probability ----------------------------------------------------------
n("prob-counting", "Counting & Combinatorics", "probability", "foundations",
  "Permutations, combinations, and the multiplication principle for counting outcomes.",
  [(R,0.75,DP),(E,0.70,WK),(D,0.75,WK),(F,0.92,DV)])
n("prob-axioms", "Probability Axioms & Sample Spaces", "probability", "foundations",
  "Sample spaces, events, and Kolmogorov's axioms of probability.",
  [(R,0.80,DP),(E,0.75,WK),(D,0.80,WK),(S,0.55,AW),(F,0.90,DV)])
n("prob-conditional", "Conditional Probability", "probability", "foundations",
  "P(A|B) and the chain rule; reasoning about probabilities under given information.",
  [(R,0.88,DP),(E,0.85,DP),(D,0.90,DP),(S,0.60,WK),(P,0.55,AW),(F,0.95,DV)])
n("prob-independence", "Independence", "probability", "foundations",
  "Independent and conditionally independent events and their implications.",
  [(R,0.82,DP),(E,0.78,WK),(D,0.85,DP),(F,0.90,DV)])
n("prob-bayes", "Bayes' Theorem", "probability", "bayesian",
  "Inverting conditional probabilities; priors, likelihoods, and posteriors.",
  [(R,0.92,DV),(E,0.88,DP),(D,0.92,DP),(S,0.60,WK),(P,0.55,AW),(F,0.93,DV)])
n("prob-random-variables", "Random Variables", "probability", "random-variables",
  "Discrete and continuous random variables, PMFs, PDFs, and CDFs.",
  [(R,0.85,DP),(E,0.80,WK),(D,0.85,DP),(F,0.92,DV)])
n("prob-distributions", "Common Distributions", "probability", "random-variables",
  "Bernoulli, Binomial, Poisson, Uniform, Normal, Exponential, and Geometric distributions.",
  [(R,0.85,DP),(E,0.82,WK),(D,0.88,DP),(F,0.92,DV)])
n("prob-expectation", "Expectation & Variance", "probability", "moments",
  "Expected value, variance, and linearity of expectation.",
  [(R,0.88,DP),(E,0.82,DP),(D,0.90,DP),(S,0.55,AW),(F,0.95,DV)])
n("prob-covariance", "Covariance & Correlation", "probability", "moments",
  "Joint variability of random variables and the correlation coefficient.",
  [(R,0.82,DP),(E,0.75,WK),(D,0.85,DP),(F,0.90,DV)])
n("prob-inequalities", "Probability Inequalities", "probability", "limit-theorems",
  "Markov, Chebyshev, and Jensen inequalities for bounding probabilities.",
  [(R,0.80,DP),(D,0.65,WK),(F,0.85,DV)])
n("prob-lln", "Law of Large Numbers", "probability", "limit-theorems",
  "Convergence of sample averages to the expected value.",
  [(R,0.78,DP),(E,0.65,WK),(D,0.80,DP),(F,0.85,DV)])
n("prob-clt", "Central Limit Theorem", "probability", "limit-theorems",
  "Why sums of independent variables approach a normal distribution.",
  [(R,0.85,DP),(E,0.75,WK),(D,0.90,DP),(F,0.90,DV)])
n("prob-conditional-expectation", "Conditional Expectation", "probability", "moments",
  "E[X|Y], the tower property, and its use in decomposition.",
  [(R,0.80,DP),(D,0.72,WK),(F,0.90,DV)])
n("prob-markov-chains", "Markov Chains", "probability", "stochastic",
  "State transitions, transition matrices, and stationary distributions.",
  [(R,0.75,DP),(E,0.62,WK),(F,0.85,DV)])
n("prob-mgf", "Moment Generating Functions", "probability", "moments",
  "MGFs for deriving moments and characterizing distributions.",
  [(R,0.68,DP),(F,0.82,DV)])

e("prob-conditional","prob-axioms",1.0)
e("prob-independence","prob-conditional",0.7)
e("prob-bayes","prob-conditional",1.0)
e("prob-random-variables","prob-axioms",1.0)
e("prob-distributions","prob-random-variables",1.0)
e("prob-expectation","prob-random-variables",1.0)
e("prob-covariance","prob-expectation",1.0)
e("prob-conditional-expectation","prob-expectation",1.0)
e("prob-conditional-expectation","prob-conditional",0.7)
e("prob-inequalities","prob-expectation",0.7)
e("prob-lln","prob-expectation",1.0)
e("prob-clt","prob-lln",0.7)
e("prob-clt","prob-distributions",0.7)
e("prob-mgf","prob-expectation",1.0)
e("prob-markov-chains","prob-conditional",1.0)
e("prob-bayes","prob-counting",0.4)

# ---- statistics -----------------------------------------------------------
n("stat-descriptive", "Descriptive Statistics", "statistics", "foundations",
  "Mean, median, variance, quantiles, and summary statistics.",
  [(R,0.70,WK),(E,0.70,WK),(D,0.85,DP),(P,0.65,WK),(F,0.80,DP)])
n("stat-estimation", "Point Estimation & Bias", "statistics", "estimation",
  "Estimators, bias, variance, consistency, and efficiency.",
  [(R,0.82,DP),(E,0.72,WK),(D,0.85,DP),(F,0.85,DP)])
n("stat-mle", "Maximum Likelihood Estimation", "statistics", "estimation",
  "Estimating parameters by maximizing the likelihood function.",
  [(R,0.90,DV),(E,0.80,DP),(D,0.88,DP),(F,0.82,DP)])
n("stat-map", "MAP & Bayesian Estimation", "statistics", "estimation",
  "Maximum a posteriori estimation and Bayesian inference of parameters.",
  [(R,0.85,DP),(E,0.72,WK),(D,0.78,WK)])
n("stat-confidence-intervals", "Confidence Intervals", "statistics", "inference",
  "Interval estimates and the correct interpretation of confidence.",
  [(R,0.75,WK),(E,0.70,WK),(D,0.88,DP),(P,0.70,WK),(F,0.80,DP)])
n("stat-hypothesis-testing", "Hypothesis Testing", "statistics", "inference",
  "Null/alternative hypotheses, p-values, type I/II errors, and power.",
  [(R,0.80,DP),(E,0.72,WK),(D,0.92,DP),(P,0.75,WK),(F,0.82,DP)])
n("stat-t-test", "t-tests & z-tests", "statistics", "inference",
  "Comparing means with t- and z-tests under different assumptions.",
  [(D,0.88,DP),(P,0.70,WK),(F,0.72,WK),(E,0.65,WK)])
n("stat-anova", "ANOVA", "statistics", "inference",
  "Analysis of variance for comparing means across multiple groups.",
  [(D,0.75,WK),(R,0.60,WK)])
n("stat-linear-regression", "Linear Regression (Statistical)", "statistics", "regression",
  "OLS estimation, assumptions, coefficient interpretation, and diagnostics.",
  [(R,0.80,DP),(E,0.75,WK),(D,0.92,DP),(P,0.60,AW),(F,0.82,DP)])
n("stat-logistic-regression-stat", "Generalized Linear Models", "statistics", "regression",
  "GLMs including logistic and Poisson regression via link functions.",
  [(R,0.72,WK),(D,0.82,DP),(F,0.68,WK)])
n("stat-bias-variance", "Bias-Variance Tradeoff", "statistics", "model-quality",
  "Decomposition of prediction error into bias, variance, and noise.",
  [(R,0.85,DP),(E,0.85,DP),(D,0.90,DP)])
n("stat-resampling", "Bootstrap & Resampling", "statistics", "inference",
  "Estimating sampling distributions via bootstrap and permutation tests.",
  [(R,0.68,WK),(D,0.82,DP),(F,0.65,WK)])
n("stat-bayesian-inference", "Bayesian Inference", "statistics", "bayesian-stats",
  "Posterior updating, conjugate priors, and credible intervals.",
  [(R,0.80,DP),(D,0.72,WK)])
n("stat-multiple-testing", "Multiple Testing Correction", "statistics", "inference",
  "Family-wise error, Bonferroni, and false discovery rate control.",
  [(D,0.72,WK),(R,0.60,WK)])
n("stat-time-series", "Time Series Basics", "statistics", "time-series",
  "Stationarity, autocorrelation, ARIMA, and forecasting fundamentals.",
  [(D,0.68,WK),(F,0.85,DP)])

e("stat-estimation","stat-descriptive",0.7)
e("stat-estimation","prob-expectation",1.0)
e("stat-mle","stat-estimation",1.0)
e("stat-mle","prob-distributions",1.0)
e("stat-map","stat-mle",0.7)
e("stat-map","prob-bayes",1.0)
e("stat-confidence-intervals","prob-clt",0.7)
e("stat-confidence-intervals","stat-estimation",1.0)
e("stat-hypothesis-testing","stat-confidence-intervals",0.7)
e("stat-hypothesis-testing","prob-distributions",1.0)
e("stat-t-test","stat-hypothesis-testing",1.0)
e("stat-anova","stat-hypothesis-testing",1.0)
e("stat-linear-regression","stat-mle",0.7)
e("stat-linear-regression","prob-covariance",0.7)
e("stat-logistic-regression-stat","stat-linear-regression",1.0)
e("stat-bias-variance","stat-estimation",0.7)
e("stat-resampling","stat-confidence-intervals",0.7)
e("stat-bayesian-inference","stat-map",0.7)
e("stat-bayesian-inference","prob-bayes",1.0)
e("stat-multiple-testing","stat-hypothesis-testing",1.0)
e("stat-time-series","stat-linear-regression",0.4)

# ---- linear-algebra -------------------------------------------------------
n("linalg-vectors", "Vectors & Vector Spaces", "linear-algebra", "foundations",
  "Vectors, linear combinations, span, and basis.",
  [(R,0.85,DP),(E,0.80,WK),(D,0.65,WK),(F,0.55,WK)])
n("linalg-matrix-multiplication", "Matrix Multiplication", "linear-algebra", "operations",
  "Matrix products, their meaning as composed linear maps, and complexity.",
  [(R,0.88,DP),(E,0.85,DP),(D,0.70,WK),(F,0.60,WK)])
n("linalg-matrix-inverse", "Matrix Inverse & Rank", "linear-algebra", "operations",
  "Invertibility, rank, null space, and solving linear systems.",
  [(R,0.82,DP),(E,0.75,WK),(D,0.62,WK),(F,0.60,WK)])
n("linalg-dot-product", "Dot Product & Norms", "linear-algebra", "geometry",
  "Inner products, norms, orthogonality, and projections.",
  [(R,0.85,DP),(E,0.82,DP),(D,0.68,WK),(F,0.58,WK)])
n("linalg-eigen", "Eigenvalues & Eigenvectors", "linear-algebra", "decompositions",
  "Eigen-decomposition and its geometric interpretation.",
  [(R,0.85,DV),(E,0.75,WK),(D,0.65,WK),(F,0.62,WK)])
n("linalg-svd", "Singular Value Decomposition", "linear-algebra", "decompositions",
  "SVD, low-rank approximation, and its role in dimensionality reduction.",
  [(R,0.82,DP),(E,0.70,WK),(D,0.68,WK)])
n("linalg-pd-matrices", "Positive Definite Matrices", "linear-algebra", "special-matrices",
  "Positive (semi)definiteness and its role in optimization and covariance.",
  [(R,0.75,DP),(E,0.62,WK),(F,0.60,WK)])
n("linalg-matrix-calculus", "Matrix Calculus", "linear-algebra", "calculus-bridge",
  "Gradients and Jacobians of vector/matrix expressions.",
  [(R,0.85,DV),(E,0.72,WK)])
n("linalg-orthogonality", "Orthogonal & Projection Matrices", "linear-algebra", "geometry",
  "Orthonormal bases, Gram-Schmidt, and projection onto subspaces.",
  [(R,0.72,DP),(E,0.60,WK),(F,0.55,WK)])

e("linalg-matrix-multiplication","linalg-vectors",1.0)
e("linalg-dot-product","linalg-vectors",1.0)
e("linalg-matrix-inverse","linalg-matrix-multiplication",1.0)
e("linalg-eigen","linalg-matrix-multiplication",1.0)
e("linalg-svd","linalg-eigen",1.0)
e("linalg-svd","linalg-orthogonality",0.7)
e("linalg-orthogonality","linalg-dot-product",1.0)
e("linalg-pd-matrices","linalg-eigen",1.0)
e("linalg-matrix-calculus","linalg-matrix-multiplication",1.0)
e("linalg-matrix-calculus","linalg-dot-product",0.7)

# ---- calculus-optimization ------------------------------------------------
n("opt-derivatives", "Derivatives & Chain Rule", "calculus-optimization", "calculus",
  "Single/multivariable derivatives, gradients, and the chain rule.",
  [(R,0.88,DV),(E,0.82,DP),(D,0.65,WK),(F,0.78,DP)])
n("opt-gradients", "Gradients & Jacobians", "calculus-optimization", "calculus",
  "Gradient vectors, Jacobians, and Hessians for multivariable functions.",
  [(R,0.88,DV),(E,0.80,DP),(D,0.62,WK),(F,0.70,WK)])
n("opt-convexity", "Convexity", "calculus-optimization", "theory",
  "Convex sets/functions and why convexity guarantees global optima.",
  [(R,0.85,DP),(E,0.72,WK),(F,0.78,DP)])
n("opt-gradient-descent", "Gradient Descent", "calculus-optimization", "algorithms",
  "First-order optimization via gradient steps; learning rate effects.",
  [(R,0.90,DV),(E,0.88,DP),(D,0.72,WK),(F,0.65,WK)])
n("opt-sgd", "Stochastic Gradient Descent", "calculus-optimization", "algorithms",
  "Mini-batch SGD, variance, and convergence behavior.",
  [(R,0.88,DP),(E,0.88,DP),(D,0.65,WK)])
n("opt-momentum-adam", "Momentum & Adam", "calculus-optimization", "algorithms",
  "Momentum, RMSProp, and Adam adaptive optimizers.",
  [(R,0.82,DP),(E,0.85,DP),(D,0.55,AW)])
n("opt-lagrange", "Lagrange Multipliers & KKT", "calculus-optimization", "constrained",
  "Constrained optimization via Lagrange multipliers and KKT conditions.",
  [(R,0.80,DV),(E,0.62,WK),(F,0.72,DP)])
n("opt-convex-optimization", "Convex Optimization Problems", "calculus-optimization", "constrained",
  "LP/QP formulations and duality at a working level.",
  [(R,0.72,DP),(F,0.70,WK)])
n("opt-second-order", "Newton's Method", "calculus-optimization", "algorithms",
  "Second-order optimization using curvature information.",
  [(R,0.68,DP),(F,0.60,WK)])

e("opt-gradients","opt-derivatives",1.0)
e("opt-gradients","linalg-matrix-calculus",0.7)
e("opt-convexity","opt-derivatives",0.7)
e("opt-gradient-descent","opt-gradients",1.0)
e("opt-gradient-descent","opt-convexity",0.7)
e("opt-sgd","opt-gradient-descent",1.0)
e("opt-momentum-adam","opt-sgd",1.0)
e("opt-lagrange","opt-gradients",1.0)
e("opt-lagrange","opt-convexity",0.7)
e("opt-convex-optimization","opt-convexity",1.0)
e("opt-convex-optimization","opt-lagrange",0.7)
e("opt-second-order","opt-gradients",1.0)
e("opt-second-order","linalg-pd-matrices",0.7)

# ---- dsa ------------------------------------------------------------------
n("dsa-big-o", "Big-O & Complexity Analysis", "dsa", "foundations",
  "Asymptotic time/space complexity and amortized analysis.",
  [(R,0.60,WK),(E,0.85,DP),(D,0.55,WK),(S,0.95,DV),(F,0.80,DP)])
n("dsa-arrays-strings", "Arrays & Strings", "dsa", "structures",
  "Contiguous storage, two-pointer, and sliding-window techniques.",
  [(E,0.85,DP),(S,0.92,DP),(F,0.72,WK),(D,0.55,WK)])
n("dsa-hashing", "Hash Tables", "dsa", "structures",
  "Hashing, collision handling, and O(1) average lookups.",
  [(E,0.88,DP),(S,0.92,DP),(F,0.72,WK),(D,0.60,WK),(R,0.55,AW)])
n("dsa-linked-lists", "Linked Lists", "dsa", "structures",
  "Singly/doubly linked lists and pointer manipulation.",
  [(E,0.72,WK),(S,0.85,DP),(F,0.62,WK)])
n("dsa-stacks-queues", "Stacks & Queues", "dsa", "structures",
  "LIFO/FIFO structures, monotonic stacks, and deques.",
  [(E,0.75,WK),(S,0.88,DP),(F,0.65,WK)])
n("dsa-trees", "Trees & BSTs", "dsa", "structures",
  "Binary trees, BSTs, traversals, and balancing intuition.",
  [(E,0.82,DP),(S,0.90,DP),(F,0.68,WK),(R,0.55,AW)])
n("dsa-heaps", "Heaps & Priority Queues", "dsa", "structures",
  "Binary heaps and priority-queue-based algorithms.",
  [(E,0.78,DP),(S,0.85,DP),(F,0.65,WK)])
n("dsa-graphs", "Graph Representations", "dsa", "graphs",
  "Adjacency lists/matrices and core graph modeling.",
  [(E,0.80,DP),(S,0.88,DP),(F,0.58,WK),(R,0.55,AW)])
n("dsa-bfs-dfs", "BFS & DFS", "dsa", "graphs",
  "Breadth-first and depth-first traversal and their applications.",
  [(E,0.85,DP),(S,0.92,DP),(F,0.60,WK),(R,0.58,AW)])
n("dsa-sorting", "Sorting Algorithms", "dsa", "algorithms",
  "Merge/quick/heap sort, stability, and complexity tradeoffs.",
  [(E,0.82,DP),(S,0.90,DP),(F,0.72,WK),(D,0.55,WK)])
n("dsa-binary-search", "Binary Search", "dsa", "algorithms",
  "Binary search and search-space reduction patterns.",
  [(E,0.85,DP),(S,0.92,DP),(F,0.75,WK)])
n("dsa-recursion-backtracking", "Recursion & Backtracking", "dsa", "algorithms",
  "Recursive decomposition and systematic search with pruning.",
  [(E,0.80,DP),(S,0.88,DP),(F,0.62,WK)])
n("dsa-dynamic-programming", "Dynamic Programming", "dsa", "algorithms",
  "Overlapping subproblems, memoization, and tabulation.",
  [(E,0.85,DP),(S,0.90,DV),(F,0.70,WK),(R,0.55,AW)])
n("dsa-greedy", "Greedy Algorithms", "dsa", "algorithms",
  "Greedy choice property and exchange arguments.",
  [(E,0.72,WK),(S,0.82,DP),(F,0.60,WK)])
n("dsa-shortest-paths", "Shortest Paths", "dsa", "graphs",
  "Dijkstra and Bellman-Ford for weighted shortest paths.",
  [(E,0.68,WK),(S,0.80,DP)])
n("dsa-union-find", "Union-Find", "dsa", "graphs",
  "Disjoint-set structure with union by rank and path compression.",
  [(E,0.62,WK),(S,0.75,DP)])

e("dsa-arrays-strings","dsa-big-o",0.7)
e("dsa-hashing","dsa-arrays-strings",0.7)
e("dsa-linked-lists","dsa-big-o",0.7)
e("dsa-stacks-queues","dsa-arrays-strings",0.7)
e("dsa-stacks-queues","dsa-linked-lists",0.4)
e("dsa-trees","dsa-linked-lists",0.7)
e("dsa-heaps","dsa-trees",0.7)
e("dsa-graphs","dsa-hashing",0.4)
e("dsa-bfs-dfs","dsa-graphs",1.0)
e("dsa-bfs-dfs","dsa-stacks-queues",0.7)
e("dsa-sorting","dsa-big-o",1.0)
e("dsa-binary-search","dsa-sorting",0.7)
e("dsa-recursion-backtracking","dsa-trees",0.4)
e("dsa-dynamic-programming","dsa-recursion-backtracking",1.0)
e("dsa-greedy","dsa-sorting",0.4)
e("dsa-shortest-paths","dsa-bfs-dfs",1.0)
e("dsa-shortest-paths","dsa-heaps",0.7)
e("dsa-union-find","dsa-graphs",0.7)

# ---- dsa (deepened) ----
n("dsa-two-pointers", "Two-Pointer Technique", "dsa", "patterns",
  "Coordinated pointers to scan arrays/strings in linear time.",
  [(E,0.85,DP),(S,0.90,DP),(F,0.70,WK),(D,0.52,WK)])
n("dsa-sliding-window", "Sliding Window", "dsa", "patterns",
  "Maintaining a moving subarray/substring to solve range problems efficiently.",
  [(E,0.85,DP),(S,0.90,DP),(F,0.68,WK)])
n("dsa-prefix-sum", "Prefix Sums & Difference Arrays", "dsa", "patterns",
  "Precomputed cumulative sums for O(1) range queries.",
  [(E,0.78,DP),(S,0.85,DP),(F,0.68,WK)])
n("dsa-monotonic-stack", "Monotonic Stack", "dsa", "patterns",
  "Stack maintaining sorted order for next-greater/next-smaller queries.",
  [(E,0.72,WK),(S,0.82,DP),(F,0.58,WK)])
n("dsa-intervals", "Interval Problems", "dsa", "patterns",
  "Merging, inserting, and scheduling overlapping intervals.",
  [(E,0.75,WK),(S,0.85,DP),(F,0.55,WK)])
n("dsa-bit-manipulation", "Bit Manipulation", "dsa", "techniques",
  "Bitwise operations, masks, and common bit tricks.",
  [(E,0.68,WK),(S,0.80,DP),(F,0.72,WK)])
n("dsa-tries", "Tries (Prefix Trees)", "dsa", "structures",
  "Character-indexed trees for prefix search and autocomplete.",
  [(E,0.72,WK),(S,0.82,DP),(R,0.50,AW)])
n("dsa-balanced-trees", "Balanced BSTs (AVL/Red-Black)", "dsa", "structures",
  "Self-balancing trees guaranteeing logarithmic operations.",
  [(E,0.60,AW),(S,0.75,WK),(F,0.50,AW)])
n("dsa-segment-tree", "Segment & Fenwick Trees", "dsa", "structures",
  "Tree structures for efficient range queries and point updates.",
  [(E,0.55,AW),(S,0.72,WK),(F,0.58,WK)])
n("dsa-topological-sort", "Topological Sort", "dsa", "graphs",
  "Ordering a DAG's nodes so dependencies precede dependents.",
  [(E,0.78,DP),(S,0.85,DP),(R,0.52,AW),(F,0.55,WK)])
n("dsa-mst", "Minimum Spanning Tree", "dsa", "graphs",
  "Kruskal's and Prim's algorithms for minimum-weight spanning trees.",
  [(E,0.62,WK),(S,0.78,DP),(F,0.55,WK)])
n("dsa-string-matching", "String Matching", "dsa", "algorithms",
  "KMP and Rabin-Karp for efficient substring search.",
  [(E,0.60,WK),(S,0.72,WK),(F,0.52,WK)])
n("dsa-dp-1d", "1D Dynamic Programming", "dsa", "dynamic-programming",
  "Linear-state DP such as house robber and climbing stairs.",
  [(E,0.85,DP),(S,0.90,DP),(F,0.70,WK),(R,0.52,AW)])
n("dsa-dp-2d", "2D / Grid Dynamic Programming", "dsa", "dynamic-programming",
  "Two-dimensional DP over grids and pairs of sequences.",
  [(E,0.82,DP),(S,0.90,DP),(F,0.68,WK)])
n("dsa-knapsack", "Knapsack Problems", "dsa", "dynamic-programming",
  "0/1 and unbounded knapsack as canonical DP formulations.",
  [(E,0.75,DP),(S,0.85,DP),(F,0.65,WK)])
n("dsa-lis-lcs", "LIS & LCS", "dsa", "dynamic-programming",
  "Longest increasing subsequence and longest common subsequence.",
  [(E,0.72,WK),(S,0.85,DP),(F,0.60,WK)])

e("dsa-two-pointers","dsa-arrays-strings",1.0)
e("dsa-sliding-window","dsa-two-pointers",0.7)
e("dsa-sliding-window","dsa-arrays-strings",1.0)
e("dsa-prefix-sum","dsa-arrays-strings",1.0)
e("dsa-monotonic-stack","dsa-stacks-queues",1.0)
e("dsa-intervals","dsa-sorting",1.0)
e("dsa-bit-manipulation","dsa-big-o",0.4)
e("dsa-tries","dsa-trees",1.0)
e("dsa-tries","dsa-hashing",0.4)
e("dsa-balanced-trees","dsa-trees",1.0)
e("dsa-segment-tree","dsa-trees",1.0)
e("dsa-segment-tree","dsa-prefix-sum",0.7)
e("dsa-topological-sort","dsa-bfs-dfs",1.0)
e("dsa-mst","dsa-graphs",1.0)
e("dsa-mst","dsa-union-find",0.7)
e("dsa-mst","dsa-heaps",0.7)
e("dsa-string-matching","dsa-arrays-strings",1.0)
e("dsa-string-matching","dsa-hashing",0.7)
e("dsa-dp-1d","dsa-dynamic-programming",1.0)
e("dsa-dp-2d","dsa-dp-1d",1.0)
e("dsa-knapsack","dsa-dp-2d",1.0)
e("dsa-lis-lcs","dsa-dp-2d",1.0)

# ---- cs-fundamentals ------------------------------------------------------
n("cs-memory-model", "Memory & Pointers", "cs-fundamentals", "systems",
  "Stack vs heap, pointers/references, and memory layout.",
  [(E,0.70,WK),(S,0.85,DP)])
n("cs-processes-threads", "Processes & Threads", "cs-fundamentals", "os",
  "Process/thread models, context switching, and scheduling.",
  [(E,0.72,WK),(S,0.85,DP),(P,0.50,AW)])
n("cs-concurrency", "Concurrency & Synchronization", "cs-fundamentals", "os",
  "Race conditions, locks, deadlock, and synchronization primitives.",
  [(E,0.72,WK),(S,0.88,DP),(F,0.60,WK)])
n("cs-networking", "Networking Basics", "cs-fundamentals", "networks",
  "TCP/IP, HTTP, DNS, and the request lifecycle.",
  [(E,0.65,WK),(S,0.82,DP),(P,0.50,AW)])
n("cs-databases", "Database Fundamentals", "cs-fundamentals", "data",
  "Relational models, indexing, transactions, and ACID.",
  [(E,0.75,WK),(S,0.85,DP),(P,0.55,AW),(F,0.60,WK)])
n("cs-sql", "SQL", "cs-fundamentals", "data",
  "Joins, aggregations, window functions, and query reasoning.",
  [(E,0.72,WK),(S,0.78,WK),(D,0.85,DP),(P,0.65,WK),(F,0.62,WK)])
n("cs-caching", "Caching Concepts", "cs-fundamentals", "systems",
  "Cache hierarchies, eviction policies, and locality.",
  [(E,0.68,WK),(S,0.80,DP)])
n("cs-os-memory-mgmt", "Virtual Memory & Paging", "cs-fundamentals", "os",
  "Virtual memory, paging, and the role of the MMU.",
  [(S,0.75,DP),(E,0.55,AW)])

e("cs-processes-threads","cs-memory-model",0.7)
e("cs-concurrency","cs-processes-threads",1.0)
e("cs-caching","cs-memory-model",0.7)
e("cs-os-memory-mgmt","cs-memory-model",1.0)
e("cs-sql","cs-databases",1.0)
e("cs-networking","cs-processes-threads",0.4)

# ---- system-design --------------------------------------------------------
n("sysd-scalability", "Scalability Basics", "system-design", "principles",
  "Vertical vs horizontal scaling and stateless design.",
  [(E,0.82,DP),(S,0.88,DP),(P,0.60,WK),(R,0.55,AW)])
n("sysd-load-balancing", "Load Balancing", "system-design", "components",
  "Distributing traffic, health checks, and routing strategies.",
  [(E,0.78,DP),(S,0.85,DP),(P,0.55,AW)])
n("sysd-caching-systems", "Distributed Caching", "system-design", "components",
  "CDNs, Redis/Memcached, and cache invalidation strategies.",
  [(E,0.78,DP),(S,0.85,DP)])
n("sysd-db-scaling", "Database Scaling", "system-design", "data",
  "Replication, sharding, and read/write separation.",
  [(E,0.80,DP),(S,0.85,DP),(P,0.55,AW)])
n("sysd-cap-theorem", "CAP Theorem & Consistency", "system-design", "principles",
  "Consistency/availability/partition tradeoffs and consistency models.",
  [(E,0.75,DP),(S,0.82,DP),(R,0.50,AW)])
n("sysd-message-queues", "Message Queues", "system-design", "components",
  "Async processing, pub/sub, and event-driven decoupling.",
  [(E,0.75,DP),(S,0.80,DP)])
n("sysd-api-design", "API Design", "system-design", "interfaces",
  "REST/gRPC, versioning, idempotency, and rate limiting.",
  [(E,0.72,WK),(S,0.80,DP),(P,0.65,WK)])
n("sysd-ml-system-design", "ML System Design", "system-design", "ml-systems",
  "Designing training/serving pipelines, feature stores, and online inference.",
  [(R,0.75,DP),(E,0.88,DP)])
n("sysd-consistent-hashing", "Consistent Hashing", "system-design", "data",
  "Distributing keys across nodes with minimal reshuffling.",
  [(E,0.68,WK),(S,0.78,DP)])

e("sysd-load-balancing","sysd-scalability",1.0)
e("sysd-caching-systems","sysd-scalability",0.7)
e("sysd-caching-systems","cs-caching",0.7)
e("sysd-db-scaling","cs-databases",1.0)
e("sysd-db-scaling","sysd-scalability",0.7)
e("sysd-cap-theorem","sysd-db-scaling",0.7)
e("sysd-message-queues","sysd-scalability",0.7)
e("sysd-api-design","cs-networking",0.7)
e("sysd-consistent-hashing","sysd-db-scaling",0.7)
e("sysd-consistent-hashing","dsa-hashing",0.7)
e("sysd-ml-system-design","sysd-scalability",0.7)
e("sysd-ml-system-design","sysd-db-scaling",0.4)

# ---- behavioral -----------------------------------------------------------
n("beh-star-method", "STAR Storytelling", "behavioral", "communication",
  "Structuring experience answers as Situation-Task-Action-Result.",
  [(R,0.75,WK),(E,0.80,WK),(D,0.80,WK),(S,0.82,WK),(P,0.90,DP),(F,0.78,WK)])
n("beh-conflict", "Handling Conflict", "behavioral", "collaboration",
  "Navigating disagreement and describing resolution constructively.",
  [(R,0.70,WK),(E,0.75,WK),(D,0.75,WK),(S,0.78,WK),(P,0.85,DP),(F,0.72,WK)])
n("beh-leadership", "Leadership & Ownership", "behavioral", "collaboration",
  "Demonstrating initiative, ownership, and influence without authority.",
  [(R,0.65,WK),(E,0.72,WK),(D,0.72,WK),(S,0.75,WK),(P,0.90,DP),(F,0.72,WK)])
n("beh-failure", "Discussing Failure", "behavioral", "communication",
  "Framing setbacks with accountability and learning.",
  [(R,0.68,WK),(E,0.72,WK),(D,0.72,WK),(S,0.75,WK),(P,0.82,DP),(F,0.70,WK)])
n("beh-why-company", "Motivation & Fit", "behavioral", "communication",
  "Articulating genuine interest in the role, team, and company.",
  [(R,0.62,AW),(E,0.68,WK),(D,0.68,WK),(S,0.70,WK),(P,0.80,DP),(F,0.72,WK)])
n("beh-communication", "Communicating Complexity", "behavioral", "communication",
  "Explaining technical work clearly to varied audiences.",
  [(R,0.72,WK),(E,0.75,WK),(D,0.80,WK),(S,0.72,WK),(P,0.88,DP),(F,0.70,WK)])

e("beh-conflict","beh-star-method",0.7)
e("beh-leadership","beh-star-method",0.7)
e("beh-failure","beh-star-method",0.7)

# ===========================================================================
# ML SECTIONS
# ===========================================================================

# ---- classical-ml ---------------------------------------------------------
n("ml-supervised-unsupervised", "Supervised vs Unsupervised", "classical-ml", "foundations",
  "The learning paradigms and when each applies.",
  [(R,0.72,WK),(E,0.78,WK),(D,0.85,DP),(F,0.55,AW)])
n("ml-train-test-split", "Train/Val/Test & Cross-Validation", "classical-ml", "methodology",
  "Data splitting, k-fold CV, and avoiding leakage.",
  [(R,0.75,WK),(E,0.85,DP),(D,0.90,DP)])
n("ml-overfitting", "Overfitting & Regularization", "classical-ml", "methodology",
  "L1/L2 regularization, early stopping, and generalization.",
  [(R,0.85,DP),(E,0.88,DP),(D,0.90,DP)])
n("ml-linear-regression", "Linear Regression (ML)", "classical-ml", "models",
  "Regression as an ML model: loss, fitting, and evaluation.",
  [(R,0.78,DP),(E,0.82,DP),(D,0.88,DP),(F,0.62,WK)])
n("ml-logistic-regression", "Logistic Regression", "classical-ml", "models",
  "Binary classification via the sigmoid and cross-entropy loss.",
  [(R,0.82,DP),(E,0.85,DP),(D,0.90,DP),(F,0.60,WK)])
n("ml-decision-trees", "Decision Trees", "classical-ml", "models",
  "Recursive splitting, impurity measures, and interpretability.",
  [(R,0.70,WK),(E,0.80,DP),(D,0.85,DP),(F,0.58,WK)])
n("ml-ensembles", "Random Forests & Boosting", "classical-ml", "models",
  "Bagging, random forests, and gradient boosting (XGBoost).",
  [(R,0.72,WK),(E,0.82,DP),(D,0.90,DP),(F,0.65,WK)])
n("ml-svm", "Support Vector Machines", "classical-ml", "models",
  "Margins, the kernel trick, and dual formulation.",
  [(R,0.72,DP),(E,0.65,WK),(D,0.75,WK)])
n("ml-knn", "k-Nearest Neighbors", "classical-ml", "models",
  "Instance-based learning and distance metrics.",
  [(R,0.60,WK),(E,0.68,WK),(D,0.75,WK)])
n("ml-naive-bayes", "Naive Bayes", "classical-ml", "models",
  "Probabilistic classification under the conditional-independence assumption.",
  [(R,0.65,WK),(E,0.70,WK),(D,0.78,DP)])
n("ml-kmeans", "K-Means Clustering", "classical-ml", "unsupervised",
  "Centroid-based clustering and the objective it minimizes.",
  [(R,0.68,WK),(E,0.72,WK),(D,0.82,DP)])
n("ml-pca", "Principal Component Analysis", "classical-ml", "unsupervised",
  "Dimensionality reduction via variance-maximizing projections.",
  [(R,0.78,DP),(E,0.72,WK),(D,0.85,DP),(F,0.62,WK)])
n("ml-evaluation-metrics", "Classification Metrics", "classical-ml", "evaluation",
  "Precision, recall, F1, ROC-AUC, and confusion matrices.",
  [(R,0.75,DP),(E,0.88,DP),(D,0.92,DP),(P,0.60,WK)])
n("ml-feature-engineering", "Feature Engineering", "classical-ml", "methodology",
  "Encoding, scaling, and constructing predictive features.",
  [(E,0.82,DP),(D,0.88,DP),(R,0.60,WK)])
n("ml-imbalanced-data", "Imbalanced Data", "classical-ml", "methodology",
  "Resampling, class weights, and threshold tuning.",
  [(E,0.72,WK),(D,0.80,DP)])

e("ml-train-test-split","ml-supervised-unsupervised",0.7)
e("ml-overfitting","ml-train-test-split",1.0)
e("ml-overfitting","stat-bias-variance",1.0)
e("ml-linear-regression","stat-linear-regression",0.7)
e("ml-linear-regression","opt-gradient-descent",1.0)
e("ml-logistic-regression","ml-linear-regression",0.7)
e("ml-logistic-regression","opt-gradient-descent",1.0)
e("ml-logistic-regression","prob-bayes",0.4)
e("ml-decision-trees","ml-supervised-unsupervised",0.7)
e("ml-ensembles","ml-decision-trees",1.0)
e("ml-svm","opt-lagrange",0.7)
e("ml-svm","linalg-dot-product",0.7)
e("ml-naive-bayes","prob-bayes",1.0)
e("ml-naive-bayes","prob-independence",1.0)
e("ml-knn","linalg-dot-product",0.7)
e("ml-kmeans","linalg-dot-product",0.7)
e("ml-pca","linalg-svd",1.0)
e("ml-pca","linalg-eigen",1.0)
e("ml-pca","prob-covariance",0.7)
e("ml-evaluation-metrics","ml-logistic-regression",0.4)
e("ml-feature-engineering","ml-train-test-split",0.4)
e("ml-imbalanced-data","ml-evaluation-metrics",0.7)

# ---- deep-learning --------------------------------------------------------
n("dl-perceptron", "Perceptron & MLP", "deep-learning", "foundations",
  "Neurons, layers, and the multilayer perceptron.",
  [(R,0.85,DP),(E,0.85,DP),(D,0.65,WK)])
n("dl-activation-functions", "Activation Functions", "deep-learning", "foundations",
  "ReLU, sigmoid, tanh, GELU, and non-linearity's role.",
  [(R,0.80,DP),(E,0.82,DP),(D,0.58,WK)])
n("dl-backprop", "Backpropagation", "deep-learning", "training",
  "Reverse-mode autodiff and gradient computation through layers.",
  [(R,0.92,DV),(E,0.85,DP),(D,0.60,AW)])
n("dl-loss-functions", "Loss Functions", "deep-learning", "training",
  "Cross-entropy, MSE, and matching losses to tasks.",
  [(R,0.82,DP),(E,0.85,DP),(D,0.65,WK)])
n("dl-regularization-dl", "DL Regularization", "deep-learning", "training",
  "Dropout, weight decay, and data augmentation.",
  [(R,0.80,DP),(E,0.85,DP),(D,0.55,AW)])
n("dl-batchnorm", "Normalization Layers", "deep-learning", "training",
  "BatchNorm, LayerNorm, and why normalization helps training.",
  [(R,0.80,DP),(E,0.80,DP)])
n("dl-cnn", "Convolutional Networks", "deep-learning", "architectures",
  "Convolutions, pooling, and spatial feature hierarchies.",
  [(R,0.80,DP),(E,0.80,DP),(D,0.55,AW)])
n("dl-rnn", "Recurrent Networks & LSTM", "deep-learning", "architectures",
  "Sequence modeling with RNNs/LSTMs and vanishing gradients.",
  [(R,0.75,DP),(E,0.72,WK)])
n("dl-attention", "Self-Attention", "deep-learning", "transformers",
  "Scaled dot-product attention: queries, keys, values, and weighting.",
  [(R,0.95,DV),(E,0.90,DP),(D,0.55,AW)])
n("dl-multihead-attention", "Multi-Head Attention", "deep-learning", "transformers",
  "Parallel attention heads and why they improve representation.",
  [(R,0.92,DV),(E,0.85,DP)])
n("dl-transformer-architecture", "Transformer Architecture", "deep-learning", "transformers",
  "Encoder/decoder blocks, residual connections, and positional encoding.",
  [(R,0.92,DP),(E,0.88,DP),(D,0.55,AW)])
n("dl-positional-encoding", "Positional Encoding", "deep-learning", "transformers",
  "Injecting order information, including sinusoidal and RoPE schemes.",
  [(R,0.82,DP),(E,0.75,WK)])
n("dl-weight-init", "Weight Initialization", "deep-learning", "training",
  "Xavier/He initialization and its effect on signal propagation.",
  [(R,0.72,DP),(E,0.70,WK)])
n("dl-vanishing-gradients", "Vanishing/Exploding Gradients", "deep-learning", "training",
  "Gradient pathologies in deep nets and mitigations.",
  [(R,0.78,DP),(E,0.72,WK)])
n("dl-lr-scheduling", "Learning Rate Scheduling", "deep-learning", "training",
  "Warmup, decay schedules, and their training effects.",
  [(R,0.72,WK),(E,0.78,DP)])

e("dl-perceptron","linalg-matrix-multiplication",1.0)
e("dl-perceptron","opt-gradient-descent",1.0)
e("dl-activation-functions","dl-perceptron",1.0)
e("dl-backprop","dl-perceptron",1.0)
e("dl-backprop","opt-gradients",1.0)
e("dl-backprop","linalg-matrix-calculus",1.0)
e("dl-loss-functions","dl-perceptron",0.7)
e("dl-loss-functions","stat-mle",0.4)
e("dl-regularization-dl","ml-overfitting",1.0)
e("dl-regularization-dl","dl-backprop",0.7)
e("dl-batchnorm","dl-backprop",0.7)
e("dl-cnn","dl-backprop",1.0)
e("dl-rnn","dl-backprop",1.0)
e("dl-vanishing-gradients","dl-backprop",1.0)
e("dl-weight-init","dl-backprop",0.7)
e("dl-lr-scheduling","opt-sgd",0.7)
e("dl-attention","dl-perceptron",1.0)
e("dl-attention","linalg-matrix-multiplication",1.0)
e("dl-attention","linalg-dot-product",1.0)
e("dl-multihead-attention","dl-attention",1.0)
e("dl-transformer-architecture","dl-multihead-attention",1.0)
e("dl-transformer-architecture","dl-batchnorm",0.7)
e("dl-transformer-architecture","dl-positional-encoding",1.0)
e("dl-positional-encoding","dl-attention",0.7)
e("dl-rnn","dl-vanishing-gradients",0.7)

# ---- deep-learning (deepened) ----
n("dl-softmax", "Softmax & Temperature", "deep-learning", "foundations",
  "The softmax function, its link to cross-entropy, and temperature scaling.",
  [(R,0.82,DV),(E,0.80,DP),(D,0.55,WK)])
n("dl-embedding-layers", "Embedding Layers", "deep-learning", "foundations",
  "Learned lookup tables mapping discrete tokens to dense vectors.",
  [(R,0.78,DP),(E,0.82,DP),(D,0.55,AW)])
n("dl-residual-connections", "Residual Connections", "deep-learning", "architectures",
  "Skip connections that enable training very deep networks.",
  [(R,0.85,DP),(E,0.82,DP)])
n("dl-seq2seq", "Sequence-to-Sequence Models", "deep-learning", "architectures",
  "Encoder-decoder models for mapping input sequences to output sequences.",
  [(R,0.72,DP),(E,0.70,WK)])
n("dl-gradient-clipping", "Gradient Clipping", "deep-learning", "training",
  "Bounding gradient norms to stabilize training.",
  [(R,0.68,WK),(E,0.78,DP)])
n("dl-mixed-precision", "Mixed Precision Training", "deep-learning", "training",
  "FP16/BF16 training for speed and memory, with loss scaling.",
  [(R,0.65,WK),(E,0.82,DP)])
n("dl-hyperparameter-tuning", "Hyperparameter Tuning", "deep-learning", "training",
  "Searching learning rate, batch size, and architectural choices.",
  [(R,0.68,WK),(E,0.80,DP),(D,0.60,WK)])
n("dl-transfer-learning", "Transfer Learning", "deep-learning", "methodology",
  "Reusing pretrained representations for new tasks.",
  [(R,0.75,DP),(E,0.85,DP),(D,0.58,WK)])
n("dl-autoencoders", "Autoencoders", "deep-learning", "generative",
  "Encoder-decoder networks that learn compressed representations.",
  [(R,0.75,DP),(E,0.68,WK),(D,0.52,AW)])
n("dl-vae", "Variational Autoencoders", "deep-learning", "generative",
  "Latent-variable generative models trained via the ELBO.",
  [(R,0.80,DV),(E,0.62,WK)])
n("dl-gan", "Generative Adversarial Networks", "deep-learning", "generative",
  "Generator-discriminator adversarial training for generation.",
  [(R,0.78,DP),(E,0.65,WK)])
n("dl-diffusion", "Diffusion Models", "deep-learning", "generative",
  "Iterative denoising generative models and their training objective.",
  [(R,0.82,DP),(E,0.68,WK)])
n("dl-contrastive", "Contrastive & Self-Supervised Learning", "deep-learning", "representation",
  "Learning representations by contrasting positive and negative pairs.",
  [(R,0.80,DP),(E,0.68,WK)])
n("dl-gnn", "Graph Neural Networks", "deep-learning", "architectures",
  "Message-passing networks over graph-structured data.",
  [(R,0.65,WK),(E,0.58,WK)])
n("dl-knowledge-distillation", "Knowledge Distillation", "deep-learning", "compression",
  "Training a small student model to mimic a larger teacher.",
  [(R,0.72,DP),(E,0.78,DP)])
n("dl-moe", "Mixture of Experts", "deep-learning", "architectures",
  "Sparsely-activated expert layers with learned routing.",
  [(R,0.82,DP),(E,0.72,WK)])

e("dl-softmax","dl-activation-functions",1.0)
e("dl-softmax","dl-loss-functions",0.7)
e("dl-embedding-layers","dl-perceptron",1.0)
e("dl-residual-connections","dl-backprop",1.0)
e("dl-residual-connections","dl-vanishing-gradients",0.7)
e("dl-transformer-architecture","dl-residual-connections",0.7)
e("dl-seq2seq","dl-rnn",1.0)
e("dl-gradient-clipping","dl-vanishing-gradients",1.0)
e("dl-mixed-precision","dl-backprop",0.7)
e("dl-hyperparameter-tuning","dl-lr-scheduling",0.7)
e("dl-hyperparameter-tuning","ml-overfitting",0.7)
e("dl-transfer-learning","dl-backprop",0.7)
e("dl-transfer-learning","dl-cnn",0.4)
e("dl-autoencoders","dl-perceptron",1.0)
e("dl-autoencoders","dl-backprop",0.7)
e("dl-vae","dl-autoencoders",1.0)
e("dl-vae","prob-distributions",0.7)
e("dl-vae","prob-bayes",0.4)
e("dl-gan","dl-perceptron",1.0)
e("dl-gan","opt-gradient-descent",0.7)
e("dl-diffusion","dl-vae",0.7)
e("dl-diffusion","prob-distributions",0.7)
e("dl-contrastive","dl-embedding-layers",1.0)
e("dl-contrastive","dl-loss-functions",0.7)
e("dl-gnn","dl-perceptron",1.0)
e("dl-gnn","dsa-graphs",0.7)
e("dl-knowledge-distillation","dl-softmax",0.7)
e("dl-knowledge-distillation","dl-loss-functions",0.7)
e("dl-moe","dl-perceptron",1.0)

# ---- nlp-llms -------------------------------------------------------------
n("llm-tokenization", "Tokenization", "nlp-llms", "foundations",
  "Subword tokenization schemes like BPE and WordPiece.",
  [(R,0.82,DP),(E,0.85,DP)])
n("llm-embeddings", "Word & Token Embeddings", "nlp-llms", "foundations",
  "Dense vector representations and embedding spaces.",
  [(R,0.82,DP),(E,0.82,DP)])
n("llm-language-modeling", "Language Modeling Objective", "nlp-llms", "pretraining",
  "Next-token prediction and autoregressive training.",
  [(R,0.90,DV),(E,0.85,DP)])
n("llm-pretraining", "Pretraining at Scale", "nlp-llms", "pretraining",
  "Corpus construction, scaling laws, and compute considerations.",
  [(R,0.85,DP),(E,0.75,WK)])
n("llm-finetuning", "Fine-tuning", "nlp-llms", "adaptation",
  "Adapting pretrained models to downstream tasks.",
  [(R,0.85,DP),(E,0.88,DP)])
n("llm-peft-lora", "LoRA & Parameter-Efficient Tuning", "nlp-llms", "adaptation",
  "Low-rank adapters and efficient fine-tuning methods.",
  [(R,0.80,DP),(E,0.85,DP)])
n("llm-prompting", "Prompting & In-Context Learning", "nlp-llms", "inference",
  "Few-shot prompting and chain-of-thought reasoning.",
  [(R,0.78,DP),(E,0.85,DP)])
n("llm-kv-cache", "KV Cache", "nlp-llms", "inference-optimization",
  "Caching keys/values to accelerate autoregressive decoding.",
  [(R,0.82,DP),(E,0.88,DP)])
n("llm-attention-variants", "Efficient Attention (MQA/GQA/Flash)", "nlp-llms", "inference-optimization",
  "Multi-query, grouped-query, and FlashAttention optimizations.",
  [(R,0.82,DP),(E,0.82,DP)])
n("llm-quantization", "Quantization", "nlp-llms", "inference-optimization",
  "Reducing precision for memory/latency gains with minimal quality loss.",
  [(R,0.75,WK),(E,0.85,DP)])
n("llm-rag", "Retrieval-Augmented Generation", "nlp-llms", "systems",
  "Grounding generation in retrieved documents via vector search.",
  [(R,0.78,DP),(E,0.90,DP)])
n("llm-decoding-strategies", "Decoding Strategies", "nlp-llms", "inference",
  "Greedy, beam, top-k, top-p, and temperature sampling.",
  [(R,0.78,DP),(E,0.85,DP)])
n("llm-scaling-laws", "Scaling Laws", "nlp-llms", "pretraining",
  "Power-law relationships between compute, data, and loss.",
  [(R,0.82,DP),(E,0.68,WK)])
n("llm-evaluation", "LLM Evaluation", "nlp-llms", "evaluation",
  "Benchmarks, perplexity, and the challenges of evaluating generation.",
  [(R,0.78,DP),(E,0.80,DP)])

e("llm-embeddings","llm-tokenization",1.0)
e("llm-embeddings","linalg-vectors",0.7)
e("llm-language-modeling","dl-transformer-architecture",1.0)
e("llm-language-modeling","llm-embeddings",1.0)
e("llm-pretraining","llm-language-modeling",1.0)
e("llm-pretraining","opt-sgd",0.7)
e("llm-scaling-laws","llm-pretraining",1.0)
e("llm-finetuning","llm-pretraining",1.0)
e("llm-peft-lora","llm-finetuning",1.0)
e("llm-peft-lora","linalg-svd",0.7)
e("llm-prompting","llm-language-modeling",0.7)
e("llm-decoding-strategies","llm-language-modeling",1.0)
e("llm-kv-cache","dl-attention",1.0)
e("llm-kv-cache","llm-decoding-strategies",0.7)
e("llm-attention-variants","dl-multihead-attention",1.0)
e("llm-attention-variants","llm-kv-cache",0.7)
e("llm-quantization","dl-perceptron",0.4)
e("llm-rag","llm-embeddings",1.0)
e("llm-rag","llm-prompting",0.7)
e("llm-evaluation","llm-language-modeling",0.7)

# ---- nlp-llms (deepened) ----
n("llm-long-context", "Long Context Handling", "nlp-llms", "inference-optimization",
  "Extending context windows and the memory/quality tradeoffs involved.",
  [(R,0.80,DP),(E,0.80,DP)])
n("llm-speculative-decoding", "Speculative Decoding", "nlp-llms", "inference-optimization",
  "Draft-and-verify decoding to accelerate autoregressive generation.",
  [(R,0.72,WK),(E,0.82,DP)])
n("llm-continuous-batching", "Continuous Batching", "nlp-llms", "serving",
  "Dynamically batching requests to maximize LLM serving throughput.",
  [(R,0.58,AW),(E,0.85,DP)])
n("llm-distributed-inference", "Distributed Inference", "nlp-llms", "serving",
  "Tensor and pipeline parallelism for serving large models.",
  [(R,0.68,WK),(E,0.82,DP)])
n("llm-context-caching", "Prefix / Context Caching", "nlp-llms", "inference-optimization",
  "Reusing cached prefix computation across requests.",
  [(R,0.60,AW),(E,0.80,DP)])
n("llm-agents", "LLM Agents", "nlp-llms", "applications",
  "Multi-step agents that plan, act, and use tools in a loop.",
  [(R,0.75,DP),(E,0.85,DP)])
n("llm-function-calling", "Function / Tool Calling", "nlp-llms", "applications",
  "Structured tool invocation from model outputs.",
  [(R,0.68,WK),(E,0.85,DP)])
n("llm-chain-of-thought", "Chain-of-Thought Reasoning", "nlp-llms", "reasoning",
  "Eliciting intermediate reasoning steps to improve accuracy.",
  [(R,0.82,DP),(E,0.78,DP)])
n("llm-structured-output", "Structured Output & Constrained Decoding", "nlp-llms", "inference",
  "Grammar/schema-constrained generation for reliable structured output.",
  [(R,0.62,WK),(E,0.82,DP)])
n("llm-vector-search", "Vector Search & ANN", "nlp-llms", "retrieval",
  "Approximate nearest-neighbor search over embedding spaces.",
  [(R,0.68,WK),(E,0.85,DP)])
n("llm-reranking", "Reranking", "nlp-llms", "retrieval",
  "Cross-encoder reranking to improve retrieval precision.",
  [(R,0.62,WK),(E,0.78,DP)])
n("llm-hallucination", "Hallucination & Faithfulness", "nlp-llms", "reliability",
  "Why models fabricate and how grounding/verification mitigate it.",
  [(R,0.78,DP),(E,0.82,DP)])
n("llm-guardrails", "Inference-Time Guardrails", "nlp-llms", "reliability",
  "Input/output filtering and safety classifiers around a model.",
  [(R,0.62,WK),(E,0.78,DP)])
n("llm-multimodal", "Multimodal Models", "nlp-llms", "modalities",
  "Vision-language models and cross-modal representation fusion.",
  [(R,0.75,DP),(E,0.68,WK)])
n("llm-perplexity", "Perplexity & LM Metrics", "nlp-llms", "evaluation",
  "Perplexity, bits-per-token, and their interpretation.",
  [(R,0.78,DP),(E,0.65,WK)])

e("llm-long-context","dl-attention",0.7)
e("llm-long-context","llm-attention-variants",0.7)
e("llm-long-context","dl-positional-encoding",0.7)
e("llm-speculative-decoding","llm-decoding-strategies",1.0)
e("llm-speculative-decoding","llm-kv-cache",0.7)
e("llm-continuous-batching","llm-kv-cache",0.7)
e("llm-continuous-batching","mlops-model-serving",0.7)
e("llm-distributed-inference","mlops-distributed-training",0.7)
e("llm-context-caching","llm-kv-cache",1.0)
e("llm-agents","llm-prompting",1.0)
e("llm-agents","llm-function-calling",0.7)
e("llm-function-calling","llm-prompting",1.0)
e("llm-function-calling","llm-structured-output",0.7)
e("llm-chain-of-thought","llm-prompting",1.0)
e("llm-structured-output","llm-decoding-strategies",1.0)
e("llm-vector-search","llm-embeddings",1.0)
e("llm-vector-search","dsa-hashing",0.4)
e("llm-reranking","llm-vector-search",1.0)
e("llm-reranking","llm-rag",0.7)
e("llm-rag","llm-vector-search",0.7)
e("llm-hallucination","llm-language-modeling",0.7)
e("llm-hallucination","llm-rag",0.4)
e("llm-guardrails","llm-prompting",0.7)
e("llm-multimodal","dl-transformer-architecture",1.0)
e("llm-multimodal","llm-embeddings",0.7)
e("llm-perplexity","llm-language-modeling",1.0)

# ---- post-training-llms (ai-research only, deeper) -------------------------
n("pt-alignment-problem", "The Alignment Problem", "post-training-llms", "safety-foundations",
  "Why capable models may pursue unintended objectives and what alignment means.",
  [(R,0.90,DP)])
n("pt-instruction-tuning", "Instruction Tuning (SFT)", "post-training-llms", "sft",
  "Supervised fine-tuning on instruction-response pairs.",
  [(R,0.90,DP)])
n("pt-reward-modeling", "Reward Modeling", "post-training-llms", "rlhf",
  "Learning a reward model from human preference comparisons.",
  [(R,0.92,DV)])
n("pt-bradley-terry", "Bradley-Terry Preference Model", "post-training-llms", "rlhf",
  "The pairwise-preference likelihood underlying reward models.",
  [(R,0.88,DV)])
n("pt-policy-gradient", "Policy Gradients", "post-training-llms", "rl-math",
  "The policy-gradient theorem and REINFORCE for sequence generation.",
  [(R,0.92,DV)])
n("pt-ppo", "PPO for Language Models", "post-training-llms", "rlhf",
  "Proximal Policy Optimization with clipped objectives applied to LLMs.",
  [(R,0.92,DV)])
n("pt-kl-objective", "KL-Regularized RLHF Objective", "post-training-llms", "rl-math",
  "The reward-minus-KL objective that keeps the policy near the reference model.",
  [(R,0.93,DV)])
n("pt-rlhf-pipeline", "RLHF End-to-End", "post-training-llms", "rlhf",
  "The SFT to reward-model to RL pipeline for preference alignment.",
  [(R,0.92,DP)])
n("pt-dpo", "Direct Preference Optimization", "post-training-llms", "preference-optimization",
  "DPO's closed-form preference objective and its equivalence to RLHF.",
  [(R,0.92,DV)])
n("pt-rlaif-cai", "RLAIF & Constitutional AI", "post-training-llms", "preference-optimization",
  "Using AI feedback and a constitution to scale alignment supervision.",
  [(R,0.85,DP)])
n("pt-reward-hacking", "Reward Hacking & Overoptimization", "post-training-llms", "safety-failures",
  "How policies exploit imperfect reward models and Goodhart effects.",
  [(R,0.88,DP)])
n("pt-scalable-oversight", "Scalable Oversight", "post-training-llms", "safety-methods",
  "Supervising models on tasks humans cannot easily evaluate directly.",
  [(R,0.82,DP)])
n("pt-mech-interp", "Mechanistic Interpretability", "post-training-llms", "interpretability",
  "Reverse-engineering circuits and features inside trained networks.",
  [(R,0.85,DP)])
n("pt-red-teaming", "Red-Teaming & Jailbreaks", "post-training-llms", "safety-methods",
  "Adversarially probing models for harmful or unintended behavior.",
  [(R,0.80,DP)])
n("pt-rl-formulation", "RL Formulation for LLMs", "post-training-llms", "rl-math",
  "Framing text generation as an MDP: states, actions, and rewards.",
  [(R,0.88,DV)])

e("pt-instruction-tuning","llm-finetuning",1.0)
e("pt-alignment-problem","llm-pretraining",0.4)
e("pt-reward-modeling","pt-bradley-terry",1.0)
e("pt-reward-modeling","pt-instruction-tuning",0.7)
e("pt-bradley-terry","prob-distributions",0.7)
e("pt-bradley-terry","stat-mle",0.7)
e("pt-rl-formulation","prob-markov-chains",0.7)
e("pt-policy-gradient","pt-rl-formulation",1.0)
e("pt-policy-gradient","opt-gradients",1.0)
e("pt-policy-gradient","prob-expectation",1.0)
e("pt-ppo","pt-policy-gradient",1.0)
e("pt-kl-objective","pt-reward-modeling",1.0)
e("pt-kl-objective","pt-policy-gradient",0.7)
e("pt-rlhf-pipeline","pt-ppo",1.0)
e("pt-rlhf-pipeline","pt-kl-objective",1.0)
e("pt-rlhf-pipeline","pt-reward-modeling",1.0)
e("pt-dpo","pt-kl-objective",1.0)
e("pt-dpo","pt-bradley-terry",1.0)
e("pt-rlaif-cai","pt-rlhf-pipeline",0.7)
e("pt-reward-hacking","pt-reward-modeling",1.0)
e("pt-reward-hacking","pt-rlhf-pipeline",0.7)
e("pt-scalable-oversight","pt-alignment-problem",0.7)
e("pt-scalable-oversight","pt-rlaif-cai",0.4)
e("pt-mech-interp","dl-transformer-architecture",1.0)
e("pt-red-teaming","pt-rlhf-pipeline",0.4)
e("pt-red-teaming","pt-alignment-problem",0.7)

# ---- post-training-llms (deepened) ----
n("pt-rl-value-functions", "Value Functions & Critics", "post-training-llms", "rl-math",
  "State/action value functions and the critic in actor-critic methods.",
  [(R,0.85,DV)])
n("pt-advantage-gae", "Advantage Estimation (GAE)", "post-training-llms", "rl-math",
  "Generalized advantage estimation trading off bias and variance.",
  [(R,0.85,DV)])
n("pt-importance-sampling", "Importance Sampling in RL", "post-training-llms", "rl-math",
  "Off-policy correction via importance weights and its variance issues.",
  [(R,0.82,DV)])
n("pt-kl-estimation", "KL Divergence Estimation", "post-training-llms", "rl-math",
  "Practical estimators of KL between policy and reference model.",
  [(R,0.82,DV)])
n("pt-grpo", "Group Relative Policy Optimization", "post-training-llms", "rlhf",
  "GRPO's critic-free, group-normalized advantage for RL fine-tuning.",
  [(R,0.85,DV)])
n("pt-dpo-variants", "IPO, KTO & DPO Variants", "post-training-llms", "preference-optimization",
  "Alternative preference objectives addressing DPO's limitations.",
  [(R,0.85,DV)])
n("pt-best-of-n", "Best-of-N & Rejection Sampling", "post-training-llms", "inference-alignment",
  "Selecting among sampled outputs using a reward model.",
  [(R,0.80,DP)])
n("pt-process-reward", "Process Reward Models", "post-training-llms", "rlhf",
  "Rewarding reasoning steps rather than only final outcomes.",
  [(R,0.82,DP)])
n("pt-deceptive-alignment", "Deceptive Alignment", "post-training-llms", "safety-failures",
  "Models that appear aligned in training but pursue other goals when deployed.",
  [(R,0.85,DP)])
n("pt-sycophancy", "Sycophancy", "post-training-llms", "safety-failures",
  "Preference models rewarding agreement over truthfulness.",
  [(R,0.80,DP)])
n("pt-sae", "Sparse Autoencoders (Interpretability)", "post-training-llms", "interpretability",
  "Decomposing activations into interpretable, monosemantic features.",
  [(R,0.85,DP)])
n("pt-activation-steering", "Activation Steering", "post-training-llms", "interpretability",
  "Steering behavior by adding directions to hidden activations.",
  [(R,0.80,DP)])
n("pt-weak-to-strong", "Weak-to-Strong Generalization", "post-training-llms", "safety-methods",
  "Using weak supervisors to elicit stronger models' capabilities safely.",
  [(R,0.82,DP)])
n("pt-debate", "Debate & Oversight Protocols", "post-training-llms", "safety-methods",
  "Adversarial debate as a mechanism for scalable oversight.",
  [(R,0.78,DP)])
n("pt-safety-evals", "Safety Evaluations", "post-training-llms", "safety-methods",
  "Dangerous-capability evals and alignment benchmarks.",
  [(R,0.80,DP)])

e("pt-rl-value-functions","pt-rl-formulation",1.0)
e("pt-advantage-gae","pt-policy-gradient",1.0)
e("pt-advantage-gae","pt-rl-value-functions",1.0)
e("pt-importance-sampling","pt-policy-gradient",1.0)
e("pt-importance-sampling","prob-expectation",0.7)
e("pt-ppo","pt-advantage-gae",0.7)
e("pt-ppo","pt-importance-sampling",0.7)
e("pt-kl-estimation","pt-kl-objective",1.0)
e("pt-kl-estimation","prob-expectation",0.7)
e("pt-grpo","pt-ppo",1.0)
e("pt-grpo","pt-advantage-gae",0.7)
e("pt-dpo-variants","pt-dpo",1.0)
e("pt-best-of-n","pt-reward-modeling",1.0)
e("pt-process-reward","pt-reward-modeling",1.0)
e("pt-deceptive-alignment","pt-alignment-problem",1.0)
e("pt-sycophancy","pt-rlhf-pipeline",1.0)
e("pt-sycophancy","pt-reward-hacking",0.7)
e("pt-sae","pt-mech-interp",1.0)
e("pt-activation-steering","pt-mech-interp",1.0)
e("pt-weak-to-strong","pt-scalable-oversight",1.0)
e("pt-debate","pt-scalable-oversight",1.0)
e("pt-safety-evals","pt-alignment-problem",0.7)
e("pt-safety-evals","pt-red-teaming",0.7)

# ---- ml-systems-mlops -----------------------------------------------------
n("mlops-data-pipelines", "Data Pipelines", "ml-systems-mlops", "data",
  "Ingestion, transformation, and orchestration of training data.",
  [(R,0.60,AW),(E,0.85,DP),(D,0.72,WK)])
n("mlops-feature-stores", "Feature Stores", "ml-systems-mlops", "data",
  "Managing and serving features consistently for train and inference.",
  [(E,0.78,DP),(D,0.62,WK)])
n("mlops-experiment-tracking", "Experiment Tracking", "ml-systems-mlops", "workflow",
  "Versioning experiments, metrics, and artifacts for reproducibility.",
  [(R,0.62,WK),(E,0.78,DP),(D,0.68,WK)])
n("mlops-model-serving", "Model Serving", "ml-systems-mlops", "deployment",
  "Batch vs online serving, latency, and throughput tradeoffs.",
  [(E,0.88,DP),(R,0.58,AW)])
n("mlops-monitoring", "Model Monitoring & Drift", "ml-systems-mlops", "operations",
  "Detecting data/concept drift and degradation in production.",
  [(E,0.82,DP),(D,0.70,WK)])
n("mlops-distributed-training", "Distributed Training", "ml-systems-mlops", "training",
  "Data/model parallelism and multi-GPU training strategies.",
  [(R,0.72,DP),(E,0.78,DP)])
n("mlops-ab-testing-ml", "Online Evaluation & A/B Testing", "ml-systems-mlops", "operations",
  "Shadow deployments, canaries, and measuring model impact live.",
  [(E,0.78,DP),(D,0.75,WK)])

e("mlops-feature-stores","mlops-data-pipelines",1.0)
e("mlops-model-serving","sysd-scalability",0.7)
e("mlops-monitoring","mlops-model-serving",0.7)
e("mlops-distributed-training","dl-backprop",0.7)
e("mlops-distributed-training","opt-sgd",0.7)
e("mlops-ab-testing-ml","mlops-model-serving",0.7)
e("mlops-experiment-tracking","ml-train-test-split",0.4)

# ===========================================================================
# ROLE-SPECIFIC SECTIONS
# ===========================================================================

# ---- data-science-analytics -----------------------------------------------
n("ds-eda", "Exploratory Data Analysis", "data-science-analytics", "analysis",
  "Profiling distributions, spotting anomalies, and forming hypotheses.",
  [(E,0.62,WK),(D,0.90,DP),(P,0.60,WK)])
n("ds-data-cleaning", "Data Cleaning & Wrangling", "data-science-analytics", "analysis",
  "Handling missing values, outliers, and inconsistent formats.",
  [(E,0.65,WK),(D,0.88,DP)])
n("ds-ab-testing", "A/B Testing Design", "data-science-analytics", "experimentation",
  "Designing controlled experiments: randomization, power, and MDE.",
  [(E,0.62,WK),(D,0.92,DP),(P,0.85,DP)])
n("ds-causal-inference", "Causal Inference", "data-science-analytics", "experimentation",
  "Confounding, DAGs, difference-in-differences, and instrumental variables.",
  [(D,0.82,DP),(P,0.62,WK),(R,0.55,AW)])
n("ds-metrics-design", "Metric Design", "data-science-analytics", "product-analytics",
  "Defining north-star and guardrail metrics that resist gaming.",
  [(D,0.85,DP),(P,0.88,DP)])
n("ds-sql-analytics", "Analytical SQL", "data-science-analytics", "tools",
  "Window functions, CTEs, and cohort queries for analysis.",
  [(E,0.62,WK),(D,0.88,DP),(P,0.62,WK)])
n("ds-experiment-pitfalls", "Experiment Pitfalls", "data-science-analytics", "experimentation",
  "Peeking, novelty effects, network effects, and Simpson's paradox.",
  [(D,0.80,DP),(P,0.72,WK)])
n("ds-storytelling", "Data Storytelling", "data-science-analytics", "communication",
  "Turning analysis into clear, decision-driving narratives.",
  [(D,0.78,WK),(P,0.75,WK)])
n("ds-dashboards", "Dashboards & Visualization", "data-science-analytics", "communication",
  "Designing visualizations that communicate accurately.",
  [(D,0.70,WK),(P,0.65,WK)])

e("ds-data-cleaning","ds-eda",0.7)
e("ds-ab-testing","stat-hypothesis-testing",1.0)
e("ds-ab-testing","stat-t-test",0.7)
e("ds-causal-inference","stat-linear-regression",0.7)
e("ds-causal-inference","ds-ab-testing",0.7)
e("ds-metrics-design","ds-eda",0.4)
e("ds-sql-analytics","cs-sql",1.0)
e("ds-experiment-pitfalls","ds-ab-testing",1.0)
e("ds-storytelling","ds-eda",0.4)
e("ds-dashboards","ds-eda",0.4)

# ---- product-management ---------------------------------------------------
n("pm-product-sense", "Product Sense", "product-management", "core",
  "Identifying user needs and evaluating product ideas.",
  [(D,0.60,WK),(P,0.95,DV)])
n("pm-metrics", "Product Metrics", "product-management", "analytics",
  "Choosing and reasoning about engagement, retention, and revenue metrics.",
  [(D,0.68,WK),(P,0.92,DP)])
n("pm-prioritization", "Prioritization Frameworks", "product-management", "execution",
  "RICE, cost-benefit, and tradeoff reasoning for roadmaps.",
  [(P,0.88,DP)])
n("pm-estimation", "Market & Estimation Questions", "product-management", "analysis",
  "Structured guesstimates and market sizing.",
  [(P,0.85,DP),(F,0.55,WK)])
n("pm-product-design", "Product Design Questions", "product-management", "core",
  "Designing a product/feature for a user segment end-to-end.",
  [(P,0.90,DP)])
n("pm-strategy", "Product Strategy", "product-management", "strategy",
  "Competitive analysis, moats, and go-to-market reasoning.",
  [(P,0.85,DP)])
n("pm-execution", "Execution & Tradeoffs", "product-management", "execution",
  "Scoping MVPs, handling constraints, and shipping decisions.",
  [(P,0.85,DP)])
n("pm-root-cause", "Diagnosing Metric Changes", "product-management", "analytics",
  "Debugging why a metric moved using structured decomposition.",
  [(D,0.65,WK),(P,0.85,DP)])
n("pm-ai-product", "AI Product Considerations", "product-management", "technical-pm",
  "Evaluating where and how to apply ML in products responsibly.",
  [(P,0.68,WK),(R,0.45,AW)])

e("pm-metrics","pm-product-sense",0.7)
e("pm-prioritization","pm-product-sense",0.7)
e("pm-product-design","pm-product-sense",1.0)
e("pm-strategy","pm-product-sense",0.7)
e("pm-execution","pm-prioritization",0.7)
e("pm-root-cause","pm-metrics",1.0)
e("pm-estimation","pm-product-sense",0.4)
e("pm-metrics","ds-metrics-design",0.4)
e("pm-ai-product","pm-product-sense",0.7)

# ---- finance-quant --------------------------------------------------------
n("fq-mental-math", "Mental Math & Estimation", "finance-quant", "aptitude",
  "Fast arithmetic and numerical estimation under pressure.",
  [(F,0.90,DP)])
n("fq-brainteasers", "Probability Brainteasers", "finance-quant", "aptitude",
  "Classic probability puzzles and expected-value reasoning.",
  [(F,0.92,DV)])
n("fq-expected-value-games", "Expected Value & Betting Games", "finance-quant", "aptitude",
  "Fair value, optimal strategy, and risk in games of chance.",
  [(F,0.90,DV)])
n("fq-stochastic-processes", "Stochastic Processes", "finance-quant", "math",
  "Random walks, martingales, and Brownian motion basics.",
  [(F,0.85,DV),(R,0.50,AW)])
n("fq-time-value-money", "Time Value of Money", "finance-quant", "finance",
  "Present/future value, discounting, and compounding.",
  [(F,0.85,DP)])
n("fq-options-basics", "Options & Derivatives Basics", "finance-quant", "finance",
  "Calls, puts, payoff diagrams, and put-call parity.",
  [(F,0.82,DP)])
n("fq-black-scholes", "Black-Scholes Intuition", "finance-quant", "finance",
  "The pricing model's assumptions and qualitative behavior.",
  [(F,0.72,WK)])
n("fq-portfolio-theory", "Portfolio Theory", "finance-quant", "finance",
  "Diversification, mean-variance optimization, and the efficient frontier.",
  [(F,0.75,WK)])
n("fq-market-microstructure", "Market Microstructure", "finance-quant", "markets",
  "Order books, bid-ask spreads, and market making basics.",
  [(F,0.72,WK)])
n("fq-statistics-trading", "Statistical Arbitrage Concepts", "finance-quant", "markets",
  "Mean reversion, cointegration, and signal construction.",
  [(F,0.70,WK)])
n("fq-programming", "Quant Programming", "finance-quant", "implementation",
  "Efficient numerical coding for simulation and backtesting.",
  [(F,0.80,DP)])
n("fq-monte-carlo", "Monte Carlo Methods", "finance-quant", "math",
  "Simulation-based estimation of expectations and pricing.",
  [(F,0.78,DP),(R,0.55,AW)])

e("fq-brainteasers","prob-conditional",1.0)
e("fq-brainteasers","prob-expectation",1.0)
e("fq-expected-value-games","prob-expectation",1.0)
e("fq-expected-value-games","fq-brainteasers",0.4)
e("fq-stochastic-processes","prob-markov-chains",1.0)
e("fq-stochastic-processes","prob-conditional-expectation",0.7)
e("fq-options-basics","fq-time-value-money",0.7)
e("fq-black-scholes","fq-options-basics",1.0)
e("fq-black-scholes","fq-stochastic-processes",0.7)
e("fq-portfolio-theory","prob-covariance",1.0)
e("fq-portfolio-theory","opt-convex-optimization",0.7)
e("fq-statistics-trading","stat-time-series",1.0)
e("fq-monte-carlo","prob-distributions",1.0)
e("fq-monte-carlo","fq-programming",0.4)
e("fq-market-microstructure","fq-options-basics",0.4)

# ===========================================================================
# VALIDATION
# ===========================================================================
def validate():
    errors, warnings = [], []
    ids = [x["node_id"] for x in NODES]
    idset = set(ids)

    # unique ids
    seen = set()
    for i in ids:
        if i in seen:
            errors.append(f"duplicate node_id: {i}")
        seen.add(i)

    # section prefix + valid section/role/depth/importance
    names = defaultdict(list)
    for x in NODES:
        sec = x["section"]
        if sec not in SECTION_ABBREV:
            errors.append(f"{x['node_id']}: unknown section {sec}")
        else:
            pref = SECTION_ABBREV[sec] + "-"
            if not x["node_id"].startswith(pref):
                errors.append(f"{x['node_id']}: id not prefixed with '{pref}'")
        if x["type"] not in ("assessable", "concept"):
            errors.append(f"{x['node_id']}: bad type {x['type']}")
        if not x["roles"]:
            warnings.append(f"{x['node_id']}: no role tags")
        for r in x["roles"]:
            if r["role_id"] not in ROLE_IDS:
                errors.append(f"{x['node_id']}: unknown role {r['role_id']}")
            if not (0.0 <= r["importance"] <= 1.0):
                errors.append(f"{x['node_id']}: importance out of range {r['importance']}")
            if r["required_depth"] not in DEPTHS:
                errors.append(f"{x['node_id']}: bad depth {r['required_depth']}")
        names[x["name"].strip().lower()].append(x["node_id"])

    for nm, lst in names.items():
        if len(lst) > 1:
            warnings.append(f"possible duplicate concept '{nm}': {lst}")

    # edges reference existing nodes; weights valid
    for ed in EDGES:
        if ed["from_node_id"] not in idset:
            errors.append(f"edge from unknown node: {ed['from_node_id']}")
        if ed["to_node_id"] not in idset:
            errors.append(f"edge to unknown node: {ed['to_node_id']}")
        if ed["type"] not in ("prerequisite", "part_of"):
            errors.append(f"bad edge type: {ed['type']}")
        if not (0.0 <= ed["weight"] <= 1.0):
            errors.append(f"edge weight out of range: {ed}")
        if ed["from_node_id"] == ed["to_node_id"]:
            errors.append(f"self-loop edge: {ed['from_node_id']}")

    # acyclicity of prerequisite subgraph (Kahn)
    adj = defaultdict(list); indeg = defaultdict(int)
    prereq_nodes = set()
    for ed in EDGES:
        if ed["type"] != "prerequisite":
            continue
        # from depends on to  =>  to must come first  =>  edge to -> from
        adj[ed["to_node_id"]].append(ed["from_node_id"])
        indeg[ed["from_node_id"]] += 1
        prereq_nodes.add(ed["from_node_id"]); prereq_nodes.add(ed["to_node_id"])
    q = deque([x for x in prereq_nodes if indeg[x] == 0])
    visited = 0
    while q:
        u = q.popleft(); visited += 1
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if visited != len(prereq_nodes):
        errors.append(f"CYCLE in prerequisite subgraph: {len(prereq_nodes)-visited} nodes unresolved")

    return errors, warnings

def stats():
    per_section = defaultdict(int)
    per_role = defaultdict(int)
    for x in NODES:
        per_section[x["section"]] += 1
        for r in x["roles"]:
            per_role[r["role_id"]] += 1
    return per_section, per_role

if __name__ == "__main__":
    # Windows consoles default to cp1252, which cannot encode the glyphs below or any
    # non-ASCII character appearing in a node name/description echoed by an error message.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover - Python < 3.7
        pass
    errs, warns = validate()
    per_section, per_role = stats()
    print(f"NODES: {len(NODES)}   EDGES: {len(EDGES)}")
    print("\nNodes per section:")
    for s in SECTION_ABBREV:
        print(f"  {s:26s} {per_section.get(s,0)}")
    print("\nRole tag counts (nodes tagged for each role):")
    for r in ROLES:
        print(f"  {r['role_id']:22s} {per_role.get(r['role_id'],0)}")
    print(f"\nERRORS: {len(errs)}")
    for x in errs: print("  ✗", x)
    print(f"WARNINGS: {len(warns)}")
    for x in warns: print("  !", x)

    if errs:
        print("\nNOT WRITING JSON — fix errors first.")
        sys.exit(1)

    out = {"roles": ROLES, "nodes": NODES, "edges": EDGES}
    outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "curriculum_graph.json")
    # newline="\n" keeps output byte-identical across platforms (Windows text mode would emit CRLF)
    with open(outpath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {outpath}")
