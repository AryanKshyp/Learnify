/**
 * Shared vocabulary for presenting the curriculum.
 *
 * The domain grouping and section codes are taken from `viz_template.html` deliberately, so the
 * standalone curriculum explorer and this application describe the graph the same way. Sixteen
 * flat sections is too many to scan; six domains is not.
 */

import type { Status } from "../api/types";

export interface Domain {
  label: string;
  sections: string[];
}

export const DOMAINS: Domain[] = [
  {
    label: "Mathematical foundations",
    sections: ["probability", "statistics", "linear-algebra", "calculus-optimization"],
  },
  { label: "Computer science", sections: ["cs-fundamentals", "dsa", "system-design"] },
  { label: "Machine learning", sections: ["classical-ml", "deep-learning"] },
  { label: "Language models", sections: ["nlp-llms", "post-training-llms"] },
  {
    label: "Applied practice",
    sections: ["ml-systems-mlops", "data-science-analytics", "finance-quant"],
  },
  { label: "Professional", sections: ["product-management", "behavioral"] },
];

export const SECTION_META: Record<string, { code: string; name: string }> = {
  probability: { code: "PROB", name: "Probability" },
  statistics: { code: "STAT", name: "Statistics" },
  "linear-algebra": { code: "LIN", name: "Linear Algebra" },
  "calculus-optimization": { code: "OPT", name: "Calculus & Optimization" },
  "cs-fundamentals": { code: "CS", name: "CS Fundamentals" },
  dsa: { code: "DSA", name: "Data Structures & Algorithms" },
  "system-design": { code: "SYS", name: "System Design" },
  "classical-ml": { code: "CML", name: "Classical ML" },
  "deep-learning": { code: "DL", name: "Deep Learning" },
  "nlp-llms": { code: "LLM", name: "NLP & LLMs" },
  "post-training-llms": { code: "PT", name: "Post-training & Alignment" },
  "ml-systems-mlops": { code: "OPS", name: "ML Systems & MLOps" },
  "data-science-analytics": { code: "DS", name: "Data Science & Analytics" },
  "product-management": { code: "PM", name: "Product Management" },
  "finance-quant": { code: "FQ", name: "Finance & Quant" },
  behavioral: { code: "BEH", name: "Behavioral" },
};

export const sectionName = (section: string): string =>
  SECTION_META[section]?.name ?? section;

export const sectionCode = (section: string): string =>
  SECTION_META[section]?.code ?? section.slice(0, 3).toUpperCase();

/** Status colours. Deliberately a ramp, so progress reads as movement along one axis.
 *
 * Keyed by `Status` rather than `string`: typed loosely, the union declared in `api/types` was
 * thrown away and adding a status to the backend enum compiled clean and rendered a colourless
 * node. Now it is a compile error until the ramp is extended.
 */
export const STATUS_COLOR: Record<Status, string> = {
  unassessed: "#8a8a80",
  learning: "#c2703d",
  practiced: "#c9a227",
  retained: "#5b8c5a",
  mastered: "#2f6b4f",
};

export const STATUS_LABEL: Record<Status, string> = {
  unassessed: "Unassessed",
  learning: "Learning",
  practiced: "Practiced",
  retained: "Retained",
  mastered: "Mastered",
};

/** How far out from the focused node to draw. This is the "bigger/smaller focus" control. */
export const FOCUS_DEPTHS = [
  { value: 1, label: "Immediate", hint: "direct prerequisites and dependents" },
  { value: 2, label: "Nearby", hint: "two hops out" },
  { value: 3, label: "Extended", hint: "three hops out" },
  { value: 99, label: "Full chain", hint: "every ancestor and descendant" },
] as const;

export const pct = (value: number): string => `${Math.round(value * 100)}%`;

export const formatHours = (hours: number): string =>
  hours < 1 ? `${Math.round(hours * 60)} min` : `${hours.toFixed(1)} h`;
