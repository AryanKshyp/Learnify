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
n("prob-joint-marginal", "Joint & Marginal Distributions", "probability", "random-variables",
  "Joint PMFs/PDFs over multiple random variables and recovering marginals by summing or integrating them out.",
  [(R,0.85,DP),(E,0.78,WK),(D,0.82,WK),(F,0.88,DV)])
n("prob-transformations", "Transformations of Random Variables", "probability", "random-variables",
  "Deriving the distribution of a function of a random variable via the CDF technique or the change-of-variables Jacobian formula.",
  [(R,0.78,DP),(E,0.65,WK),(D,0.68,WK),(F,0.85,DV)])
n("prob-order-statistics", "Order Statistics", "probability", "random-variables",
  "Distributions of the minimum, maximum, and general k-th order statistic of i.i.d. samples.",
  [(R,0.65,WK),(D,0.60,WK),(F,0.75,DP)])
n("prob-poisson-process", "Poisson Processes", "probability", "stochastic",
  "Continuous-time counting processes with independent, stationary increments, and their link to exponential interarrival times.",
  [(R,0.68,WK),(E,0.55,AW),(D,0.62,WK),(F,0.82,DP)])
n("prob-entropy-kl", "Entropy & KL Divergence", "probability", "information-theory",
  "Shannon entropy, cross-entropy, and KL divergence as a measure of the difference between two distributions.",
  [(R,0.85,DP),(E,0.75,WK),(D,0.62,WK)])
n("prob-sampling-methods", "Sampling Methods", "probability", "computation",
  "Generating samples from a target distribution via inverse-CDF sampling, rejection sampling, and importance sampling.",
  [(R,0.72,WK),(E,0.62,WK),(D,0.65,WK),(F,0.78,DP)])
n("prob-convergence-modes", "Modes of Stochastic Convergence", "probability", "limit-theorems",
  "Convergence in probability, in distribution, and almost surely, and how each relates to the LLN and CLT.",
  [(R,0.72,DP),(D,0.55,WK),(F,0.75,DP)])
n("prob-multivariate-normal", "Multivariate Normal Distribution", "probability", "random-variables",
  "The multivariate Gaussian, its covariance-matrix parameterization, and conditional/marginal Gaussian identities.",
  [(R,0.82,DP),(E,0.70,WK),(D,0.68,WK),(F,0.80,DP)])
n("prob-characteristic-functions", "Characteristic Functions", "probability", "moments",
  "Fourier-transform-like functions that uniquely determine a distribution and simplify analysis of sums of independent variables.",
  [(R,0.55,WK),(F,0.70,DP)])
n("prob-concentration-inequalities", "Concentration Inequalities & Tail Bounds", "probability", "limit-theorems",
  "Chernoff bounds and Hoeffding's inequality for exponentially tight tail probability bounds beyond Chebyshev.",
  [(R,0.75,DP),(E,0.60,WK),(F,0.80,DP)])
n("prob-random-walks", "Random Walks", "probability", "stochastic",
  "Simple random walks on the integers, expected displacement, and the gambler's ruin problem.",
  [(R,0.60,WK),(F,0.78,DP)])
n("prob-variance-reduction", "Variance Reduction Techniques", "probability", "computation",
  "Antithetic variates, control variates, and stratified sampling for reducing Monte Carlo estimator variance.",
  [(R,0.55,WK),(F,0.75,DP)])
n("prob-hypergeometric-negbinom", "Hypergeometric & Negative Binomial Distributions", "probability", "random-variables",
  "Sampling without replacement and counting trials until r successes, extending the binomial family.",
  [(R,0.55,AW),(D,0.60,WK),(F,0.72,WK)])
n("prob-multinomial-dirichlet", "Multinomial & Dirichlet Distributions", "probability", "random-variables",
  "The multivariate generalizations of the binomial and beta distributions, used to model categorical outcomes and their conjugate priors.",
  [(R,0.68,WK),(D,0.55,AW)])
n("prob-total-variance", "Law of Total Variance", "probability", "moments",
  "Eve's law: decomposing variance into the expected conditional variance plus the variance of the conditional expectation.",
  [(R,0.65,WK),(D,0.55,AW),(F,0.75,WK)])

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
e("prob-joint-marginal","prob-random-variables",1.0)
e("prob-joint-marginal","prob-independence",0.4)
e("prob-transformations","prob-random-variables",1.0)
e("prob-transformations","prob-joint-marginal",0.4)
e("prob-order-statistics","prob-distributions",1.0)
e("prob-order-statistics","prob-joint-marginal",0.7)
e("prob-poisson-process","prob-distributions",1.0)
e("prob-poisson-process","prob-markov-chains",0.4)
e("prob-entropy-kl","prob-expectation",1.0)
e("prob-entropy-kl","prob-distributions",0.7)
e("prob-sampling-methods","prob-distributions",1.0)
e("prob-sampling-methods","prob-expectation",0.4)
e("prob-convergence-modes","prob-lln",0.7)
e("prob-convergence-modes","prob-clt",0.7)
e("prob-multivariate-normal","prob-covariance",1.0)
e("prob-multivariate-normal","prob-distributions",0.7)
e("prob-multivariate-normal","linalg-pd-matrices",0.7)
e("prob-characteristic-functions","prob-mgf",0.7)
e("prob-concentration-inequalities","prob-inequalities",1.0)
e("prob-concentration-inequalities","prob-mgf",0.7)
e("prob-random-walks","prob-markov-chains",1.0)
e("prob-variance-reduction","prob-sampling-methods",1.0)
e("prob-variance-reduction","prob-covariance",0.4)
e("prob-hypergeometric-negbinom","prob-distributions",1.0)
e("prob-hypergeometric-negbinom","prob-counting",0.4)
e("prob-multinomial-dirichlet","prob-distributions",1.0)
e("prob-total-variance","prob-conditional-expectation",1.0)

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
n("stat-method-of-moments", "Method of Moments Estimation", "statistics", "estimation",
  "Estimating parameters by equating sample moments to theoretical moments; simpler but generally less efficient than MLE.",
  [(R,0.65,WK),(E,0.55,AW),(D,0.62,WK),(F,0.70,WK)])
n("stat-sufficient-statistics", "Sufficient Statistics & Factorization Theorem", "statistics", "estimation",
  "Statistics that capture all sample information about a parameter, and the Fisher-Neyman factorization theorem for identifying them.",
  [(R,0.68,DP),(D,0.55,WK),(F,0.72,DP)])
n("stat-fisher-information", "Fisher Information & Cramér-Rao Bound", "statistics", "estimation",
  "Quantifying the information a sample carries about a parameter, and the theoretical lower bound on unbiased estimator variance.",
  [(R,0.72,DV),(D,0.50,AW),(F,0.78,DV)])
n("stat-power-analysis", "Power Analysis & Sample Size Determination", "statistics", "inference",
  "Computing statistical power, minimum detectable effect, and required sample size given significance level and effect size.",
  [(R,0.72,WK),(E,0.60,WK),(D,0.85,DP),(P,0.65,WK),(F,0.70,WK)])
n("stat-chi-square-tests", "Chi-Square Tests", "statistics", "inference",
  "Goodness-of-fit and independence testing for categorical data using the chi-square statistic.",
  [(R,0.62,WK),(D,0.80,DP),(P,0.55,AW),(F,0.65,WK)])
n("stat-nonparametric-tests", "Non-Parametric Tests", "statistics", "inference",
  "Distribution-free tests -- Mann-Whitney U, Wilcoxon signed-rank, and Kruskal-Wallis -- for when parametric assumptions fail.",
  [(R,0.58,WK),(D,0.75,DP),(F,0.60,WK)])
n("stat-regression-diagnostics", "Regression Diagnostics & Assumption Checking", "statistics", "regression",
  "Checking linearity, homoscedasticity, and normality of residuals, and identifying influential points via leverage and Cook's distance.",
  [(R,0.75,DP),(E,0.65,WK),(D,0.88,DP),(F,0.75,DP)])
n("stat-multicollinearity", "Multicollinearity & Variance Inflation Factor", "statistics", "regression",
  "Detecting and addressing correlated predictors using VIF, and its effect on coefficient stability and interpretation.",
  [(R,0.62,WK),(D,0.78,DP),(F,0.65,WK)])
n("stat-sampling-design", "Sampling Methods & Study Design", "statistics", "foundations",
  "Simple random, stratified, and cluster sampling; observational vs. experimental design; and sources of sampling bias.",
  [(R,0.55,AW),(D,0.82,DP),(P,0.60,WK),(F,0.60,WK)])
n("stat-correlation-causation", "Correlation vs. Causation & Confounding", "statistics", "foundations",
  "Why correlation does not imply causation, spurious correlation, and confounding variables.",
  [(R,0.70,WK),(E,0.55,AW),(D,0.85,DP),(P,0.65,WK),(F,0.62,WK)])
n("stat-qq-plots", "Q-Q Plots & Distributional Diagnostics", "statistics", "model-quality",
  "Assessing whether data follows an assumed distribution using quantile-quantile plots, skewness, and kurtosis.",
  [(R,0.58,WK),(D,0.72,WK),(F,0.60,WK)])
n("stat-model-selection-criteria", "Model Selection Criteria (AIC/BIC)", "statistics", "model-quality",
  "Comparing models via likelihood-based information criteria that penalize complexity, as an alternative to cross-validation.",
  [(R,0.65,WK),(D,0.68,WK),(F,0.62,WK)])
n("stat-survival-analysis", "Survival Analysis", "statistics", "time-series",
  "Modeling time-to-event data with censoring, Kaplan-Meier estimates, and hazard functions.",
  [(D,0.60,WK),(F,0.55,AW)])
n("stat-robust-statistics", "Robust Statistics", "statistics", "model-quality",
  "Estimators resistant to outliers -- median, MAD, trimmed means, and M-estimators -- and when to prefer them over OLS.",
  [(R,0.55,WK),(D,0.68,WK),(F,0.58,WK)])
n("stat-sequential-testing", "Sequential Testing & Always-Valid Inference", "statistics", "inference",
  "Sequential probability ratio tests and alpha-spending methods for valid inference under continuous monitoring.",
  [(D,0.65,WK),(F,0.68,WK)])

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
e("stat-method-of-moments","stat-estimation",1.0)
e("stat-method-of-moments","prob-expectation",0.7)
e("stat-sufficient-statistics","stat-estimation",1.0)
e("stat-sufficient-statistics","prob-distributions",0.4)
e("stat-fisher-information","stat-sufficient-statistics",0.7)
e("stat-fisher-information","stat-mle",0.7)
e("stat-power-analysis","stat-hypothesis-testing",1.0)
e("stat-chi-square-tests","stat-hypothesis-testing",1.0)
e("stat-chi-square-tests","prob-distributions",0.4)
e("stat-nonparametric-tests","stat-hypothesis-testing",0.7)
e("stat-nonparametric-tests","stat-t-test",0.4)
e("stat-regression-diagnostics","stat-linear-regression",1.0)
e("stat-multicollinearity","stat-regression-diagnostics",0.7)
e("stat-multicollinearity","prob-covariance",0.4)
e("stat-sampling-design","stat-descriptive",0.4)
e("stat-correlation-causation","prob-covariance",0.7)
e("stat-qq-plots","prob-distributions",0.4)
e("stat-qq-plots","stat-descriptive",0.4)
e("stat-model-selection-criteria","stat-mle",0.7)
e("stat-model-selection-criteria","stat-bias-variance",0.4)
e("stat-survival-analysis","stat-time-series",0.4)
e("stat-survival-analysis","prob-distributions",0.4)
e("stat-robust-statistics","stat-regression-diagnostics",0.4)
e("stat-robust-statistics","stat-descriptive",0.4)
e("stat-sequential-testing","stat-hypothesis-testing",0.7)
e("stat-sequential-testing","stat-power-analysis",0.4)

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

# ---- linear-algebra (deepened) ----
n("linalg-linear-transformations", "Linear Transformations & Change of Basis", "linear-algebra", "foundations",
  "Linear maps represented as matrices, how they act geometrically, and representing them under different bases.",
  [(R,0.75,DP),(E,0.65,WK)])
n("linalg-determinants", "Determinants", "linear-algebra", "operations",
  "Determinants as signed volume scaling, their relation to invertibility, and computation via cofactor expansion or decomposition.",
  [(R,0.70,WK),(E,0.62,WK),(F,0.60,WK)])
n("linalg-null-column-space", "Null Space & Column Space", "linear-algebra", "operations",
  "The four fundamental subspaces, the rank-nullity theorem, and their geometric meaning for solvability.",
  [(R,0.72,DP),(E,0.65,WK),(D,0.45,AW)])
n("linalg-linear-systems", "Solving Linear Systems", "linear-algebra", "operations",
  "Solving Ax=b via Gaussian elimination; existence, uniqueness, and row-reduced echelon form.",
  [(R,0.68,WK),(E,0.70,WK),(F,0.58,WK)])
n("linalg-lu-decomposition", "LU Decomposition", "linear-algebra", "decompositions",
  "Factoring a matrix into lower and upper triangular factors for efficient solving of linear systems.",
  [(R,0.60,WK),(E,0.65,WK)])
n("linalg-qr-decomposition", "QR Decomposition", "linear-algebra", "decompositions",
  "Factoring a matrix into an orthogonal matrix and an upper-triangular matrix via Gram-Schmidt or Householder reflections.",
  [(R,0.68,WK),(E,0.65,WK)])
n("linalg-cholesky", "Cholesky Decomposition", "linear-algebra", "decompositions",
  "Factoring a positive-definite matrix into a lower-triangular matrix and its transpose.",
  [(R,0.62,WK),(E,0.60,WK)])
n("linalg-diagonalization", "Diagonalization", "linear-algebra", "decompositions",
  "Diagonalizing a matrix via its eigenvectors, computing matrix powers efficiently, and when diagonalization fails.",
  [(R,0.75,DP),(E,0.62,WK)])
n("linalg-pseudoinverse", "Moore-Penrose Pseudoinverse", "linear-algebra", "operations",
  "Generalizing matrix inversion to non-square or singular matrices via the pseudoinverse, and its use in least-squares.",
  [(R,0.70,DP),(E,0.62,WK)])
n("linalg-least-squares", "Projections & Least Squares", "linear-algebra", "geometry",
  "Orthogonal projection onto a subspace and deriving the least-squares solution via normal equations.",
  [(R,0.78,DP),(E,0.70,WK),(D,0.55,WK)])
n("linalg-quadratic-forms", "Quadratic Forms", "linear-algebra", "special-matrices",
  "Quadratic forms x^T A x, their relation to positive-definiteness, and geometric interpretation as ellipsoids/level sets.",
  [(R,0.70,DP),(E,0.58,WK),(F,0.55,WK)])
n("linalg-matrix-norms", "Matrix Norms", "linear-algebra", "geometry",
  "Operator/spectral norm and Frobenius norm, and their use in bounding transformations.",
  [(R,0.65,WK),(E,0.60,WK)])
n("linalg-trace", "Trace & Trace Tricks", "linear-algebra", "operations",
  "Trace's cyclic property, its relation to eigenvalues, and common trace-based simplifications used in derivations.",
  [(R,0.62,WK),(E,0.55,AW)])
n("linalg-condition-number", "Condition Number & Numerical Stability", "linear-algebra", "special-matrices",
  "How a matrix's condition number governs sensitivity to perturbation and numerical error in computation.",
  [(R,0.68,DP),(E,0.70,WK)])
