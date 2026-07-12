export type Decision = "APPROVE" | "FLAG_FOR_REVIEW" | "REJECT";

export const STATUS: Record<Decision, { label: string; icon: string; text: string; bg: string; border: string; dot: string }> = {
  APPROVE: {
    label: "Approved",
    icon: "✓",
    text: "#0a7227",
    bg: "#e9f8ec",
    border: "#bce8c4",
    dot: "#0ca30c",
  },
  FLAG_FOR_REVIEW: {
    label: "Flagged for Review",
    icon: "!",
    text: "#8a5a00",
    bg: "#fff6e0",
    border: "#f3d98f",
    dot: "#fab219",
  },
  REJECT: {
    label: "Rejected",
    icon: "✕",
    text: "#a3312f",
    bg: "#fdecec",
    border: "#f3c1c0",
    dot: "#d03b3b",
  },
};

export const ACCENT = "#2952cc";

export const STAGE_ORDER = ["Extraction", "PO Matching", "Validation", "Decision"] as const;
export type Stage = (typeof STAGE_ORDER)[number];
export type StageState = "pending" | "running" | "done" | "error";
