import { Fragment } from "react";
import { STAGE_ORDER, type StageState } from "@/lib/theme";

const ICONS: Record<StageState, string> = { pending: "○", running: "●", done: "✓", error: "✕" };
const LABELS: Record<StageState, string> = { pending: "Pending", running: "Running", done: "Done", error: "Failed" };

export default function Stepper({ stageStates }: { stageStates: Record<string, StageState> }) {
  return (
    <div className="stepper">
      {STAGE_ORDER.map((stage, i) => {
        const state = stageStates[stage] ?? "pending";
        const statusClass = state === "running" || state === "error" ? state : "";
        return (
          <Fragment key={stage}>
            <div className="step-item">
              <div className={`step-circle ${state}`}>{ICONS[state]}</div>
              <div className="step-label">{stage}</div>
              <div className={`step-status ${statusClass}`}>{LABELS[state]}</div>
            </div>
            {i < STAGE_ORDER.length - 1 && (
              <div className={`step-connector ${state === "done" ? "filled" : ""}`} />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