n("linalg-low-rank-approx", "Low-Rank Approximation", "linear-algebra", "decompositions",
  "Approximating a matrix with a lower-rank one that minimizes reconstruction error (Eckart-Young theorem).",
  [(R,0.78,DP),(E,0.72,WK)])
n("linalg-tensor-ops", "Tensor Operations & Broadcasting", "linear-algebra", "operations",
  "Multi-dimensional array operations, broadcasting rules, and reshaping as used throughout deep learning frameworks.",
  [(R,0.72,WK),(E,0.82,DP)])
n("linalg-kronecker", "Kronecker Product", "linear-algebra", "operations",
  "The Kronecker product of matrices and its use in structured transformations and efficient parameterization.",
  [(R,0.55,AW)])

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

e("linalg-linear-transformations","linalg-vectors",1.0)
e("linalg-linear-transformations","linalg-matrix-multiplication",0.7)
e("linalg-determinants","linalg-matrix-multiplication",0.7)
e("linalg-null-column-space","linalg-matrix-inverse",0.7)
e("linalg-linear-systems","linalg-matrix-inverse",0.7)
e("linalg-linear-systems","linalg-determinants",0.4)
e("linalg-lu-decomposition","linalg-linear-systems",1.0)
e("linalg-qr-decomposition","linalg-orthogonality",1.0)
e("linalg-cholesky","linalg-pd-matrices",1.0)
e("linalg-diagonalization","linalg-eigen",1.0)
e("linalg-pseudoinverse","linalg-svd",1.0)
e("linalg-pseudoinverse","linalg-matrix-inverse",0.4)
e("linalg-least-squares","linalg-orthogonality",1.0)
e("linalg-quadratic-forms","linalg-pd-matrices",1.0)
e("linalg-matrix-norms","linalg-dot-product",0.7)
e("linalg-matrix-norms","linalg-eigen",0.4)
e("linalg-trace","linalg-eigen",0.4)
e("linalg-condition-number","linalg-eigen",0.7)
e("linalg-low-rank-approx","linalg-svd",1.0)
e("linalg-tensor-ops","linalg-matrix-multiplication",0.7)
e("linalg-kronecker","linalg-matrix-multiplication",0.7)

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
n("opt-taylor-expansion", "Taylor Expansion & Local Approximation", "calculus-optimization", "calculus",
  "Approximating functions locally via Taylor series; linear and quadratic approximations used throughout optimization theory.",
  [(R,0.75,DP),(E,0.60,WK),(D,0.45,AW),(F,0.75,DP)])
n("opt-hessian-second-order", "Hessians & Second-Order Optimality Conditions", "calculus-optimization", "theory",
  "Using the Hessian's eigenvalues to classify critical points as minima, maxima, or saddle points.",
  [(R,0.78,DP),(E,0.65,WK),(F,0.68,WK)])
n("opt-convexity-tests", "Convexity Tests & Verification", "calculus-optimization", "theory",
  "First- and second-order conditions (gradient inequality, PSD Hessian) for verifying convexity of a function.",
  [(R,0.72,WK),(E,0.60,WK),(F,0.70,WK)])
n("opt-saddle-points", "Saddle Points & Critical Point Classification", "calculus-optimization", "theory",
  "Why saddle points dominate high-dimensional non-convex loss landscapes and how they slow first-order optimization.",
  [(R,0.75,DP),(E,0.62,WK)])
n("opt-duality", "Lagrangian Duality", "calculus-optimization", "constrained",
  "Weak/strong duality, the duality gap, and complementary slackness in constrained optimization.",
  [(R,0.72,WK),(E,0.55,WK),(F,0.75,DP)])
n("opt-quasi-newton", "Quasi-Newton Methods & L-BFGS", "calculus-optimization", "algorithms",
  "Approximating curvature without computing the full Hessian; BFGS and limited-memory L-BFGS updates.",
  [(R,0.65,WK),(E,0.60,WK),(F,0.60,WK)])
n("opt-line-search", "Line Search & Step Size Selection", "calculus-optimization", "algorithms",
  "Choosing step sizes via exact/backtracking line search and the Wolfe conditions.",
  [(R,0.60,WK),(E,0.55,WK),(F,0.55,WK)])
n("opt-convergence-rates", "Convergence Rates of Optimization Algorithms", "calculus-optimization", "theory",
  "Comparing linear, sublinear, and quadratic convergence rates across gradient descent, Newton, and quasi-Newton methods.",
  [(R,0.70,WK),(E,0.62,WK),(F,0.60,WK)])
n("opt-coordinate-descent", "Coordinate Descent", "calculus-optimization", "algorithms",
  "Optimizing one coordinate (or block) at a time; used in Lasso, SVM SMO, and large-scale sparse problems.",
  [(R,0.60,WK),(E,0.65,WK),(F,0.55,WK),(D,0.45,AW)])
n("opt-proximal-methods", "Proximal Gradient Methods", "calculus-optimization", "algorithms",
  "Handling non-smooth regularizers (e.g. L1) via proximal operators and soft-thresholding.",
  [(R,0.62,WK),(E,0.65,WK),(F,0.55,WK)])
n("opt-subgradient-methods", "Subgradient Methods for Non-Smooth Optimization", "calculus-optimization", "algorithms",
  "Generalizing gradients to non-differentiable convex functions via subgradients, as in hinge loss and L1 penalties.",
  [(R,0.60,WK),(E,0.62,WK)])
n("opt-automatic-differentiation", "Automatic Differentiation", "calculus-optimization", "algorithms",
  "Forward-mode vs reverse-mode automatic differentiation via computational graphs, the general technique underlying backpropagation.",
  [(R,0.80,DP),(E,0.85,DP),(D,0.45,AW)])
n("opt-change-of-variables", "Multivariate Integration & Change of Variables", "calculus-optimization", "calculus",
  "Transforming integrals under a change of variables using the Jacobian determinant.",
  [(R,0.68,WK),(E,0.55,WK),(F,0.65,WK)])
n("opt-lipschitz-smoothness", "Lipschitz Continuity & Smoothness", "calculus-optimization", "theory",
  "Lipschitz-continuous gradients and smoothness constants that bound step sizes and drive convergence proofs.",
  [(R,0.65,WK),(E,0.55,WK),(F,0.55,WK)])
n("opt-minimax-optimization", "Minimax & Saddle-Point Optimization", "calculus-optimization", "theory",
  "Game-theoretic min-max formulations underlying adversarial training, GANs, and robust optimization.",
  [(R,0.72,WK),(E,0.60,WK),(F,0.55,WK)])
n("opt-natural-gradient", "Natural Gradient Descent", "calculus-optimization", "algorithms",
  "Rescaling gradient steps by the Fisher information metric for parameterization-invariant updates.",
  [(R,0.62,WK),(E,0.50,WK)])
n("opt-variance-reduction", "Variance Reduction in Stochastic Optimization", "calculus-optimization", "algorithms",
  "SVRG/SAGA-style techniques that reduce gradient-estimate variance to accelerate SGD convergence.",
  [(R,0.58,WK),(E,0.60,WK)])
n("opt-trust-region", "Trust-Region Methods", "calculus-optimization", "algorithms",
  "Constraining each optimization step to a region where a local model is trusted, as an alternative to line search.",
  [(R,0.60,WK),(E,0.55,WK),(F,0.55,WK)])

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
e("opt-taylor-expansion","opt-derivatives",1.0)
e("opt-hessian-second-order","opt-gradients",1.0)
e("opt-hessian-second-order","opt-taylor-expansion",0.7)
e("opt-hessian-second-order","linalg-pd-matrices",0.7)
e("opt-convexity-tests","opt-convexity",1.0)
e("opt-convexity-tests","opt-hessian-second-order",0.7)
e("opt-saddle-points","opt-hessian-second-order",1.0)
e("opt-saddle-points","opt-gradient-descent",0.4)
e("opt-duality","opt-lagrange",1.0)
e("opt-duality","opt-convex-optimization",0.7)
e("opt-quasi-newton","opt-second-order",1.0)
e("opt-quasi-newton","linalg-pd-matrices",0.4)
e("opt-line-search","opt-gradient-descent",1.0)
e("opt-convergence-rates","opt-gradient-descent",1.0)
e("opt-convergence-rates","opt-convexity",0.7)
e("opt-coordinate-descent","opt-gradient-descent",0.7)
e("opt-coordinate-descent","opt-convexity",0.4)
e("opt-subgradient-methods","opt-convexity",0.7)
e("opt-subgradient-methods","opt-gradient-descent",0.7)
e("opt-proximal-methods","opt-coordinate-descent",0.4)
e("opt-proximal-methods","opt-convexity",0.7)
e("opt-proximal-methods","opt-subgradient-methods",0.7)
e("opt-automatic-differentiation","opt-derivatives",1.0)
e("opt-automatic-differentiation","opt-gradients",0.7)
e("opt-change-of-variables","opt-derivatives",0.7)
e("opt-change-of-variables","opt-gradients",0.7)
e("opt-lipschitz-smoothness","opt-derivatives",0.7)
e("opt-lipschitz-smoothness","opt-convexity",0.4)
e("opt-minimax-optimization","opt-convexity",0.4)
e("opt-minimax-optimization","opt-gradient-descent",0.7)
e("opt-minimax-optimization","opt-saddle-points",0.7)
e("opt-natural-gradient","opt-gradient-descent",1.0)
e("opt-natural-gradient","linalg-pd-matrices",0.4)
e("opt-variance-reduction","opt-sgd",1.0)
e("opt-trust-region","opt-second-order",0.7)
e("opt-trust-region","opt-line-search",0.4)

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

# ---- dsa (deepened further: gap-fill pass) ----
n("dsa-lru-cache", "LRU Cache Design", "dsa", "design",
  "Designing a Least-Recently-Used cache with O(1) get/put using a hash map plus a doubly linked list.",
  [(E,0.85,DP),(S,0.88,DP),(F,0.65,WK)])
n("dsa-floyd-warshall", "Floyd-Warshall (All-Pairs Shortest Paths)", "dsa", "graphs",
  "DP-based algorithm computing shortest paths between every pair of vertices, handling negative edges without negative cycles.",
  [(E,0.60,WK),(S,0.72,WK),(F,0.62,WK)])
n("dsa-a-star", "A* Search", "dsa", "graphs",
  "Heuristic-guided shortest-path search combining Dijkstra's algorithm with an admissible heuristic.",
  [(R,0.55,WK),(E,0.60,WK)])
n("dsa-scc", "Strongly Connected Components", "dsa", "graphs",
  "Tarjan's and Kosaraju's algorithms for finding maximal strongly connected subgraphs in a directed graph.",
  [(E,0.58,WK),(S,0.52,AW)])
n("dsa-cycle-detection", "Cycle Detection in Graphs", "dsa", "graphs",
  "Detecting cycles in directed graphs via DFS coloring and in undirected graphs via union-find.",
  [(E,0.65,WK),(S,0.62,WK),(F,0.55,WK)])
n("dsa-flow-matching", "Network Flow & Bipartite Matching", "dsa", "graphs",
  "Max-flow/min-cut via Ford-Fulkerson/Edmonds-Karp and bipartite matching via augmenting paths.",
  [(E,0.55,WK),(F,0.60,WK)])
n("dsa-binary-search-on-answer", "Binary Search on the Answer", "dsa", "patterns",
  "Binary searching over a monotonic answer space (e.g. minimize-the-maximum or capacity-feasibility problems) rather than a sorted array.",
  [(E,0.78,WK),(S,0.75,WK),(F,0.68,WK)])
n("dsa-np-completeness", "NP-Completeness & Reductions", "dsa", "complexity",
  "Recognizing NP-hard/NP-complete problems and constructing polynomial-time reductions to argue intractability.",
  [(R,0.55,WK),(E,0.62,WK),(S,0.58,WK),(F,0.55,WK)])
n("dsa-recurrence-relations", "Recurrence Relations & Master Theorem", "dsa", "complexity",
  "Solving divide-and-conquer recurrences with the Master theorem and recursion-tree/substitution methods.",
  [(R,0.50,AW),(E,0.68,WK),(S,0.65,WK),(F,0.72,WK)])
n("dsa-dp-trees", "Dynamic Programming on Trees", "dsa", "dynamic-programming",
  "DP over tree structures that combines child-subtree states at each node, e.g. tree diameter or maximum independent set.",
  [(E,0.70,WK),(S,0.62,WK),(F,0.58,WK)])
n("dsa-bitmask-dp", "Bitmask Dynamic Programming", "dsa", "dynamic-programming",
  "Encoding subsets as bitmasks to enable DP over combinatorial state spaces, e.g. TSP or assignment problems.",
  [(E,0.62,WK),(S,0.55,AW),(F,0.68,WK)])
n("dsa-interval-dp", "Interval & Matrix-Chain DP", "dsa", "dynamic-programming",
  "DP over contiguous subranges built up from smaller intervals, e.g. matrix-chain multiplication or burst balloons.",
  [(E,0.65,WK),(S,0.58,WK),(F,0.62,WK)])
n("dsa-quickselect", "Quickselect & Order Statistics", "dsa", "algorithms",
  "Selecting the k-th smallest/largest element in expected linear time via partition-based selection.",
  [(E,0.75,WK),(S,0.72,WK),(F,0.70,WK)])
n("dsa-matrix-traversal", "Matrix/Grid Traversal", "dsa", "patterns",
  "Traversing 2D grids as implicit graphs for flood fill, connected-components, and shortest-path-on-grid problems.",
  [(E,0.78,WK),(S,0.75,WK),(F,0.55,WK)])

e("dsa-lru-cache","dsa-hashing",1.0)
e("dsa-lru-cache","dsa-linked-lists",1.0)
e("dsa-floyd-warshall","dsa-shortest-paths",0.7)
e("dsa-floyd-warshall","dsa-dynamic-programming",0.4)
e("dsa-a-star","dsa-shortest-paths",1.0)
e("dsa-a-star","dsa-heaps",0.4)
e("dsa-scc","dsa-bfs-dfs",1.0)
e("dsa-cycle-detection","dsa-bfs-dfs",0.7)
e("dsa-cycle-detection","dsa-union-find",0.7)
e("dsa-flow-matching","dsa-bfs-dfs",1.0)
e("dsa-flow-matching","dsa-graphs",0.4)
e("dsa-binary-search-on-answer","dsa-binary-search",1.0)
e("dsa-np-completeness","dsa-big-o",0.4)
e("dsa-recurrence-relations","dsa-big-o",0.7)
e("dsa-recurrence-relations","dsa-recursion-backtracking",0.4)
e("dsa-dp-trees","dsa-trees",0.7)
e("dsa-dp-trees","dsa-dynamic-programming",1.0)
e("dsa-bitmask-dp","dsa-dynamic-programming",1.0)
e("dsa-bitmask-dp","dsa-bit-manipulation",0.7)
e("dsa-interval-dp","dsa-dp-2d",0.7)
e("dsa-quickselect","dsa-sorting",0.7)
e("dsa-matrix-traversal","dsa-bfs-dfs",1.0)

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
n("cs-cpu-scheduling", "CPU Scheduling & Context Switching", "cs-fundamentals", "os",
  "FCFS, SJF, round robin, and priority scheduling algorithms, plus what happens during a context switch.",
  [(E,0.65,WK),(S,0.82,DP)])
