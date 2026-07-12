"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import StageDetailPanel from "@/components/StageDetailPanel";
import StatusBadge from "@/components/StatusBadge";
import {
  createRun,
  fetchSampleFile,
  streamRun,
  type RunRecord,
  type StageData,
  type StreamEvent,
} from "@/lib/api";
import { STAGE_ORDER, type Stage, type StageState } from "@/lib/theme";

const STAGE_ICONS: Record<StageState, string> = { pending: "○", running: "●", done: "✓", error: "✕" };
const STAGE_SUB: Record<StageState, string> = { pending: "Pending", running: "Running…", done: "Complete", error: "Failed" };

function initialStageStates(): Record<Stage, StageState> {
  return Object.fromEntries(STAGE_ORDER.map((s) => [s, "pending" as StageState])) as Record<Stage, StageState>;
}

function RunPageInner() {
  const searchParams = useSearchParams();
  const [file, setFile] = useState<File | null>(null);
  const [running, setRunning] = useState(false);
  const [stageStates, setStageStates] = useState<Record<Stage, StageState>>(initialStageStates());
  const [stageData, setStageData] = useState<Partial<Record<Stage, StageData>>>({});
  const [activeStage, setActiveStage] = useState<Stage>(STAGE_ORDER[0]);
  const [result, setResult] = useState<RunRecord | null>(null);
  const [error, setError] = useState<{ stage: string; message: string } | null>(null);
  const [loadingSample, setLoadingSample] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const sample = searchParams.get("sample");
    if (!sample) return;
    setLoadingSample(true);
    fetchSampleFile(sample)
      .then((f) => pickFile(f))
      .catch((e) => setError({ stage: "Sample", message: e instanceof Error ? e.message : String(e) }))
      .finally(() => setLoadingSample(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  function pickFile(f: File | null) {
    setFile(f);
    setResult(null);
    setError(null);
    setStageStates(initialStageStates());
    setStageData({});
  }

  async function runPipeline() {
    if (!file) return;
    setRunning(true);
    setResult(null);
    setError(null);
    setStageData({});
    const states = initialStageStates();
    states[STAGE_ORDER[0]] = "running";
    setStageStates({ ...states });
    setActiveStage(STAGE_ORDER[0]);

    try {
      const { run_id } = await createRun(file);

      await new Promise<void>((resolve) => {
        streamRun(run_id, (event: StreamEvent) => {
          if (event.type === "stage_done") {
            const stage = event.stage as Stage;
            states[stage] = "done";
            const idx = STAGE_ORDER.indexOf(stage);
            if (idx >= 0 && idx + 1 < STAGE_ORDER.length) {
              states[STAGE_ORDER[idx + 1]] = "running";
            }
            setStageStates({ ...states });
            setStageData((prev) => ({ ...prev, [stage]: event.data }));
            setActiveStage(stage);
          } else if (event.type === "result") {
            setResult(event.record);
          } else if (event.type === "error") {
            const idx = STAGE_ORDER.indexOf(event.stage as Stage);
            if (idx >= 0) {
              states[STAGE_ORDER[idx]] = "error";
              setActiveStage(STAGE_ORDER[idx]);
            }
            setStageStates({ ...states });
            setError({ stage: event.stage, message: event.message });
          } else if (event.type === "end") {
            resolve();
          }
        });
      });
    } catch (e) {
      setError({ stage: "Upload", message: e instanceof Error ? e.message : String(e) });
    } finally {
      setRunning(false);
    }
  }

  const started = running || result !== null || error !== null || Object.keys(stageData).length > 0;

  return (
    <div>
      <div className="page-header">
        <h2>Run Pipeline</h2>
        <p>Upload an invoice PDF and watch it move through extraction, PO matching, validation, and decisioning.</p>
      </div>

      <div className="card">
        <div className="section-label">Upload</div>
        <div
          className="dropzone"
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) pickFile(f);
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            className="visually-hidden"
            tabIndex={-1}
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          />
          <div>
            {loadingSample
              ? "Loading sample invoice…"
              : file
                ? "Choose a different PDF"
                : "Click or drag an invoice PDF here"}
          </div>
          {file && <div className="filename">{file.name}</div>}
        </div>
        <button className="primary" disabled={!file || running} onClick={runPipeline}>
          {running ? "Running…" : "Run pipeline"}
        </button>
        <p style={{ fontSize: 13, color: "var(--ink-muted)", marginTop: 14 }}>
          Don&apos;t have an invoice handy? Browse the <a href="/samples">Sample Invoices</a> library — it includes
          clean invoices, scanned/photographed invoices, rule-violation edge cases, and a completely different
          layout.
        </p>
      </div>

      {started && (
        <div className="run-layout" style={{ marginTop: 22 }}>
          <div className="stage-tab-list">
            {STAGE_ORDER.map((stage) => {
              const state = stageStates[stage];
              return (
                <button
                  key={stage}
                  className={`stage-tab ${activeStage === stage ? "active" : ""}`}
                  disabled={state === "pending"}
                  onClick={() => setActiveStage(stage)}
                >
                  <span className={`tab-icon ${state}`}>{STAGE_ICONS[state]}</span>
                  <span className="tab-text">
                    <span className="tab-title">{stage}</span>
                    <span className="tab-sub">{STAGE_SUB[state]}</span>
                  </span>
                </button>
              );
            })}
          </div>

          <div className="card">
            <div className="section-label">{activeStage}</div>
            {stageStates[activeStage] === "error" && error ? (
              <div className="error-box">
                Processing failed at the <strong>{error.stage}</strong> stage: {error.message}
              </div>
            ) : (
              <StageDetailPanel stage={activeStage} data={stageData[activeStage]} />
            )}
          </div>
        </div>
      )}

      {error && stageStates[error.stage as Stage] === undefined && (
        <div className="card">
          <div className="error-box">
            Processing failed at the <strong>{error.stage}</strong> stage: {error.message}
          </div>
        </div>
      )}

      {result && (
        <div className="card" style={{ marginTop: 18 }}>
          <div className="section-label">Final decision</div>
          <StatusBadge decision={result.decision} />
          <p style={{ marginTop: 14 }}>{result.reasoning}</p>
        </div>
      )}
    </div>
  );
}

export default function RunPage() {
  return (
    <Suspense fallback={<div className="card">Loading…</div>}>
      <RunPageInner />
    </Suspense>
  );
}
