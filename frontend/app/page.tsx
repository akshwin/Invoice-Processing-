"use client";

import { useRef, useState } from "react";
import StatusBadge from "@/components/StatusBadge";
import Stepper from "@/components/Stepper";
import { createRun, streamRun, type RunRecord, type StreamEvent } from "@/lib/api";
import { STAGE_ORDER, type StageState } from "@/lib/theme";

function initialStageStates(): Record<string, StageState> {
  return Object.fromEntries(STAGE_ORDER.map((s) => [s, "pending" as StageState]));
}

export default function RunPage() {
  const [file, setFile] = useState<File | null>(null);
  const [running, setRunning] = useState(false);
  const [stageStates, setStageStates] = useState<Record<string, StageState>>(initialStageStates());
  const [result, setResult] = useState<RunRecord | null>(null);
  const [error, setError] = useState<{ stage: string; message: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function pickFile(f: File | null) {
    setFile(f);
    setResult(null);
    setError(null);
  }

  async function runPipeline() {
    if (!file) return;
    setRunning(true);
    setResult(null);
    setError(null);
    const states = initialStageStates();
    states[STAGE_ORDER[0]] = "running";
    setStageStates({ ...states });

    try {
      const { run_id } = await createRun(file);

      await new Promise<void>((resolve) => {
        streamRun(run_id, (event: StreamEvent) => {
          if (event.type === "stage_done") {
            states[event.stage] = "done";
            const idx = STAGE_ORDER.indexOf(event.stage as (typeof STAGE_ORDER)[number]);
            if (idx >= 0 && idx + 1 < STAGE_ORDER.length) {
              states[STAGE_ORDER[idx + 1]] = "running";
            }
            setStageStates({ ...states });
          } else if (event.type === "result") {
            setResult(event.record);
          } else if (event.type === "error") {
            const idx = STAGE_ORDER.indexOf(event.stage as (typeof STAGE_ORDER)[number]);
            if (idx >= 0) states[STAGE_ORDER[idx]] = "error";
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

  return (
    <div>
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
          <div>{file ? "Choose a different PDF" : "Click or drag an invoice PDF here"}</div>
          {file && <div className="filename">{file.name}</div>}
        </div>
        <button className="primary" disabled={!file || running} onClick={runPipeline}>
          {running ? "Running…" : "Run pipeline"}
        </button>
      </div>

      {(running || result || error) && (
        <div className="card">
          <div className="section-label">Pipeline progress</div>
          <Stepper stageStates={stageStates} />
        </div>
      )}

      {error && (
        <div className="card">
          <div className="section-label">Result</div>
          <div className="error-box">
            Processing failed at the <strong>{error.stage}</strong> stage: {error.message}
          </div>
        </div>
      )}

      {result && (
        <div className="card">
          <div className="section-label">Result</div>
          <StatusBadge decision={result.decision} />
          {result.extraction_method === "vision" && (
            <p style={{ fontSize: 13, color: "var(--ink-muted)", marginTop: 10 }}>
              📷 This PDF had no machine-readable text layer (scanned/image-based) — fields were read directly
              from the page image.
            </p>
          )}
          <div className="field-grid">
            <div>
              <div className="field-label">Vendor</div>
              <div>{result.vendor_name ?? "—"}</div>
            </div>
            <div>
              <div className="field-label">Invoice number</div>
              <div>{result.invoice_number ?? "—"}</div>
            </div>
            <div>
              <div className="field-label">Matched PO</div>
              <div>{result.matched_po ?? "None"}</div>
            </div>
          </div>
          <div className="field-label">Reasoning</div>
          <p>{result.reasoning}</p>

          <details className="json-details">
            <summary>Details — raw extracted data &amp; rule IDs</summary>
            <pre>
              {JSON.stringify(
                {
                  rules_triggered: result.rules_triggered,
                  match_method: result.match_method,
                  extraction_method: result.extraction_method,
                  extracted_invoice: result.extracted_invoice,
                },
                null,
                2
              )}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}