n("cs-file-systems", "File Systems", "cs-fundamentals", "os",
  "Inodes, directories, blocks, and how a file system organizes data on disk.",
  [(E,0.55,AW),(S,0.75,WK)])
n("cs-system-calls", "System Calls & Kernel Mode", "cs-fundamentals", "os",
  "User mode vs kernel mode, the syscall interface, and how a process requests OS services.",
  [(E,0.55,AW),(S,0.72,WK)])
n("cs-interrupts", "Interrupts & Interrupt Handling", "cs-fundamentals", "os",
  "Hardware/software interrupts, interrupt handlers, and how the CPU responds to asynchronous events.",
  [(E,0.45,AW),(S,0.65,WK)])
n("cs-deadlock", "Deadlock Detection & Prevention", "cs-fundamentals", "os",
  "The Coffman conditions, deadlock avoidance/prevention strategies, and detection algorithms.",
  [(E,0.60,WK),(S,0.82,DP)])
n("cs-memory-allocation", "Memory Allocation", "cs-fundamentals", "systems",
  "Heap allocation strategies, malloc/free mechanics, and internal/external fragmentation.",
  [(E,0.65,WK),(S,0.80,DP)])
n("cs-mutexes-semaphores", "Mutexes & Semaphores", "cs-fundamentals", "concurrency",
  "Mutual exclusion locks and counting/binary semaphores as synchronization primitives.",
  [(E,0.70,WK),(S,0.85,DP)])
n("cs-atomic-operations", "Atomic Operations & Memory Ordering", "cs-fundamentals", "concurrency",
  "Compare-and-swap, atomic instructions, and memory ordering/visibility across threads.",
  [(E,0.62,WK),(S,0.75,DP)])
n("cs-thread-pools", "Thread Pools & Worker Models", "cs-fundamentals", "concurrency",
  "Reusing a bounded set of worker threads to execute queued tasks instead of spawning per task.",
  [(E,0.70,WK),(S,0.78,WK)])
n("cs-async-io-event-loop", "Async I/O & Event Loops", "cs-fundamentals", "concurrency",
  "Non-blocking I/O, event loops, and single-threaded concurrency via callbacks/coroutines.",
  [(E,0.75,WK),(S,0.72,WK)])
n("cs-producer-consumer", "Producer-Consumer Pattern", "cs-fundamentals", "concurrency",
  "Coordinating producer and consumer threads through a bounded shared buffer/queue.",
  [(E,0.60,WK),(S,0.75,WK)])
n("cs-osi-tcpip-layers", "OSI & TCP/IP Layering Models", "cs-fundamentals", "networks",
  "The layered models for network communication and what each layer is responsible for.",
  [(E,0.50,AW),(S,0.68,WK)])
n("cs-tcp-udp", "TCP vs UDP", "cs-fundamentals", "networks",
  "Connection-oriented reliable delivery vs connectionless best-effort delivery, and when to use each.",
  [(E,0.62,WK),(S,0.80,DP)])
n("cs-tcp-handshake-flow-control", "TCP Handshake & Flow Control", "cs-fundamentals", "networks",
  "The three-way handshake, sliding window flow control, and basic congestion control.",
  [(E,0.50,AW),(S,0.72,WK)])
n("cs-http-https", "HTTP & HTTPS", "cs-fundamentals", "networks",
  "HTTP methods, status codes, statelessness/headers, and how HTTPS layers encryption over HTTP.",
  [(E,0.68,WK),(S,0.82,DP),(P,0.42,AW)])
n("cs-tls", "TLS & Encryption in Transit", "cs-fundamentals", "networks",
  "The TLS handshake, certificates, and symmetric vs asymmetric encryption in securing a connection.",
  [(E,0.48,AW),(S,0.65,WK)])
n("cs-dns", "DNS Resolution", "cs-fundamentals", "networks",
  "The domain name hierarchy, record types, and how a hostname resolves to an IP address.",
  [(E,0.45,AW),(S,0.62,WK)])
n("cs-sockets", "Sockets & Socket Programming", "cs-fundamentals", "networks",
  "The socket API as the OS-level abstraction for establishing and using network connections.",
  [(E,0.50,AW),(S,0.70,WK)])
n("cs-websockets", "WebSockets", "cs-fundamentals", "networks",
  "Upgrading an HTTP connection to a persistent, full-duplex channel for real-time communication.",
  [(E,0.55,AW),(S,0.65,WK)])
n("cs-relational-modeling-normalization", "Relational Modeling & Normalization", "cs-fundamentals", "data",
  "Entity-relationship modeling and normal forms (1NF-3NF), plus denormalization tradeoffs.",
  [(E,0.65,WK),(S,0.78,WK),(P,0.42,AW)])
n("cs-indexing-btrees", "Indexing & B-Trees", "cs-fundamentals", "data",
  "How database indexes speed up lookups, and the B-tree/B+-tree structures that back them.",
  [(E,0.72,WK),(S,0.82,DP)])
n("cs-query-optimization", "Query Planning & Optimization", "cs-fundamentals", "data",
  "How a query planner chooses an execution plan, and cost-based optimization basics.",
  [(E,0.60,WK),(S,0.72,WK)])
n("cs-isolation-levels-mvcc", "Transaction Isolation Levels & MVCC", "cs-fundamentals", "data",
  "Read uncommitted/committed, repeatable read, and serializable isolation, plus MVCC mechanics.",
  [(E,0.65,WK),(S,0.78,DP)])
n("cs-database-locking", "Database Locking Mechanisms", "cs-fundamentals", "data",
  "Row vs table locks, two-phase locking, and lock granularity tradeoffs.",
  [(E,0.58,WK),(S,0.75,DP)])
n("cs-nosql-data-models", "NoSQL Data Models", "cs-fundamentals", "data",
  "Key-value, document, and columnar stores, and how their tradeoffs differ from the relational model.",
  [(E,0.70,WK),(S,0.68,WK),(P,0.40,AW)])
n("cs-compilation-interpretation", "Compilation vs Interpretation", "cs-fundamentals", "systems",
  "How compiled and interpreted languages execute code differently, and where JIT compilation fits.",
  [(E,0.55,AW),(S,0.68,WK)])
n("cs-garbage-collection", "Memory Management & Garbage Collection", "cs-fundamentals", "systems",
  "Manual memory management vs automatic garbage collection, and common GC strategies.",
  [(E,0.62,WK),(S,0.70,WK)])

e("cs-processes-threads","cs-memory-model",0.7)
e("cs-concurrency","cs-processes-threads",1.0)
e("cs-caching","cs-memory-model",0.7)
e("cs-os-memory-mgmt","cs-memory-model",1.0)
e("cs-sql","cs-databases",1.0)
e("cs-networking","cs-processes-threads",0.4)
e("cs-cpu-scheduling","cs-processes-threads",0.7)
e("cs-file-systems","cs-memory-model",0.4)
e("cs-system-calls","cs-processes-threads",0.7)
e("cs-interrupts","cs-system-calls",0.7)
e("cs-deadlock","cs-concurrency",1.0)
e("cs-deadlock","cs-cpu-scheduling",0.4)
e("cs-memory-allocation","cs-memory-model",0.7)
e("cs-mutexes-semaphores","cs-concurrency",1.0)
e("cs-atomic-operations","cs-mutexes-semaphores",0.7)
e("cs-thread-pools","cs-processes-threads",0.7)
e("cs-thread-pools","cs-mutexes-semaphores",0.4)
e("cs-async-io-event-loop","cs-processes-threads",0.7)
e("cs-producer-consumer","cs-mutexes-semaphores",1.0)
e("cs-networking","cs-osi-tcpip-layers",0.4)
e("cs-tcp-udp","cs-networking",0.7)
e("cs-tcp-handshake-flow-control","cs-tcp-udp",1.0)
e("cs-http-https","cs-tcp-udp",0.7)
e("cs-tls","cs-http-https",0.7)
e("cs-dns","cs-networking",0.4)
e("cs-sockets","cs-tcp-udp",0.7)
e("cs-websockets","cs-http-https",0.7)
e("cs-relational-modeling-normalization","cs-databases",0.7)
e("cs-indexing-btrees","cs-databases",1.0)
e("cs-query-optimization","cs-indexing-btrees",0.7)
e("cs-query-optimization","cs-sql",0.4)
e("cs-isolation-levels-mvcc","cs-databases",1.0)
e("cs-database-locking","cs-isolation-levels-mvcc",0.7)
e("cs-database-locking","cs-concurrency",0.4)
e("cs-nosql-data-models","cs-databases",0.7)
e("cs-garbage-collection","cs-memory-allocation",0.7)

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
n("sysd-caching-strategies", "Caching Strategies", "system-design", "components",
  "Cache-aside, write-through, and write-back/write-behind policies and their consistency tradeoffs.",
  [(E,0.72,DP),(S,0.75,DP)])
n("sysd-cache-eviction-invalidation", "Cache Eviction & Invalidation", "system-design", "components",
  "Eviction policies (LRU/LFU/TTL) and invalidation approaches (write-invalidate, TTL expiry, event-driven) for distributed caches.",
  [(E,0.68,WK),(S,0.72,WK)])
n("sysd-cdn", "Content Delivery Networks", "system-design", "components",
  "Edge PoPs, geo-routing, and accelerating static vs dynamic content delivery.",
  [(E,0.62,WK),(S,0.65,WK),(P,0.50,AW)])
n("sysd-sharding-partitioning", "Database Sharding & Partitioning", "system-design", "data",
  "Hash-based, range-based, and directory-based partitioning strategies; hot shards and rebalancing.",
  [(E,0.80,DP),(S,0.82,DP),(P,0.50,AW)])
n("sysd-replication-read-replicas", "Replication & Read Replicas", "system-design", "data",
  "Leader-follower replication, synchronous vs asynchronous replication, read replicas, replication lag, and failover.",
  [(E,0.78,DP),(S,0.80,DP)])
n("sysd-consistency-models", "Consistency Models", "system-design", "principles",
  "The spectrum of distributed consistency guarantees — linearizable, sequential, causal, and eventual — and choosing among them.",
  [(E,0.72,DP),(S,0.75,DP),(R,0.50,AW)])
n("sysd-eventual-consistency", "Eventual Consistency", "system-design", "principles",
  "Eventual consistency in practice: conflict resolution (last-write-wins, vector clocks), read-your-writes, and monotonic reads.",
  [(E,0.68,WK),(S,0.72,WK),(R,0.45,AW)])
n("sysd-event-driven-architecture", "Event-Driven Architecture", "system-design", "architecture",
  "Choreography vs orchestration, event sourcing basics, and decoupling producers from consumers via events.",
  [(E,0.72,DP),(S,0.75,DP)])
n("sysd-rate-limiting", "Rate Limiting", "system-design", "interfaces",
  "Token bucket, leaky bucket, and sliding-window algorithms for limiting request rates, including distributed enforcement.",
  [(E,0.72,DP),(S,0.78,DP)])
n("sysd-idempotency", "Idempotency", "system-design", "interfaces",
  "Designing idempotent APIs and operations so retries and duplicate requests are safe to replay.",
  [(E,0.70,WK),(S,0.75,WK)])
n("sysd-rest-graphql-grpc", "REST vs GraphQL vs gRPC", "system-design", "interfaces",
  "Tradeoffs among REST, GraphQL, and gRPC for API design: latency, schema strictness, over/under-fetching, and streaming.",
  [(E,0.68,WK),(S,0.72,WK),(P,0.50,AW)])
n("sysd-microservices-vs-monolith", "Microservices vs Monolith", "system-design", "architecture",
  "Tradeoffs between monolithic and microservice architectures: coupling, independent deployability, and operational overhead.",
  [(E,0.75,DP),(S,0.80,DP),(P,0.60,WK)])
n("sysd-service-discovery", "Service Discovery", "system-design", "architecture",
  "How services locate each other at runtime: client-side vs server-side discovery and service registries.",
  [(E,0.62,WK),(S,0.68,WK)])
n("sysd-distributed-transactions-sagas", "Distributed Transactions & Sagas", "system-design", "architecture",
  "Coordinating writes across services: two-phase commit, the saga pattern (choreography/orchestration), and compensating transactions.",
  [(E,0.72,DP),(S,0.75,DP)])
n("sysd-consensus-algorithms", "Consensus Algorithms (Raft/Paxos)", "system-design", "architecture",
  "Why distributed systems need agreement protocols, at an awareness level: leader-based replication and how Raft/Paxos reach consensus.",
  [(E,0.55,AW),(S,0.55,AW),(R,0.45,AW)])
n("sysd-blob-object-storage", "Blob & Object Storage", "system-design", "data",
  "Object storage systems (S3-like) for unstructured data: durability, storage tiers, and use cases vs block/file storage.",
  [(E,0.62,WK),(S,0.65,WK)])
n("sysd-search-indexing-architecture", "Search Indexing Architecture", "system-design", "data",
  "Architecture of large-scale search: inverted indices, index sharding, and serving queries at scale.",
  [(E,0.65,WK),(R,0.50,AW)])
n("sysd-capacity-estimation", "Capacity Estimation", "system-design", "estimation",
  "Back-of-the-envelope estimation of QPS, storage, and bandwidth for system design interviews.",
  [(E,0.80,DP),(S,0.82,DP)])
n("sysd-latency-slas", "Latency Budgets & SLAs", "system-design", "reliability",
  "Latency budgets, percentile latency (p50/p95/p99), and service-level agreements/objectives.",
  [(E,0.72,DP),(S,0.75,DP),(P,0.55,WK)])
n("sysd-availability-redundancy", "Availability & Redundancy", "system-design", "reliability",
  "Designing for availability: redundancy across zones/regions, failover, and reasoning about uptime ('nines').",
  [(E,0.72,DP),(S,0.78,DP)])
n("sysd-failure-modes-graceful-degradation", "Failure Modes & Graceful Degradation", "system-design", "reliability",
  "Anticipating partial failures and designing graceful degradation instead of full outages.",
  [(E,0.70,WK),(S,0.75,WK)])
n("sysd-circuit-breakers-retries", "Circuit Breakers & Retries", "system-design", "reliability",
  "The circuit breaker pattern and retries with exponential backoff and jitter to prevent cascading failures.",
  [(E,0.72,WK),(S,0.75,WK)])
n("sysd-observability", "Observability", "system-design", "reliability",
  "Logging, metrics, and distributed tracing for understanding system behavior in production.",
  [(E,0.68,WK),(S,0.72,WK)])
n("sysd-deployment-strategies", "Deployment Strategies", "system-design", "deployment",
  "Blue-green and canary deployments, rolling updates, and feature flags for safe rollout.",
  [(E,0.62,WK),(S,0.68,WK),(P,0.50,AW)])
n("sysd-design-url-shortener", "Design: URL Shortener", "system-design", "design-exercises",
  "Classic design exercise: URL shortener — encoding schemes, storage, and the redirect path at scale.",
  [(E,0.75,DP),(S,0.75,DP)])
n("sysd-design-news-feed", "Design: News Feed", "system-design", "design-exercises",
  "Classic design exercise: news feed — fan-out on write vs read, ranking, and storing feed items at scale.",
  [(E,0.72,DP),(S,0.70,DP),(P,0.55,WK)])
