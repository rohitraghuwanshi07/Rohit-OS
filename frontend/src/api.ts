export type Proc = { pid: string; arrival: number; burst: number; priority: number };
export type Ev = { t: number; type: string; pid: string; why: string };
export const DEFAULT_WORKLOAD: Proc[] = [
  { pid: "P1", arrival: 0, burst: 8, priority: 2 }, { pid: "P2", arrival: 1, burst: 2, priority: 1 },
  { pid: "P3", arrival: 2, burst: 4, priority: 3 }, { pid: "P4", arrival: 3, burst: 1, priority: 1 }];
export async function api<T>(path: string, body?: unknown, method = body ? "POST" : "GET"): Promise<T> {
  const r = await fetch(path, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(typeof e.detail === "string" ? e.detail : "Request failed (" + r.status + ")"); }
  return r.json();
}
