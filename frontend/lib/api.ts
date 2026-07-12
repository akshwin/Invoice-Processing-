import type { Decision } from "./theme";

// Strip any trailing slash — a base URL configured as "https://host.com/" would
// otherwise produce double-slash paths like "https://host.com//api/runs", which
// FastAPI's router treats as a different (nonexistent) path and 404s.
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

export interface LineItem {
  description: string;
  quantity: number | null;
  unit_price: number | null;
  amount: number | null;
}

export interface ExtractedInvoice {
  invoice_number: string | null;
  invoice_date: string | null;
  vendor_name: string | null;
  po_reference: string | null;
  line_items: LineItem[];
  subtotal: number | null;
  tax: number | null;
  total: number | null;
  extraction_confidence_notes: string;
}

export interface RunRecord {
  run_id: string;
  timestamp: string;
  invoice_number: string | null;
  vendor_name: string | null;
  matched_po: string | null;
  total: number | null;
  decision: Decision;
  reasoning: string;
  rules_triggered: string[];
  extracted_invoice: ExtractedInvoice;
  match_method: string;
  extraction_method: string;
}

export interface PurchaseOrderDetail {
  po_number: string;
  vendor_name: string;
  po_amount: number;
  po_date: string;
  status: string;
}

export interface RuleCheck {
  rule_id: string;
  passed: boolean;
  message: string;
}

export interface ExtractionStageData {
  extracted_invoice: ExtractedInvoice;
  extraction_method: string | null;
}

export interface PoMatchingStageData {
  match_method: string;
  notes: string;
  matched_po: PurchaseOrderDetail | null;
}

export interface ValidationStageData {
  rules_checked: RuleCheck[];
  failed_rule: string | null;
}

export type DecisionStageData = RunRecord;

export type StageData =
  | ExtractionStageData
  | PoMatchingStageData
  | ValidationStageData
  | DecisionStageData;

export type StreamEvent =
  | { type: "stage_done"; stage: string; data: StageData }
  | { type: "result"; record: RunRecord }
  | { type: "error"; stage: string; message: string }
  | { type: "end" };

export interface SampleInvoice {
  filename: string;
  label: string;
  vendor_name: string;
  description: string;
  expected_outcome: Decision;
}

export async function createRun(file: File): Promise<{ run_id: string; stages: string[] }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/runs`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Upload failed (${res.status}): ${body}`);
  }
  return res.json();
}

export function streamRun(runId: string, onEvent: (event: StreamEvent) => void): () => void {
  const es = new EventSource(`${API_BASE}/api/runs/${runId}/stream`);
  es.onmessage = (message) => {
    const event = JSON.parse(message.data) as StreamEvent;
    onEvent(event);
    if (event.type === "end") {
      es.close();
    }
  };
  es.onerror = () => {
    onEvent({ type: "error", stage: "Connection", message: "Lost connection to the server." });
    es.close();
  };
  return () => es.close();
}

export async function listRuns(decision?: string): Promise<RunRecord[]> {
  const url = new URL(`${API_BASE}/api/runs`);
  if (decision) url.searchParams.set("decision", decision);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Failed to load run history (${res.status})`);
  return res.json();
}

export async function getRun(runId: string): Promise<RunRecord> {
  const res = await fetch(`${API_BASE}/api/runs/${runId}`);
  if (!res.ok) throw new Error(`Run not found (${res.status})`);
  return res.json();
}

export async function listSamples(): Promise<SampleInvoice[]> {
  const res = await fetch(`${API_BASE}/api/samples`);
  if (!res.ok) throw new Error(`Failed to load sample invoices (${res.status})`);
  return res.json();
}

export function sampleDownloadUrl(filename: string): string {
  return `${API_BASE}/api/samples/${encodeURIComponent(filename)}`;
}

export async function fetchSampleFile(filename: string): Promise<File> {
  const res = await fetch(sampleDownloadUrl(filename));
  if (!res.ok) throw new Error(`Failed to fetch sample (${res.status})`);
  const blob = await res.blob();
  return new File([blob], filename, { type: "application/pdf" });
}