n("sysd-design-chat-system", "Design: Chat System", "system-design", "design-exercises",
  "Classic design exercise: real-time chat/messaging — delivery guarantees, connection management, and message storage.",
  [(E,0.70,DP),(S,0.70,DP)])
n("sysd-design-notification-system", "Design: Notification System", "system-design", "design-exercises",
  "Classic design exercise: notification system — multi-channel delivery, fan-out, retries, and deduplication.",
  [(E,0.65,WK),(S,0.65,WK)])
n("sysd-recommendation-system-design", "Recommendation System Architecture", "system-design", "ml-systems",
  "Architecture of a recommendation system: candidate generation, ranking, retrieval, and serving at scale.",
  [(E,0.75,DP),(R,0.55,AW)])

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

e("sysd-caching-strategies","sysd-caching-systems",0.7)
e("sysd-caching-strategies","cs-caching",0.4)
e("sysd-cache-eviction-invalidation","sysd-caching-systems",0.7)
e("sysd-cache-eviction-invalidation","dsa-lru-cache",0.4)
e("sysd-cdn","sysd-caching-systems",0.7)
e("sysd-cdn","cs-dns",0.4)
e("sysd-sharding-partitioning","sysd-db-scaling",0.7)
e("sysd-sharding-partitioning","cs-databases",0.7)
e("sysd-replication-read-replicas","sysd-db-scaling",0.7)
e("sysd-replication-read-replicas","cs-databases",0.7)
e("sysd-consistency-models","cs-isolation-levels-mvcc",0.4)
e("sysd-eventual-consistency","sysd-consistency-models",1.0)
e("sysd-eventual-consistency","sysd-cap-theorem",0.7)
e("sysd-event-driven-architecture","sysd-message-queues",0.7)
e("sysd-rate-limiting","sysd-api-design",0.4)
e("sysd-idempotency","sysd-api-design",0.7)
e("sysd-rest-graphql-grpc","sysd-api-design",0.7)
e("sysd-rest-graphql-grpc","cs-http-https",0.4)
e("sysd-microservices-vs-monolith","sysd-scalability",0.4)
e("sysd-service-discovery","sysd-microservices-vs-monolith",0.7)
e("sysd-service-discovery","cs-dns",0.4)
e("sysd-distributed-transactions-sagas","sysd-microservices-vs-monolith",0.7)
e("sysd-distributed-transactions-sagas","cs-isolation-levels-mvcc",0.4)
e("sysd-consensus-algorithms","sysd-replication-read-replicas",0.4)
e("sysd-blob-object-storage","sysd-scalability",0.4)
e("sysd-search-indexing-architecture","sysd-sharding-partitioning",0.4)
e("sysd-search-indexing-architecture","dsa-hashing",0.4)
e("sysd-capacity-estimation","sysd-scalability",0.4)
e("sysd-latency-slas","sysd-scalability",0.4)
e("sysd-availability-redundancy","sysd-replication-read-replicas",0.4)
e("sysd-failure-modes-graceful-degradation","sysd-availability-redundancy",0.7)
e("sysd-circuit-breakers-retries","sysd-failure-modes-graceful-degradation",0.7)
e("sysd-observability","sysd-scalability",0.4)
e("sysd-deployment-strategies","sysd-microservices-vs-monolith",0.4)
e("sysd-design-url-shortener","sysd-capacity-estimation",0.7)
e("sysd-design-url-shortener","sysd-db-scaling",0.7)
e("sysd-design-url-shortener","sysd-caching-systems",0.4)
e("sysd-design-news-feed","sysd-capacity-estimation",0.7)
e("sysd-design-news-feed","sysd-caching-systems",0.4)
e("sysd-design-news-feed","sysd-message-queues",0.4)
e("sysd-design-chat-system","cs-websockets",0.7)
e("sysd-design-chat-system","sysd-message-queues",0.4)
e("sysd-design-chat-system","sysd-capacity-estimation",0.4)
e("sysd-design-notification-system","sysd-message-queues",0.7)
e("sysd-design-notification-system","sysd-circuit-breakers-retries",0.4)
e("sysd-recommendation-system-design","sysd-ml-system-design",0.7)
e("sysd-recommendation-system-design","sysd-search-indexing-architecture",0.4)

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
n("beh-story-selection", "Story Selection & Portfolio Building", "behavioral", "preparation",
  "Curating a portfolio of 6-8 stories that map to common behavioral themes and can be adapted across question types.",
  [(R,0.68,WK),(E,0.72,WK),(D,0.70,WK),(S,0.72,WK),(P,0.85,DP),(F,0.68,WK)])
n("beh-manager-disagreement", "Disagreeing with a Manager", "behavioral", "collaboration",
  "Describing a professional disagreement with a manager or senior stakeholder and how it was resolved without damaging the relationship.",
  [(R,0.65,WK),(E,0.72,WK),(D,0.70,WK),(S,0.72,WK),(P,0.82,DP),(F,0.75,WK)])
n("beh-feedback-receiving", "Receiving and Acting on Feedback", "behavioral", "growth",
  "Describing how critical feedback was received, internalized, and acted upon to improve performance.",
  [(R,0.65,WK),(E,0.70,WK),(D,0.68,WK),(S,0.72,WK),(P,0.80,DP),(F,0.70,WK)])
n("beh-feedback-giving", "Giving Constructive Feedback", "behavioral", "growth",
  "Delivering critical feedback to a peer or report constructively while preserving trust.",
  [(R,0.60,WK),(E,0.65,WK),(D,0.65,WK),(S,0.68,WK),(P,0.78,DP),(F,0.62,WK)])
n("beh-influence-stakeholders", "Influencing Without Direct Authority", "behavioral", "collaboration",
  "Persuading peers or cross-functional stakeholders to adopt an approach without formal reporting authority.",
  [(R,0.62,WK),(E,0.70,WK),(D,0.65,WK),(S,0.72,WK),(P,0.88,DP),(F,0.65,WK)])
n("beh-ambiguity", "Navigating Ambiguity", "behavioral", "execution",
  "Making progress and decisions when requirements, goals, or ownership are unclear or incomplete.",
  [(R,0.68,WK),(E,0.75,WK),(D,0.70,WK),(S,0.72,WK),(P,0.88,DP),(F,0.65,WK)])
n("beh-prioritization-pressure", "Prioritizing Under Deadline Pressure", "behavioral", "execution",
  "Choosing what to work on and what to defer when multiple deadlines or requests compete for limited time.",
  [(R,0.62,WK),(E,0.72,WK),(D,0.68,WK),(S,0.72,WK),(P,0.85,DP),(F,0.70,WK)])
n("beh-missed-deadline", "Handling a Missed Deadline", "behavioral", "execution",
  "Explaining a deadline that was missed, the root cause, communication with stakeholders, and the recovery plan.",
  [(R,0.55,WK),(E,0.68,WK),(D,0.65,WK),(S,0.68,WK),(P,0.78,DP),(F,0.65,WK)])
n("beh-teamwork", "Teamwork & Collaboration", "behavioral", "collaboration",
  "Contributing effectively as part of a team, sharing credit, and adapting to teammates' working styles.",
  [(R,0.60,WK),(E,0.70,WK),(D,0.68,WK),(S,0.75,WK),(P,0.78,DP),(F,0.65,WK)])
n("beh-cross-functional", "Cross-Functional Communication", "behavioral", "communication",
  "Coordinating with people in different functions (e.g. design, sales, legal) who have different priorities and vocabularies.",
  [(R,0.55,WK),(E,0.65,WK),(D,0.62,WK),(S,0.65,WK),(P,0.90,DP),(F,0.62,WK)])
n("beh-learning-new-tech", "Learning a New Technology Quickly", "behavioral", "growth",
  "Ramping up on an unfamiliar tool, language, or domain under time pressure and applying it productively.",
  [(R,0.55,WK),(E,0.72,WK),(D,0.62,WK),(S,0.75,WK),(P,0.55,AW),(F,0.58,WK)])
n("beh-strengths-weaknesses", "Strengths & Weaknesses", "behavioral", "preparation",
  "Articulating genuine strengths and a real weakness with evidence of self-awareness and active improvement.",
  [(R,0.60,WK),(E,0.62,WK),(D,0.62,WK),(S,0.65,WK),(P,0.70,WK),(F,0.65,WK)])
n("beh-interviewer-questions", "Questions to Ask the Interviewer", "behavioral", "preparation",
  "Preparing thoughtful, role-specific questions that signal genuine research and engagement.",
  [(R,0.50,AW),(E,0.55,AW),(D,0.55,AW),(S,0.55,AW),(P,0.65,WK),(F,0.55,AW)])
n("beh-offer-negotiation", "Offer & Compensation Conversations", "behavioral", "negotiation",
  "Discussing compensation expectations and negotiating an offer professionally.",
  [(R,0.45,AW),(E,0.48,AW),(D,0.48,AW),(S,0.48,AW),(P,0.52,AW),(F,0.55,AW)])
n("beh-remote-collaboration", "Remote & Async Collaboration", "behavioral", "collaboration",
  "Working effectively with distributed teammates across time zones using asynchronous communication norms.",
  [(R,0.55,WK),(E,0.62,WK),(D,0.58,WK),(S,0.60,WK),(P,0.65,WK),(F,0.50,AW)])
n("beh-mentoring", "Mentoring Others", "behavioral", "growth",
  "Supporting a less experienced colleague's growth through guidance, work review, and encouragement.",
  [(R,0.50,AW),(E,0.58,WK),(D,0.55,AW),(S,0.58,WK),(P,0.55,AW),(F,0.48,AW)])
n("beh-ethical-dilemma", "Ethical Dilemmas & Pushing Back", "behavioral", "judgment",
  "Recognizing an ethical, compliance, or integrity concern and pushing back or escalating appropriately.",
  [(R,0.60,WK),(E,0.62,WK),(D,0.65,WK),(S,0.62,WK),(P,0.68,WK),(F,0.92,DP)])
n("beh-difficult-constraints", "Working Within Difficult Constraints", "behavioral", "execution",
  "Delivering results despite limited resources, unclear authority, legacy systems, or organizational friction.",
  [(R,0.55,WK),(E,0.65,WK),(D,0.60,WK),(S,0.65,WK),(P,0.68,WK),(F,0.60,WK)])
n("beh-technical-tradeoff", "Explaining a Technical Tradeoff Decision", "behavioral", "communication",
  "Justifying an engineering or modeling decision by walking through the tradeoffs considered and why one was chosen.",
  [(R,0.75,DP),(E,0.85,DP),(D,0.78,DP),(S,0.82,DP),(P,0.55,WK),(F,0.60,WK)])
n("beh-difficult-stakeholder", "Managing a Difficult Stakeholder or Client", "behavioral", "collaboration",
  "Handling a demanding, unresponsive, or misaligned stakeholder while protecting scope, timeline, or quality.",
  [(R,0.50,AW),(E,0.60,WK),(D,0.60,WK),(S,0.58,WK),(P,0.88,DP),(F,0.72,WK)])

e("beh-conflict","beh-star-method",0.7)
e("beh-leadership","beh-star-method",0.7)
e("beh-failure","beh-star-method",0.7)
e("beh-story-selection","beh-star-method",0.7)
e("beh-manager-disagreement","beh-star-method",0.7)
e("beh-manager-disagreement","beh-conflict",0.4)
e("beh-feedback-receiving","beh-star-method",0.7)
e("beh-feedback-giving","beh-star-method",0.7)
e("beh-influence-stakeholders","beh-leadership",0.7)
e("beh-influence-stakeholders","beh-communication",0.4)
e("beh-ambiguity","beh-star-method",0.7)
e("beh-prioritization-pressure","beh-star-method",0.7)
e("beh-missed-deadline","beh-failure",0.7)
e("beh-missed-deadline","beh-prioritization-pressure",0.4)
e("beh-teamwork","beh-star-method",0.7)
e("beh-cross-functional","beh-communication",0.7)
e("beh-cross-functional","beh-teamwork",0.4)
e("beh-learning-new-tech","beh-star-method",0.7)
e("beh-interviewer-questions","beh-why-company",0.4)
e("beh-remote-collaboration","beh-teamwork",0.4)
e("beh-mentoring","beh-feedback-giving",0.7)
e("beh-ethical-dilemma","beh-star-method",0.7)
e("beh-difficult-constraints","beh-ambiguity",0.4)
e("beh-technical-tradeoff","beh-communication",0.7)
e("beh-difficult-stakeholder","beh-cross-functional",0.7)
e("beh-difficult-stakeholder","beh-conflict",0.4)

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
n("ml-cross-validation", "Cross-Validation Strategies", "classical-ml", "methodology",
  "k-fold, stratified, leave-one-out, and time-series-aware cross-validation for reliable performance estimation.",
  [(R,0.65,WK),(E,0.80,DP),(D,0.85,DP),(F,0.55,WK)])
n("ml-data-leakage", "Data Leakage", "classical-ml", "methodology",
  "Target leakage, temporal leakage, and preprocessing leakage that inflate offline performance estimates.",
  [(E,0.82,DP),(D,0.85,DP),(R,0.60,WK)])
n("ml-gradient-boosting", "Gradient Boosting Machines", "classical-ml", "models",
  "Sequentially fitting weak learners to residual errors; XGBoost/LightGBM regularization and tree-growth strategies.",
  [(R,0.72,DP),(E,0.85,DP),(D,0.90,DP),(F,0.62,WK)])
n("ml-ensemble-stacking", "Stacking & Blending", "classical-ml", "models",
  "Combining heterogeneous base models with a meta-learner trained on out-of-fold predictions.",
  [(E,0.68,WK),(D,0.72,WK),(R,0.55,AW)])
n("ml-multiclass-strategies", "Multi-Class Classification Strategies", "classical-ml", "models",
  "One-vs-rest, one-vs-one, and softmax/multinomial extensions of binary classifiers.",
  [(E,0.65,WK),(D,0.70,WK),(R,0.55,AW)])
n("ml-hierarchical-clustering", "Hierarchical Clustering", "classical-ml", "unsupervised",
  "Agglomerative and divisive clustering, linkage criteria, and dendrograms.",
  [(D,0.72,WK),(E,0.62,WK),(R,0.55,AW)])
n("ml-dbscan", "DBSCAN", "classical-ml", "unsupervised",
  "Density-based clustering via core points, eps, and minPts; robustness to non-spherical clusters and noise.",
  [(D,0.68,WK),(E,0.60,WK)])
n("ml-gmm-em", "Gaussian Mixture Models & EM", "classical-ml", "unsupervised",
  "Soft clustering as a mixture of Gaussians fit via the Expectation-Maximization algorithm.",
  [(R,0.72,DP),(D,0.75,DP),(E,0.65,WK)])
n("ml-tsne-umap", "t-SNE & UMAP", "classical-ml", "unsupervised",
  "Nonlinear dimensionality reduction for visualization, and its tradeoffs versus linear methods like PCA.",
  [(R,0.62,WK),(D,0.70,WK),(E,0.55,AW)])
n("ml-anomaly-detection", "Anomaly Detection", "classical-ml", "unsupervised",
  "Isolation forests, one-class SVM, and statistical outlier detection for identifying rare or abnormal instances.",
  [(E,0.68,WK),(D,0.72,WK),(F,0.55,AW)])
n("ml-recommender-systems", "Recommender Systems", "classical-ml", "applications",
  "Collaborative filtering, content-based filtering, and matrix factorization for personalized recommendations.",
  [(E,0.65,WK),(D,0.68,WK)])
n("ml-semi-supervised", "Semi-Supervised & Self-Training", "classical-ml", "methodology",
  "Leveraging unlabeled data via self-training, pseudo-labeling, and label propagation.",
  [(R,0.58,WK),(E,0.58,AW),(D,0.55,AW)])
n("ml-feature-scaling", "Feature Scaling & Normalization", "classical-ml", "methodology",
  "Standardization, min-max scaling, and robust scaling, and why distance- and gradient-based models require them.",
  [(E,0.72,WK),(D,0.75,WK),(R,0.50,AW)])
n("ml-categorical-encoding", "Categorical Encoding", "classical-ml", "methodology",
  "One-hot, ordinal, target, and frequency encoding, and handling high-cardinality categorical features.",
  [(E,0.75,WK),(D,0.75,WK)])
n("ml-feature-selection", "Feature Selection", "classical-ml", "methodology",
  "Filter, wrapper, and embedded methods for selecting predictive features and reducing dimensionality.",
  [(E,0.70,WK),(D,0.72,WK)])
n("ml-hyperparameter-search", "Hyperparameter Search Strategies", "classical-ml", "methodology",
  "Grid search, random search, and Bayesian optimization for tuning model hyperparameters.",
  [(E,0.70,WK),(D,0.70,WK)])
n("ml-regression-metrics", "Regression Evaluation Metrics", "classical-ml", "evaluation",
  "RMSE, MAE, R-squared, and adjusted R-squared for evaluating regression models.",
  [(E,0.75,WK),(D,0.82,DP),(R,0.55,AW),(F,0.62,WK)])
n("ml-calibration", "Probability Calibration", "classical-ml", "evaluation",
  "Platt scaling, isotonic regression, and calibration curves for aligning predicted probabilities with observed frequencies.",
  [(E,0.68,WK),(D,0.70,WK),(R,0.55,AW)])
n("ml-learning-curves", "Learning Curves", "classical-ml", "evaluation",
  "Diagnosing underfitting vs. overfitting by plotting error against training set size or model complexity.",
  [(E,0.68,WK),(D,0.72,WK),(R,0.55,AW)])
n("ml-ranking-metrics", "Ranking Metrics", "classical-ml", "evaluation",
  "NDCG, MAP, and MRR for evaluating ranked output quality.",
  [(E,0.62,WK),(D,0.65,WK)])
n("ml-interpretability", "Model Interpretability", "classical-ml", "evaluation",
  "SHAP values, LIME, and feature importance for explaining individual predictions and global model behavior.",
  [(E,0.72,WK),(D,0.75,WK),(R,0.55,AW),(F,0.58,WK)])

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
e("ml-cross-validation","ml-train-test-split",0.7)
e("ml-data-leakage","ml-train-test-split",0.7)
e("ml-gradient-boosting","ml-decision-trees",1.0)
e("ml-gradient-boosting","ml-ensembles",0.7)
e("ml-gradient-boosting","opt-gradient-descent",0.7)
e("ml-ensemble-stacking","ml-ensembles",0.7)
e("ml-ensemble-stacking","ml-cross-validation",0.7)
e("ml-multiclass-strategies","ml-logistic-regression",0.7)
e("ml-hierarchical-clustering","linalg-dot-product",0.4)
e("ml-dbscan","ml-kmeans",0.4)
e("ml-gmm-em","prob-multivariate-normal",0.7)
e("ml-gmm-em","stat-mle",0.7)
e("ml-gmm-em","ml-kmeans",0.4)
e("ml-tsne-umap","ml-pca",0.4)
e("ml-tsne-umap","prob-covariance",0.4)
e("ml-anomaly-detection","ml-decision-trees",0.4)
e("ml-anomaly-detection","ml-svm",0.4)
e("ml-recommender-systems","linalg-svd",0.4)
e("ml-semi-supervised","ml-supervised-unsupervised",0.4)
e("ml-feature-scaling","ml-feature-engineering",0.4)
e("ml-feature-scaling","ml-knn",0.4)
e("ml-categorical-encoding","ml-feature-engineering",0.4)
e("ml-feature-selection","ml-feature-engineering",0.4)
e("ml-feature-selection","ml-overfitting",0.4)
e("ml-hyperparameter-search","ml-cross-validation",0.7)
e("ml-regression-metrics","ml-linear-regression",0.4)
e("ml-calibration","ml-logistic-regression",0.4)
e("ml-calibration","ml-evaluation-metrics",0.4)
e("ml-learning-curves","ml-overfitting",0.7)
e("ml-ranking-metrics","ml-evaluation-metrics",0.4)
e("ml-interpretability","ml-decision-trees",0.4)
e("ml-interpretability","ml-ensembles",0.4)

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
  "Dropout and weight decay as parameter-level regularization for neural networks.",
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

# ---- deep-learning (gap-fill) ----
n("dl-conv-arithmetic", "Convolution Arithmetic & Receptive Field", "deep-learning", "architectures",
  "Computing output dimensions from kernel size, stride, padding, and dilation, and how receptive field grows with network depth.",
  [(R,0.62,WK),(E,0.72,DP),(D,0.45,AW)])
n("dl-cnn-architectures", "Classic CNN Architectures", "deep-learning", "architectures",
  "Landmark vision backbones (VGG, ResNet, Inception/GoogLeNet) and the design choices — depth, skip connections, multi-scale filters — that shaped them.",
  [(R,0.68,DP),(E,0.72,DP)])
n("dl-cross-attention", "Cross-Attention", "deep-learning", "transformers",
  "Attention where queries come from one sequence and keys/values from another, as used in encoder-decoder transformers and conditioning mechanisms.",
  [(R,0.80,DP),(E,0.75,DP)])
n("dl-vision-transformers", "Vision Transformers", "deep-learning", "transformers",
  "Applying the transformer architecture to images via patch embeddings, trading convolutional inductive bias for attention.",
  [(R,0.75,DP),(E,0.68,WK)])
n("dl-curriculum-learning", "Curriculum Learning", "deep-learning", "methodology",
  "Ordering training examples from easy to hard to improve convergence speed and final generalization.",
  [(R,0.62,WK),(E,0.55,AW)])
n("dl-gradient-accumulation", "Gradient Accumulation", "deep-learning", "training",
  "Simulating a larger effective batch size by summing gradients over several micro-batches before an optimizer step, when memory limits batch size.",
  [(R,0.55,AW),(E,0.78,DP)])
n("dl-pruning", "Neural Network Pruning", "deep-learning", "compression",
  "Removing redundant weights, neurons, or channels from a trained network to shrink it and speed up inference with minimal accuracy loss.",
  [(R,0.60,WK),(E,0.75,DP)])
n("dl-data-augmentation", "Data Augmentation", "deep-learning", "training",
  "Synthesizing label-preserving training variations (crops, flips, mixup/cutmix, noise injection) to improve generalization without collecting new data.",
  [(R,0.60,WK),(E,0.78,DP),(D,0.50,AW)])
n("dl-interpretability", "Neural Network Interpretability", "deep-learning", "evaluation",
  "Saliency maps, Grad-CAM, feature visualization, and probing classifiers for inspecting what a trained network has learned.",
  [(R,0.70,DP),(E,0.55,WK)])
n("dl-loss-landscape", "Loss Landscape & Generalization", "deep-learning", "training",
  "Geometry of non-convex neural network loss surfaces — local minima, saddle points, sharp vs. flat minima — and its link to generalization.",
  [(R,0.72,DV),(E,0.48,AW)])
n("dl-double-descent", "Double Descent", "deep-learning", "training",
  "The non-monotonic test-error curve in which increasing model capacity past the interpolation threshold can improve generalization again.",
  [(R,0.68,DP),(E,0.45,AW)])
n("dl-label-smoothing", "Label Smoothing", "deep-learning", "training",
  "Softening one-hot training targets to reduce overconfidence and improve calibration.",
  [(R,0.55,WK),(E,0.60,WK)])
n("dl-nas", "Neural Architecture Search", "deep-learning", "methodology",
  "Automating network architecture design via reinforcement learning, evolutionary search, or differentiable relaxations (e.g. DARTS).",
  [(R,0.58,WK),(E,0.62,WK)])
n("dl-adversarial-robustness", "Adversarial Examples & Robustness", "deep-learning", "evaluation",
  "Small, often imperceptible input perturbations (e.g. FGSM, PGD) that fool trained networks, and adversarial training as a defense.",
  [(R,0.68,DP),(E,0.55,WK)])

e("dl-conv-arithmetic","dl-cnn",1.0)
e("dl-cnn-architectures","dl-cnn",1.0)
e("dl-cnn-architectures","dl-residual-connections",0.7)
e("dl-cross-attention","dl-multihead-attention",1.0)
e("dl-cross-attention","dl-seq2seq",0.4)
e("dl-vision-transformers","dl-transformer-architecture",1.0)
e("dl-vision-transformers","dl-cnn",0.4)
e("dl-curriculum-learning","dl-backprop",0.4)
e("dl-gradient-accumulation","dl-backprop",0.7)
e("dl-gradient-accumulation","dl-mixed-precision",0.4)
e("dl-pruning","dl-perceptron",1.0)
e("dl-pruning","dl-knowledge-distillation",0.4)
e("dl-data-augmentation","dl-regularization-dl",0.4)
e("dl-interpretability","dl-cnn",0.4)
e("dl-interpretability","dl-backprop",0.7)
e("dl-loss-landscape","opt-saddle-points",0.7)
e("dl-loss-landscape","dl-backprop",0.4)
e("dl-double-descent","stat-bias-variance",0.7)
e("dl-double-descent","ml-overfitting",0.4)
e("dl-label-smoothing","dl-loss-functions",0.7)
e("dl-label-smoothing","dl-softmax",0.4)
e("dl-nas","dl-cnn-architectures",0.4)
e("dl-nas","opt-gradient-descent",0.4)
e("dl-adversarial-robustness","dl-backprop",0.7)
e("dl-adversarial-robustness","dl-loss-functions",0.4)

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

# ---- nlp-llms (gap-fill wave) ----
n("llm-static-embeddings", "Static Word Embeddings (word2vec/GloVe)", "nlp-llms", "embeddings",
  "Learning fixed word vectors via skip-gram/CBOW (word2vec) and co-occurrence factorization (GloVe), and their limits versus contextual representations.",
  [(R,0.65,WK),(E,0.55,AW)])
n("llm-contextual-embeddings", "Contextual Embeddings", "nlp-llms", "embeddings",
  "Representations that vary with surrounding context (ELMo, BERT/GPT hidden states) versus static embeddings, and why context-sensitivity improves downstream tasks.",
  [(R,0.78,DP),(E,0.72,WK)])
n("llm-sentence-embeddings", "Sentence Embeddings & Semantic Similarity", "nlp-llms", "embeddings",
  "Pooling or fine-tuning models (e.g. Sentence-BERT) into fixed-size sentence/document vectors and measuring similarity via cosine distance for retrieval and clustering.",
  [(R,0.68,WK),(E,0.82,DP)])
n("llm-masked-language-modeling", "Masked Language Modeling (BERT-style Pretraining)", "nlp-llms", "pretraining",
  "Predicting masked tokens from bidirectional context plus auxiliary objectives like next-sentence prediction, contrasted with causal next-token prediction.",
  [(R,0.80,DP),(E,0.68,WK)])
n("llm-architecture-variants", "Encoder-only vs Decoder-only vs Encoder-Decoder LMs", "nlp-llms", "pretraining",
  "How attention masking (bidirectional vs causal) and architecture choice shape model families (BERT, GPT, T5) and which suits which task class.",
  [(R,0.82,DP),(E,0.75,WK)])
n("llm-emergent-abilities", "Emergent Abilities of LLMs", "nlp-llms", "pretraining",
  "Capabilities that appear discontinuously with scale, and the debate over whether they are truly emergent or a metric artifact.",
  [(R,0.75,DP),(E,0.55,AW)])
n("llm-vocabulary-oov", "Vocabulary Construction & Out-of-Vocabulary Handling", "nlp-llms", "foundations",
  "Vocabulary size tradeoffs, special tokens, and subword/byte-level fallback strategies for handling rare and unseen tokens.",
  [(R,0.55,WK),(E,0.62,WK)])
n("llm-qlora", "QLoRA (Quantized LoRA Fine-tuning)", "nlp-llms", "adaptation",
  "Combining 4-bit quantized frozen weights with LoRA adapters to fine-tune large models under tight memory budgets.",
  [(R,0.68,WK),(E,0.85,DP)])
n("llm-catastrophic-forgetting", "Catastrophic Forgetting in Fine-tuning", "nlp-llms", "adaptation",
  "Loss of previously learned capabilities when fine-tuning on a narrow task distribution, and mitigations like replay, regularization, and PEFT.",
  [(R,0.72,DP),(E,0.68,WK)])
n("llm-model-merging", "Model Merging & Weight Averaging", "nlp-llms", "adaptation",
  "Combining multiple fine-tuned checkpoints via weight averaging, task arithmetic, or SLERP to blend capabilities without additional training.",
  [(R,0.62,WK),(E,0.65,WK)])
n("llm-chunking-strategies", "Chunking Strategies for Retrieval", "nlp-llms", "systems",
  "Splitting documents into retrieval units (fixed-size, semantic, recursive) and the tradeoffs between chunk size, context loss, and retrieval precision.",
  [(R,0.55,WK),(E,0.82,DP)])
n("llm-hybrid-search", "Hybrid Search (Sparse + Dense Retrieval)", "nlp-llms", "retrieval",
  "Combining lexical retrieval (BM25) with dense embedding search and fusing rankings for improved recall and precision.",
  [(R,0.58,WK),(E,0.80,DP)])
n("llm-llm-as-judge", "LLM-as-Judge Evaluation", "nlp-llms", "evaluation",
  "Using a strong LLM to score or compare model outputs against a rubric, and the biases (position, verbosity, self-preference) that affect its reliability.",
  [(R,0.75,DP),(E,0.78,DP)])
n("llm-prompt-injection", "Prompt Injection & Jailbreaking", "nlp-llms", "reliability",
  "Attacks that manipulate a model via crafted input (direct or indirect prompt injection, jailbreak templates) and defenses beyond basic guardrails.",
  [(R,0.60,WK),(E,0.78,DP)])

e("llm-static-embeddings","dl-embedding-layers",0.7)
e("llm-static-embeddings","linalg-vectors",0.4)
e("llm-contextual-embeddings","llm-static-embeddings",0.7)
e("llm-contextual-embeddings","dl-transformer-architecture",0.7)
e("llm-sentence-embeddings","llm-contextual-embeddings",0.7)
e("llm-sentence-embeddings","linalg-dot-product",0.4)
e("llm-masked-language-modeling","llm-language-modeling",0.7)
e("llm-masked-language-modeling","dl-transformer-architecture",0.7)
e("llm-architecture-variants","dl-transformer-architecture",1.0)
e("llm-architecture-variants","llm-masked-language-modeling",0.7)
e("llm-architecture-variants","llm-language-modeling",0.7)
e("llm-emergent-abilities","llm-scaling-laws",0.7)
e("llm-vocabulary-oov","llm-tokenization",1.0)
e("llm-qlora","llm-peft-lora",1.0)
e("llm-qlora","llm-quantization",1.0)
e("llm-catastrophic-forgetting","llm-finetuning",0.7)
e("llm-model-merging","llm-finetuning",0.4)
e("llm-model-merging","llm-peft-lora",0.4)
e("llm-chunking-strategies","llm-rag",0.7)
e("llm-hybrid-search","llm-vector-search",0.7)
e("llm-hybrid-search","llm-reranking",0.4)
e("llm-llm-as-judge","llm-evaluation",0.7)
e("llm-llm-as-judge","llm-hallucination",0.4)
e("llm-prompt-injection","llm-guardrails",0.7)
e("llm-prompt-injection","llm-agents",0.4)

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

# ---- post-training-llms (deepened further: RL theory, reasoning-era RL, interpretability, safety) ----
n("pt-preference-data-collection", "Preference Data Collection & Annotator Agreement", "post-training-llms", "rlhf",
  "How pairwise preference datasets are collected, and measuring inter-annotator agreement and label noise.",
  [(R,0.78,DP)])
n("pt-trust-region-rl", "Trust Regions & TRPO", "post-training-llms", "rl-math",
  "Constraining policy updates to a trust region via a hard KL constraint, and its relation to PPO's clipped surrogate.",
  [(R,0.85,DV)])
n("pt-online-dpo", "Iterative & Online DPO/RLHF", "post-training-llms", "preference-optimization",
  "Refreshing preference data and the reference policy across rounds instead of a single offline pass.",
  [(R,0.82,DP)])
n("pt-rlvr", "RL with Verifiable Rewards (RLVR)", "post-training-llms", "reasoning",
  "Training on programmatically checkable rewards (unit tests, math answer matching) instead of a learned reward model.",
  [(R,0.88,DP)])
n("pt-self-consistency", "Self-Consistency & Sampling-Based Reasoning", "post-training-llms", "reasoning",
  "Sampling multiple reasoning chains and marginalizing over final answers by majority vote.",
  [(R,0.75,WK)])
n("pt-test-time-compute", "Test-Time Compute Scaling", "post-training-llms", "reasoning",
  "Trading additional inference-time computation (longer chains, search, verification) for accuracy instead of scaling parameters.",
  [(R,0.85,DP)])
n("pt-reasoning-distillation", "Distillation of Reasoning Traces", "post-training-llms", "reasoning",
  "Fine-tuning smaller models on long chain-of-thought traces generated by stronger reasoning models.",
  [(R,0.78,WK)])
n("pt-inner-outer-alignment", "Inner vs. Outer Alignment", "post-training-llms", "safety-foundations",
  "Distinguishing a misspecified training objective (outer) from a learned model pursuing a different objective (inner).",
  [(R,0.82,DP)])
n("pt-mesa-optimization", "Mesa-Optimization", "post-training-llms", "safety-foundations",
  "When a learned model itself implements an internal optimizer pursuing a mesa-objective that can diverge from the base objective.",
  [(R,0.78,DP)])
n("pt-superposition", "Superposition & Polysemanticity", "post-training-llms", "interpretability",
  "How networks represent more features than dimensions by encoding them in overlapping, non-orthogonal directions.",
  [(R,0.82,DP)])
n("pt-circuits", "Circuit Analysis & Causal Mediation", "post-training-llms", "interpretability",
  "Identifying causal computational subgraphs (e.g. induction heads, the IOI circuit) via activation patching and ablation.",
  [(R,0.82,DP)])
n("pt-probing", "Linear Probing for Interpretability", "post-training-llms", "interpretability",
  "Training simple classifiers on hidden activations to test what information a representation linearly encodes.",
  [(R,0.75,WK)])
n("pt-refusal-direction", "Refusal Direction & Behavior Ablation", "post-training-llms", "interpretability",
  "Refusal as a single steerable direction in activation space, and how ablating or amplifying it controls jailbreak susceptibility.",
  [(R,0.78,DP)])
n("pt-model-organisms", "Model Organisms of Misalignment", "post-training-llms", "safety-methods",
  "Deliberately training small-scale models exhibiting a target misaligned behavior (e.g. sleeper agents) to study detection and removal.",
  [(R,0.75,DP)])
n("pt-sandbagging", "Sandbagging & Strategic Underperformance", "post-training-llms", "safety-failures",
  "Models deliberately underperforming on evaluations to conceal capabilities.",
  [(R,0.75,DP)])
n("pt-cot-faithfulness", "Chain-of-Thought Faithfulness", "post-training-llms", "safety-methods",
  "Whether a model's stated chain-of-thought reflects the actual computation driving its answer, and how to test it.",
  [(R,0.80,DP)])
n("pt-unlearning", "Machine Unlearning for LLMs", "post-training-llms", "safety-methods",
  "Removing the influence of specific training data or capabilities from a trained model without full retraining.",
  [(R,0.72,WK)])

e("pt-preference-data-collection","pt-reward-modeling",0.7)
e("pt-preference-data-collection","pt-bradley-terry",0.4)
e("pt-trust-region-rl","pt-policy-gradient",1.0)
e("pt-trust-region-rl","opt-lagrange",0.7)
e("pt-ppo","pt-trust-region-rl",0.4)
e("pt-online-dpo","pt-dpo",1.0)
e("pt-online-dpo","pt-best-of-n",0.4)
e("pt-rlvr","pt-grpo",0.7)
e("pt-rlvr","pt-process-reward",0.4)
e("pt-rlvr","pt-rl-formulation",0.7)
e("pt-self-consistency","llm-chain-of-thought",0.7)
e("pt-test-time-compute","pt-self-consistency",0.4)
e("pt-test-time-compute","pt-best-of-n",0.4)
e("pt-test-time-compute","pt-rlvr",0.4)
e("pt-reasoning-distillation","pt-instruction-tuning",0.7)
e("pt-reasoning-distillation","pt-rlvr",0.4)
e("pt-inner-outer-alignment","pt-alignment-problem",1.0)
e("pt-mesa-optimization","pt-inner-outer-alignment",1.0)
e("pt-superposition","pt-mech-interp",1.0)
e("pt-superposition","linalg-orthogonality",0.4)
e("pt-sae","pt-superposition",1.0)
e("pt-circuits","pt-mech-interp",1.0)
e("pt-circuits","dl-transformer-architecture",0.4)
e("pt-probing","pt-mech-interp",0.7)
e("pt-refusal-direction","pt-activation-steering",1.0)
e("pt-refusal-direction","pt-red-teaming",0.4)
e("pt-model-organisms","pt-deceptive-alignment",0.7)
e("pt-model-organisms","pt-safety-evals",0.4)
e("pt-sandbagging","pt-safety-evals",0.7)
e("pt-sandbagging","pt-deceptive-alignment",0.4)
e("pt-cot-faithfulness","llm-chain-of-thought",0.7)
e("pt-cot-faithfulness","pt-mech-interp",0.4)
e("pt-unlearning","pt-instruction-tuning",0.4)
e("pt-unlearning","pt-safety-evals",0.4)

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
n("mlops-data-versioning", "Data Versioning", "ml-systems-mlops", "data",
  "Tracking versions of datasets used for training so runs and results can be reproduced.",
  [(E,0.72,WK),(D,0.58,WK)])
n("mlops-training-serving-skew", "Training/Serving Skew", "ml-systems-mlops", "data",
  "Diagnosing and preventing mismatches between features computed at training time vs. inference time.",
  [(E,0.82,DP),(D,0.55,WK)])
n("mlops-data-lineage", "Data & Model Lineage", "ml-systems-mlops", "data",
  "Tracking provenance of data and model artifacts through the pipeline for auditability and debugging.",
  [(E,0.68,WK),(D,0.50,AW)])
n("mlops-labeling-pipelines", "Labeling Pipelines & Annotation Quality", "ml-systems-mlops", "data",
  "Designing annotation workflows and measuring label quality via inter-annotator agreement.",
  [(E,0.60,WK),(D,0.62,WK)])
n("mlops-data-validation", "Data Validation", "ml-systems-mlops", "data",
  "Automated schema and statistical checks on input data to catch bad data before training or serving.",
  [(E,0.72,WK),(D,0.60,WK)])
n("mlops-model-registry", "Model Registry & Versioning", "ml-systems-mlops", "lifecycle",
  "Centralized versioning, staging, and promotion of trained model artifacts across environments.",
  [(E,0.75,WK),(R,0.45,AW)])
n("mlops-reproducibility", "Reproducibility & Seeding", "ml-systems-mlops", "lifecycle",
  "Seeding, environment pinning, and deterministic pipelines that make training runs reproducible.",
  [(R,0.68,WK),(E,0.75,WK),(D,0.62,WK)])
n("mlops-ci-cd-ml", "CI/CD for ML", "ml-systems-mlops", "lifecycle",
  "Continuous integration/delivery adapted for ML: automated tests, retraining triggers, staged rollout.",
  [(E,0.78,DP)])
n("mlops-orchestration-dags", "Pipeline Orchestration (DAG Scheduling)", "ml-systems-mlops", "lifecycle",
  "DAG-based workflow orchestration for scheduling and chaining data and training pipeline steps.",
  [(E,0.72,WK)])
n("mlops-data-parallel-training", "Data-Parallel Training", "ml-systems-mlops", "training",
  "Replicating a model across devices, splitting batches, and synchronizing gradients each step.",
  [(R,0.72,WK),(E,0.85,DP)])
n("mlops-model-parallel-training", "Model-Parallel Training", "ml-systems-mlops", "training",
  "Splitting a single model's layers or parameters across multiple devices when it doesn't fit on one.",
  [(R,0.75,WK),(E,0.82,DP)])
n("mlops-tensor-pipeline-parallelism", "Tensor & Pipeline Parallelism", "ml-systems-mlops", "training",
  "Splitting individual layers/matmuls across devices (tensor parallelism) and layer stages with micro-batching (pipeline parallelism).",
  [(R,0.72,DP),(E,0.80,DP)])
n("mlops-gradient-synchronization", "Gradient Synchronization Strategies", "ml-systems-mlops", "training",
  "All-reduce vs. parameter-server synchronization, and synchronous vs. asynchronous SGD tradeoffs.",
  [(R,0.65,WK),(E,0.78,DP)])
n("mlops-checkpointing-fault-tolerance", "Checkpointing & Fault Tolerance", "ml-systems-mlops", "training",
  "Periodically checkpointing model/optimizer state and resuming distributed jobs after preemption or failure.",
  [(R,0.62,WK),(E,0.75,WK)])
n("mlops-gpu-scheduling", "GPU Utilization & Scheduling", "ml-systems-mlops", "training",
  "Cluster-level GPU resource allocation, scheduling, and utilization monitoring for training and inference workloads.",
  [(E,0.72,WK)])
n("mlops-hyperparameter-tuning-at-scale", "Hyperparameter Tuning at Scale", "ml-systems-mlops", "training",
  "Running many hyperparameter trials in parallel across a cluster with early-stopping schedulers such as ASHA or Hyperband.",
  [(R,0.55,WK),(E,0.68,WK),(D,0.50,AW)])
n("mlops-distributed-memory-optimization", "Distributed Training Memory Optimization", "ml-systems-mlops", "training",
  "Reducing per-device memory footprint at scale via optimizer state sharding (ZeRO), activation checkpointing, and CPU/NVMe offloading.",
  [(R,0.68,DP),(E,0.75,DP)])
n("mlops-containerization-ml", "Containerization for ML", "ml-systems-mlops", "deployment",
  "Packaging models and their dependencies into containers for consistent, portable deployment.",
  [(E,0.68,WK)])
n("mlops-inference-latency-optimization", "Inference Latency Optimization", "ml-systems-mlops", "deployment",
  "Reducing production inference latency and increasing throughput via batching, caching, and hardware acceleration.",
  [(E,0.80,DP),(R,0.50,AW)])
n("mlops-cost-optimization-ml", "Cost Optimization for ML Workloads", "ml-systems-mlops", "deployment",
  "Managing compute cost for training and serving: spot/preemptible instances, autoscaling, and right-sizing hardware.",
  [(E,0.62,WK)])
n("mlops-performance-degradation-alerting", "Performance Degradation Alerting", "ml-systems-mlops", "operations",
  "Defining SLOs and alerting thresholds for model quality and system health so degradation is caught early.",
  [(E,0.68,WK),(D,0.55,WK)])
n("mlops-retraining-strategies", "Retraining Strategies & Triggers", "ml-systems-mlops", "operations",
  "Deciding when and how to retrain models: scheduled, drift-triggered, or performance-triggered policies.",
  [(E,0.72,WK),(D,0.58,WK)])
n("mlops-feedback-loops", "Feedback Loops", "ml-systems-mlops", "operations",
  "Capturing production predictions and outcome labels to close the loop for retraining, and the risk of feedback-induced distribution shift.",
  [(E,0.65,WK),(D,0.55,WK),(R,0.45,AW)])
n("mlops-model-testing", "ML Model & Pipeline Testing", "ml-systems-mlops", "testing",
  "Unit and behavioral testing of models and pipelines: invariance tests, minimum functionality tests, and regression checks beyond aggregate metrics.",
  [(E,0.68,WK),(D,0.50,AW)])

e("mlops-feature-stores","mlops-data-pipelines",1.0)
e("mlops-model-serving","sysd-scalability",0.7)
e("mlops-monitoring","mlops-model-serving",0.7)
e("mlops-distributed-training","dl-backprop",0.7)
e("mlops-distributed-training","opt-sgd",0.7)
e("mlops-ab-testing-ml","mlops-model-serving",0.7)
e("mlops-experiment-tracking","ml-train-test-split",0.4)
e("mlops-data-versioning","mlops-data-pipelines",0.7)
e("mlops-training-serving-skew","mlops-data-pipelines",0.7)
e("mlops-training-serving-skew","mlops-feature-stores",0.7)
e("mlops-data-lineage","mlops-data-pipelines",0.7)
e("mlops-data-lineage","mlops-data-versioning",0.4)
e("mlops-labeling-pipelines","mlops-data-pipelines",0.4)
e("mlops-data-validation","mlops-data-pipelines",0.7)
e("mlops-model-registry","mlops-experiment-tracking",0.7)
e("mlops-reproducibility","mlops-experiment-tracking",0.4)
e("mlops-ci-cd-ml","mlops-model-registry",0.7)
e("mlops-ci-cd-ml","mlops-experiment-tracking",0.4)
e("mlops-orchestration-dags","mlops-data-pipelines",0.7)
e("mlops-data-parallel-training","mlops-distributed-training",1.0)
e("mlops-model-parallel-training","mlops-distributed-training",1.0)
e("mlops-tensor-pipeline-parallelism","mlops-model-parallel-training",0.7)
e("mlops-tensor-pipeline-parallelism","mlops-distributed-training",0.7)
e("mlops-gradient-synchronization","mlops-data-parallel-training",1.0)
e("mlops-gradient-synchronization","cs-concurrency",0.4)
e("mlops-checkpointing-fault-tolerance","mlops-distributed-training",0.7)
e("mlops-gpu-scheduling","mlops-distributed-training",0.4)
e("mlops-hyperparameter-tuning-at-scale","ml-hyperparameter-search",0.7)
e("mlops-hyperparameter-tuning-at-scale","mlops-gpu-scheduling",0.4)
e("mlops-distributed-memory-optimization","mlops-model-parallel-training",0.7)
e("mlops-distributed-memory-optimization","dl-mixed-precision",0.4)
e("mlops-containerization-ml","mlops-model-serving",0.4)
e("mlops-inference-latency-optimization","mlops-model-serving",0.7)
e("mlops-inference-latency-optimization","llm-quantization",0.4)
e("mlops-cost-optimization-ml","mlops-gpu-scheduling",0.4)
e("mlops-cost-optimization-ml","mlops-model-serving",0.4)
e("mlops-performance-degradation-alerting","mlops-monitoring",0.7)
e("mlops-performance-degradation-alerting","sysd-observability",0.7)
e("mlops-retraining-strategies","mlops-monitoring",0.7)
e("mlops-retraining-strategies","mlops-training-serving-skew",0.4)
e("mlops-feedback-loops","mlops-monitoring",0.4)
e("mlops-feedback-loops","mlops-retraining-strategies",0.4)
e("mlops-model-testing","mlops-data-validation",0.4)
e("mlops-model-testing","ml-evaluation-metrics",0.4)

# ===========================================================================
# ROLE-SPECIFIC SECTIONS
# ===========================================================================

# ---- data-science-analytics -----------------------------------------------
n("ds-eda", "Exploratory Data Analysis", "data-science-analytics", "analysis",
  "Profiling distributions, spotting anomalies, and forming hypotheses.",
  [(E,0.62,WK),(D,0.90,DP),(P,0.60,WK)])
n("ds-data-cleaning", "Data Cleaning & Wrangling", "data-science-analytics", "analysis",
  "Handling missing values, duplicate records, and inconsistent formats before analysis.",
  [(E,0.65,WK),(D,0.88,DP)])
n("ds-outlier-detection", "Outlier Detection in Practice", "data-science-analytics", "analysis",
  "Identifying outliers via IQR, z-score/modified z-score, and visual methods, and deciding whether to winsorize, cap, remove, or investigate them.",
  [(E,0.55,WK),(D,0.80,WK)])
n("ds-feature-metric-definition", "Feature & Metric Definition", "data-science-analytics", "analysis",
  "Translating an ambiguous business question into a precise, measurable definition: numerator/denominator, unit, aggregation window, and edge cases.",
  [(D,0.85,DP),(P,0.80,WK)])
n("ds-ab-testing", "A/B Testing Design", "data-science-analytics", "experimentation",
  "Designing controlled experiments: randomization, power, and MDE.",
  [(E,0.62,WK),(D,0.92,DP),(P,0.85,DP)])
n("ds-randomization-assignment", "Randomization & Assignment Units", "data-science-analytics", "experimentation",
  "Choosing the unit of randomization (user, session, device, cluster) and assignment mechanism, and why mismatches with the unit of analysis bias results.",
  [(D,0.85,DP),(P,0.62,WK)])
n("ds-test-duration-peeking", "Test Duration & Peeking", "data-science-analytics", "experimentation",
  "Setting experiment run length to cover business cycles and reach target sample size, and the inflated false-positive risk of checking results early and often.",
  [(D,0.85,DP),(P,0.68,WK)])
n("ds-novelty-primacy-effects", "Novelty & Primacy Effects", "data-science-analytics", "experimentation",
  "Temporary treatment-effect distortions from users reacting to a change simply because it's new (novelty) or resisting it out of habit (primacy), and how to distinguish them from durable effects.",
  [(D,0.78,DP),(P,0.65,WK)])
n("ds-interference-network-effects", "Interference & Network Effects in Experiments", "data-science-analytics", "experimentation",
  "SUTVA violations where a user's treatment affects another user's outcome (marketplaces, social graphs), and how they bias standard A/B estimates.",
  [(D,0.78,DP),(P,0.55,AW)])
n("ds-variance-reduction-cuped", "Variance Reduction (CUPED)", "data-science-analytics", "experimentation",
  "Using pre-experiment covariates to reduce metric variance and shrink confidence intervals without changing sample size.",
  [(D,0.75,DP),(E,0.50,AW)])
n("ds-switchback-quasi-experiments", "Switchback & Quasi-Experimental Designs", "data-science-analytics", "experimentation",
  "Time-based switchback designs and other quasi-experimental setups used when individual-level randomization isn't feasible, e.g., under strong interference.",
  [(D,0.72,WK)])
n("ds-causal-inference", "Causal Graphs & Confounding", "data-science-analytics", "causal-inference",
  "Potential-outcomes framing, causal DAGs, and confounding as the foundation for choosing an identification strategy when randomization isn't possible.",
  [(D,0.85,DP),(P,0.62,WK)])
n("ds-diff-in-diff", "Difference-in-Differences", "data-science-analytics", "causal-inference",
  "Estimating causal effects by comparing treatment/control changes over time under the parallel-trends assumption.",
  [(D,0.82,DP),(P,0.55,AW)])
n("ds-propensity-score-matching", "Propensity Score Matching", "data-science-analytics", "causal-inference",
  "Balancing observed covariates between treated and control groups by matching on estimated treatment probability to reduce confounding in observational data.",
  [(D,0.78,DP)])
n("ds-instrumental-variables", "Instrumental Variables", "data-science-analytics", "causal-inference",
  "Using a variable that affects treatment but not the outcome directly to identify causal effects under unobserved confounding.",
  [(D,0.75,DP)])
n("ds-regression-discontinuity", "Regression Discontinuity Design", "data-science-analytics", "causal-inference",
  "Estimating causal effects at a threshold where treatment assignment discontinuously changes, e.g., eligibility cutoffs.",
  [(D,0.72,WK)])
n("ds-synthetic-control", "Synthetic Control Method", "data-science-analytics", "causal-inference",
  "Constructing a weighted combination of untreated units to approximate the counterfactual for a single treated unit, common in market-level or geo experiments.",
  [(D,0.68,WK)])
n("ds-selection-survivorship-bias", "Selection & Survivorship Bias in Analytics", "data-science-analytics", "causal-inference",
  "How non-random inclusion in a dataset -- e.g., analyzing only retained users or completed sessions -- systematically distorts conclusions.",
  [(D,0.80,DP),(P,0.68,WK)])
n("ds-metrics-design", "Metric Design", "data-science-analytics", "product-analytics",
  "Defining north-star and guardrail metrics that resist gaming.",
  [(D,0.85,DP),(P,0.88,DP)])
n("ds-metric-trees", "Metric Trees & Decomposition", "data-science-analytics", "product-analytics",
  "Breaking a top-line metric into its multiplicative or additive input drivers to localize where a change originates.",
  [(D,0.85,DP),(P,0.82,DP)])
n("ds-cohort-analysis", "Cohort Analysis", "data-science-analytics", "business-analytics",
  "Grouping users by shared start event (signup week, first purchase) and tracking their behavior over time to separate aging effects from period effects.",
  [(D,0.82,DP),(P,0.72,WK)])
n("ds-funnel-analysis", "Funnel Analysis", "data-science-analytics", "business-analytics",
  "Measuring step-by-step conversion through a sequence of user actions to locate where drop-off concentrates.",
  [(D,0.80,DP),(P,0.78,WK)])
n("ds-retention-churn-analysis", "Retention & Churn Analysis", "data-science-analytics", "business-analytics",
  "Measuring how long users stay active and characterizing the drivers of churn using retention curves and cohort comparisons.",
  [(D,0.82,DP),(P,0.75,WK)])
n("ds-segmentation-analysis", "User & Customer Segmentation", "data-science-analytics", "business-analytics",
  "Grouping users into meaningful segments by behavior or value to target analysis, experiments, or product decisions.",
  [(D,0.72,WK),(P,0.70,WK)])
n("ds-diagnosing-metric-drop", "Diagnosing a Metric Drop", "data-science-analytics", "business-analytics",
  "The structured case-study workflow for root-causing a sudden metric change: ruling out instrumentation issues, mix shifts, seasonality, and external events before concluding a real effect.",
  [(D,0.90,DP),(P,0.88,DP)])
n("ds-time-series-decomposition-business", "Time-Series Decomposition for Business Metrics", "data-science-analytics", "forecasting",
  "Splitting a KPI series into trend, seasonality, and residual components to separate expected cyclic patterns from real movement.",
  [(D,0.72,WK)])
n("ds-forecasting-business-planning", "Forecasting for Business Planning", "data-science-analytics", "forecasting",
  "Producing and evaluating short-horizon forecasts of business metrics (e.g., revenue, DAU) to support planning and goal-setting.",
  [(D,0.70,WK),(P,0.62,WK)])
n("ds-anomaly-detection-metrics", "Anomaly Detection in Metrics Monitoring", "data-science-analytics", "forecasting",
  "Setting statistically grounded alert thresholds on business dashboards to flag unexpected metric moves while controlling false-alarm rate.",
  [(D,0.68,WK),(E,0.55,AW)])
n("ds-sql-analytics", "SQL Joins & Aggregation for Analytics", "data-science-analytics", "tools",
  "Combining and summarizing relational data with joins, GROUP BY aggregation, and subqueries/CTEs for analysis.",
  [(E,0.62,WK),(D,0.88,DP),(P,0.62,WK)])
n("ds-sql-window-functions", "SQL Window Functions", "data-science-analytics", "tools",
  "ROW_NUMBER, RANK, LAG/LEAD, and running/rolling aggregates computed over partitions without collapsing rows.",
  [(E,0.68,WK),(D,0.85,DP),(P,0.55,AW)])
n("ds-query-optimization-analytics", "Query Optimization for Analysts", "data-science-analytics", "tools",
  "Writing analytical queries that scale: filtering before joining, indexing awareness, and avoiding expensive full scans on large tables.",
  [(E,0.60,WK),(D,0.65,WK)])
n("ds-experiment-pitfalls", "Experiment Interpretation Pitfalls", "data-science-analytics", "experimentation",
  "Simpson's paradox and other aggregation traps that make an experiment's overall result misleading.",
  [(D,0.80,DP),(P,0.72,WK)])
n("ds-storytelling", "Data Storytelling", "data-science-analytics", "communication",
  "Turning analysis into clear, decision-driving narratives.",
  [(D,0.78,WK),(P,0.75,WK)])
n("ds-dashboards", "Dashboards & Visualization", "data-science-analytics", "communication",
  "Designing visualizations that communicate accurately.",
  [(D,0.70,WK),(P,0.65,WK)])

e("ds-data-cleaning","ds-eda",0.7)
e("ds-outlier-detection","ds-eda",0.7)
e("ds-outlier-detection","stat-robust-statistics",0.4)
e("ds-feature-metric-definition","ds-eda",0.4)
e("ds-ab-testing","stat-hypothesis-testing",1.0)
e("ds-ab-testing","stat-t-test",0.7)
e("ds-randomization-assignment","ds-ab-testing",0.7)
e("ds-randomization-assignment","stat-sampling-design",0.4)
e("ds-test-duration-peeking","stat-power-analysis",0.7)
e("ds-test-duration-peeking","stat-sequential-testing",0.7)
e("ds-test-duration-peeking","ds-ab-testing",1.0)
e("ds-novelty-primacy-effects","ds-ab-testing",0.7)
e("ds-interference-network-effects","ds-ab-testing",0.7)
e("ds-interference-network-effects","ds-randomization-assignment",0.7)
e("ds-variance-reduction-cuped","ds-ab-testing",0.7)
e("ds-variance-reduction-cuped","stat-linear-regression",0.7)
e("ds-switchback-quasi-experiments","ds-ab-testing",0.7)
e("ds-switchback-quasi-experiments","ds-interference-network-effects",0.7)
e("ds-causal-inference","stat-linear-regression",0.7)
e("ds-causal-inference","ds-ab-testing",0.7)
e("ds-diff-in-diff","ds-causal-inference",1.0)
e("ds-diff-in-diff","stat-linear-regression",0.7)
e("ds-propensity-score-matching","ds-causal-inference",1.0)
e("ds-propensity-score-matching","ml-logistic-regression",0.7)
e("ds-instrumental-variables","ds-causal-inference",1.0)
e("ds-instrumental-variables","stat-linear-regression",0.7)
e("ds-regression-discontinuity","ds-causal-inference",1.0)
e("ds-regression-discontinuity","stat-linear-regression",0.7)
e("ds-synthetic-control","ds-causal-inference",1.0)
e("ds-synthetic-control","ds-diff-in-diff",0.4)
e("ds-selection-survivorship-bias","ds-causal-inference",0.7)
e("ds-metrics-design","ds-eda",0.4)
e("ds-metric-trees","ds-metrics-design",0.7)
e("ds-cohort-analysis","ds-eda",0.4)
e("ds-funnel-analysis","ds-metrics-design",0.4)
e("ds-retention-churn-analysis","ds-cohort-analysis",0.7)
e("ds-retention-churn-analysis","stat-survival-analysis",0.4)
e("ds-segmentation-analysis","ds-eda",0.4)
e("ds-segmentation-analysis","ml-kmeans",0.4)
e("ds-diagnosing-metric-drop","ds-metric-trees",0.7)
e("ds-diagnosing-metric-drop","ds-cohort-analysis",0.4)
e("ds-diagnosing-metric-drop","ds-funnel-analysis",0.4)
e("ds-diagnosing-metric-drop","ds-eda",0.4)
e("ds-time-series-decomposition-business","stat-time-series",0.7)
e("ds-forecasting-business-planning","ds-time-series-decomposition-business",0.7)
e("ds-forecasting-business-planning","stat-time-series",0.4)
e("ds-anomaly-detection-metrics","ds-time-series-decomposition-business",0.7)
e("ds-anomaly-detection-metrics","ml-anomaly-detection",0.4)
e("ds-sql-analytics","cs-sql",1.0)
e("ds-sql-window-functions","cs-sql",1.0)
e("ds-sql-window-functions","ds-sql-analytics",0.7)
e("ds-query-optimization-analytics","cs-sql",0.7)
e("ds-query-optimization-analytics","ds-sql-analytics",0.4)
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
n("pm-user-personas", "User Personas & Segmentation", "product-management", "discovery",
  "Building representative user archetypes and segmenting users to ground product decisions.",
  [(P,0.75,WK),(D,0.45,AW)])
n("pm-jobs-to-be-done", "Jobs-to-Be-Done Framework", "product-management", "discovery",
  "Framing user motivation as the job a customer hires a product to do, independent of any solution.",
  [(P,0.80,DP)])
n("pm-customer-discovery", "Customer Discovery & User Interviews", "product-management", "discovery",
  "Structuring interviews and discovery research to surface real user needs without leading the witness.",
  [(P,0.78,WK)])
n("pm-problem-framing", "Problem Framing & Clarifying Questions", "product-management", "discovery",
  "Turning an ambiguous prompt into a clear problem statement, target user, and constraints before proposing solutions.",
  [(P,0.90,DP)])
n("pm-favorite-product", "Favorite Product Questions", "product-management", "core",
  "Articulating what makes a product excellent using structured product-sense reasoning rather than opinion.",
  [(P,0.70,WK)])
n("pm-product-critique", "Product Critique & Improvement", "product-management", "core",
  "Evaluating an existing product's weaknesses and proposing prioritized, justified improvements.",
  [(P,0.85,DP)])
n("pm-mvp-scoping", "MVP Definition & Scoping", "product-management", "execution",
  "Defining the minimum viable scope that tests a hypothesis with the least effort.",
  [(P,0.85,DP)])
n("pm-roadmapping", "Roadmapping", "product-management", "execution",
  "Sequencing initiatives over time, balancing strategy, capacity, and dependencies.",
  [(P,0.80,DP)])
n("pm-gtm-strategy", "Go-to-Market Strategy", "product-management", "strategy",
  "Planning how a product reaches and is adopted by its target market: channels, messaging, and sequencing.",
  [(P,0.78,DP)])
n("pm-competitive-analysis", "Competitive Analysis & Positioning", "product-management", "strategy",
  "Assessing competitor strengths and weaknesses and articulating differentiated positioning.",
  [(P,0.75,WK)])
n("pm-pricing-strategy", "Pricing Strategy", "product-management", "strategy",
  "Choosing pricing models and reasoning about willingness-to-pay, packaging, and monetization tradeoffs.",
  [(P,0.68,WK)])
n("pm-product-market-fit", "Product-Market Fit", "product-management", "strategy",
  "Recognizing and reasoning about signals that a product satisfies strong, durable market demand.",
  [(P,0.75,WK),(D,0.40,AW)])
n("pm-aarrr-funnel", "Acquisition-Activation-Retention-Referral-Revenue Funnel", "product-management", "analytics",
  "Structuring product metrics and diagnosis across the AARRR (pirate metrics) funnel stages.",
  [(P,0.75,DP),(D,0.50,WK)])
n("pm-growth-loops", "Growth Loops & Viral Mechanics", "product-management", "strategy",
  "Designing self-reinforcing acquisition loops and reasoning about viral coefficient and loop payback time.",
  [(P,0.72,WK)])
n("pm-north-star-metric", "North Star Metric Selection", "product-management", "analytics",
  "Choosing the single metric that best captures the value a product delivers to its users.",
  [(P,0.80,DP),(D,0.45,AW)])
n("pm-launch-metrics", "Success Metrics for a Feature Launch", "product-management", "analytics",
  "Selecting primary success and guardrail metrics for a specific feature before it ships.",
  [(P,0.78,DP)])
n("pm-launch-planning", "Launch Planning & Rollout Strategy", "product-management", "execution",
  "Sequencing a staged rollout (beta, phased GA) with kill criteria and risk mitigation.",
  [(P,0.75,WK)])
n("pm-cross-functional-partnership", "Cross-Functional Partnership with Engineering & Design", "product-management", "execution",
  "Structuring the day-to-day PM/engineering/design working relationship: specs, reviews, and decision rights.",
  [(P,0.75,WK)])
n("pm-prd-writing", "Writing PRDs & Product Specs", "product-management", "execution",
  "Structuring a product requirements document: problem, goals, non-goals, requirements, and success metrics.",
  [(P,0.78,DP)])
n("pm-agile-scrum", "Agile & Scrum Fundamentals for PMs", "product-management", "execution",
  "Sprint planning, backlog grooming, and the PM's role in agile ceremonies.",
  [(P,0.60,WK)])
n("pm-technical-fluency", "Technical Fluency for PMs", "product-management", "technical-pm",
  "Enough understanding of APIs, data, and system constraints to scope tradeoffs with engineering.",
  [(P,0.65,WK)])
n("pm-api-platform-thinking", "API & Platform Product Thinking", "product-management", "technical-pm",
  "Product decisions specific to APIs and developer platforms: versioning, developer experience, and ecosystem tradeoffs.",
  [(P,0.62,WK)])
n("pm-product-ethics", "Responsible Product Decisions & Ethics", "product-management", "technical-pm",
  "Reasoning about privacy, dark patterns, accessibility, and fairness tradeoffs in product decisions.",
  [(P,0.65,WK)])

e("pm-metrics","pm-product-sense",0.7)
e("pm-prioritization","pm-product-sense",0.7)
e("pm-product-design","pm-product-sense",1.0)
e("pm-strategy","pm-product-sense",0.7)
e("pm-execution","pm-prioritization",0.7)
e("pm-root-cause","pm-metrics",1.0)
e("pm-estimation","pm-product-sense",0.4)
e("pm-metrics","ds-metrics-design",0.4)
e("pm-ai-product","pm-product-sense",0.7)
e("pm-user-personas","pm-product-sense",0.7)
e("pm-jobs-to-be-done","pm-product-sense",0.7)
e("pm-customer-discovery","pm-product-sense",0.7)
e("pm-customer-discovery","pm-jobs-to-be-done",0.4)
e("pm-problem-framing","pm-product-sense",0.7)
e("pm-favorite-product","pm-product-sense",1.0)
e("pm-product-critique","pm-product-sense",1.0)
e("pm-product-critique","pm-prioritization",0.4)
e("pm-mvp-scoping","pm-execution",0.7)
e("pm-mvp-scoping","pm-problem-framing",0.4)
e("pm-roadmapping","pm-prioritization",0.7)
e("pm-roadmapping","pm-strategy",0.4)
e("pm-gtm-strategy","pm-strategy",0.7)
e("pm-competitive-analysis","pm-strategy",0.7)
e("pm-pricing-strategy","pm-strategy",0.4)
e("pm-product-market-fit","pm-strategy",0.4)
e("pm-product-market-fit","pm-metrics",0.4)
e("pm-aarrr-funnel","pm-metrics",0.7)
e("pm-growth-loops","pm-aarrr-funnel",0.7)
e("pm-north-star-metric","pm-metrics",0.7)
e("pm-launch-metrics","pm-metrics",0.7)
e("pm-launch-metrics","ds-metrics-design",0.4)
e("pm-launch-planning","pm-launch-metrics",0.7)
e("pm-launch-planning","pm-execution",0.4)
e("pm-cross-functional-partnership","pm-execution",0.4)
e("pm-cross-functional-partnership","beh-cross-functional",0.4)
e("pm-prd-writing","pm-problem-framing",0.7)
e("pm-prd-writing","pm-launch-metrics",0.4)
e("pm-agile-scrum","pm-roadmapping",0.4)
e("pm-technical-fluency","sysd-api-design",0.4)
e("pm-technical-fluency","cs-databases",0.4)
e("pm-api-platform-thinking","pm-technical-fluency",0.7)
e("pm-api-platform-thinking","sysd-rest-graphql-grpc",0.4)
e("pm-product-ethics","pm-product-sense",0.4)

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

# ---- finance-quant (deepened) ----
n("fq-logic-puzzles", "Logic & Sequence Puzzles", "finance-quant", "aptitude",
  "Pattern recognition, number sequences, and logic-grid puzzles that test structured reasoning speed.",
  [(F,0.85,DP)])
n("fq-optimal-stopping", "Optimal Stopping Problems", "finance-quant", "aptitude",
  "Secretary-problem-style stopping rules for maximizing expected outcome under sequential decisions.",
  [(F,0.85,DV)])
n("fq-gamblers-ruin", "Gambler's Ruin", "finance-quant", "aptitude",
  "Probability of ruin for a biased random walk with absorbing barriers.",
  [(F,0.85,DV)])
n("fq-card-dice-coin-problems", "Card, Dice & Coin-Flip Problems", "finance-quant", "aptitude",
  "Classic combinatorial probability puzzles involving shuffled decks, dice rolls, and repeated coin flips.",
  [(F,0.88,DV)])
n("fq-monty-hall-reasoning", "Monty Hall & Conditional Reasoning Puzzles", "finance-quant", "aptitude",
  "Updating probabilities correctly under revealed information, using the Monty Hall problem as the canonical trap.",
  [(F,0.85,DV)])
n("fq-kelly-criterion", "Kelly Criterion", "finance-quant", "aptitude",
  "Optimal bet sizing to maximize long-run geometric growth rate given a probabilistic edge.",
  [(F,0.88,DV)])
n("fq-betting-odds", "Betting, Odds & Fair Value", "finance-quant", "aptitude",
  "Converting between odds, implied probabilities, and fair value/vig in betting markets.",
  [(F,0.82,DP)])
n("fq-bond-pricing", "Bond Pricing", "finance-quant", "finance",
  "Pricing a bond as the present value of its coupon and principal cash flows.",
  [(F,0.90,DV)])
n("fq-duration-convexity", "Duration & Convexity", "finance-quant", "finance",
  "Measuring a bond's price sensitivity to interest-rate changes via duration and convexity.",
  [(F,0.85,DP)])
n("fq-yield-curves", "Yield Curves & Term Structure", "finance-quant", "finance",
  "Shapes of the yield curve and what they imply about rate expectations.",
  [(F,0.82,DP)])
n("fq-forward-rates", "Forward Rates", "finance-quant", "finance",
  "Deriving implied forward rates from spot rates under no-arbitrage.",
  [(F,0.80,DP)])
n("fq-no-arbitrage-pricing", "No-Arbitrage Pricing", "finance-quant", "finance",
  "Pricing assets by ruling out riskless profit opportunities; the law of one price.",
  [(F,0.90,DV)])
n("fq-risk-neutral-valuation", "Risk-Neutral Valuation", "finance-quant", "finance",
  "Pricing derivatives as discounted expectations under the risk-neutral measure.",
  [(F,0.88,DV)])
n("fq-the-greeks", "The Greeks", "finance-quant", "finance",
  "Delta, gamma, vega, theta, and rho: option price sensitivities to the underlying, volatility, and time.",
  [(F,0.90,DP)])
n("fq-implied-realized-vol", "Implied vs Realized Volatility", "finance-quant", "finance",
  "Distinguishing market-implied volatility from historically realized volatility and their relationship.",
  [(F,0.82,DP)])
n("fq-volatility-smile", "Volatility Smile", "finance-quant", "finance",
  "Why implied volatility varies across strikes and maturities, departing from Black-Scholes' constant-volatility assumption.",
  [(F,0.75,WK)])
n("fq-binomial-option-pricing", "Binomial Option Pricing Model", "finance-quant", "finance",
  "Pricing options on a discrete-time binomial tree via replication and risk-neutral probabilities.",
  [(F,0.85,DV)])
n("fq-ito-lemma", "Ito's Lemma", "finance-quant", "math",
  "The chain rule for stochastic calculus, used to derive the dynamics of functions of a diffusion process.",
  [(F,0.80,DV),(R,0.40,AW)])
n("fq-geometric-brownian-motion", "Geometric Brownian Motion", "finance-quant", "math",
  "The lognormal diffusion model underlying Black-Scholes for asset price dynamics.",
  [(F,0.82,DV),(R,0.40,AW)])
n("fq-futures-forwards", "Futures & Forwards", "finance-quant", "finance",
  "Contract mechanics, marking-to-market, and pricing of futures and forward contracts.",
  [(F,0.80,DP)])
n("fq-delta-hedging", "Delta Hedging", "finance-quant", "finance",
  "Dynamically hedging an option position's directional exposure using the underlying.",
  [(F,0.85,DP)])
n("fq-capm", "CAPM", "finance-quant", "portfolio",
  "The Capital Asset Pricing Model: expected return as a function of systematic risk (beta).",
  [(F,0.82,DP)])
n("fq-sharpe-performance-metrics", "Sharpe Ratio & Performance Metrics", "finance-quant", "portfolio",
  "Risk-adjusted return measures: Sharpe ratio, Sortino ratio, and information ratio.",
  [(F,0.80,WK)])
n("fq-value-at-risk", "Value at Risk (VaR)", "finance-quant", "portfolio",
  "Quantile-based estimate of potential portfolio loss over a horizon at a given confidence level.",
  [(F,0.80,DP)])
n("fq-expected-shortfall", "Expected Shortfall (CVaR)", "finance-quant", "portfolio",
  "The expected loss beyond the VaR threshold; a coherent tail-risk measure.",
  [(F,0.72,WK)])
n("fq-order-types", "Order Types & Execution", "finance-quant", "markets",
  "Market, limit, stop, and iceberg orders, and how order type choice affects execution.",
  [(F,0.75,WK)])
n("fq-pairs-trading", "Pairs Trading", "finance-quant", "markets",
  "Trading the spread between cointegrated assets to exploit mean-reverting deviations.",
  [(F,0.75,WK)])
n("fq-backtesting-overfitting", "Backtesting & Overfitting", "finance-quant", "markets",
  "Evaluating strategy performance on historical data while avoiding look-ahead bias and overfitting.",
  [(F,0.78,WK)])

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

e("fq-logic-puzzles","fq-mental-math",0.4)
e("fq-optimal-stopping","prob-expectation",1.0)
e("fq-optimal-stopping","fq-brainteasers",0.4)
e("fq-gamblers-ruin","prob-random-walks",1.0)
e("fq-gamblers-ruin","prob-markov-chains",0.7)
e("fq-card-dice-coin-problems","prob-counting",1.0)
e("fq-card-dice-coin-problems","prob-conditional",0.7)
e("fq-monty-hall-reasoning","prob-bayes",1.0)
e("fq-kelly-criterion","prob-expectation",1.0)
e("fq-kelly-criterion","fq-expected-value-games",0.7)
e("fq-betting-odds","prob-expectation",0.7)
e("fq-betting-odds","fq-mental-math",0.4)
e("fq-bond-pricing","fq-time-value-money",1.0)
e("fq-duration-convexity","fq-bond-pricing",1.0)
e("fq-duration-convexity","opt-taylor-expansion",0.4)
e("fq-yield-curves","fq-bond-pricing",0.7)
e("fq-forward-rates","fq-yield-curves",1.0)
e("fq-forward-rates","fq-no-arbitrage-pricing",0.7)
e("fq-no-arbitrage-pricing","fq-time-value-money",0.7)
e("fq-risk-neutral-valuation","fq-no-arbitrage-pricing",1.0)
e("fq-risk-neutral-valuation","prob-expectation",0.7)
e("fq-the-greeks","fq-options-basics",1.0)
e("fq-the-greeks","fq-black-scholes",0.7)
e("fq-implied-realized-vol","fq-options-basics",0.7)
e("fq-implied-realized-vol","stat-time-series",0.4)
e("fq-volatility-smile","fq-implied-realized-vol",1.0)
e("fq-volatility-smile","fq-black-scholes",0.7)
e("fq-binomial-option-pricing","fq-options-basics",1.0)
e("fq-binomial-option-pricing","fq-risk-neutral-valuation",0.7)
e("fq-ito-lemma","fq-stochastic-processes",1.0)
e("fq-ito-lemma","opt-taylor-expansion",0.4)
e("fq-geometric-brownian-motion","fq-ito-lemma",1.0)
e("fq-geometric-brownian-motion","fq-stochastic-processes",0.7)
e("fq-black-scholes","fq-geometric-brownian-motion",0.7)
e("fq-futures-forwards","fq-no-arbitrage-pricing",0.7)
e("fq-futures-forwards","fq-time-value-money",0.4)
e("fq-delta-hedging","fq-the-greeks",1.0)
e("fq-delta-hedging","fq-options-basics",0.7)
e("fq-capm","fq-portfolio-theory",1.0)
e("fq-capm","prob-covariance",0.7)
e("fq-sharpe-performance-metrics","fq-portfolio-theory",0.7)
e("fq-sharpe-performance-metrics","prob-expectation",0.4)
e("fq-value-at-risk","prob-distributions",0.7)
e("fq-value-at-risk","fq-portfolio-theory",0.4)
e("fq-expected-shortfall","fq-value-at-risk",1.0)
e("fq-order-types","fq-market-microstructure",0.7)
e("fq-pairs-trading","fq-statistics-trading",1.0)
e("fq-backtesting-overfitting","fq-statistics-trading",0.4)
e("fq-backtesting-overfitting","stat-model-selection-criteria",0.4)

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
