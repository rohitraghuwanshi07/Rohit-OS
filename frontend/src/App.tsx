import { useEffect, useMemo, useRef, useState } from "react";
import { api, DEFAULT_WORKLOAD, Proc } from "./api";

type Tab = "sched" | "memory" | "deadlock" | "security" | "evidence" | "kernel";
const TABS: [Tab, string][] = [["sched", "scheduler"], ["memory", "memory"], ["deadlock", "deadlock"], ["security", "immune"], ["evidence", "evidence"], ["kernel", "kernel.log"]];
const PAL = ["#3dff9a", "#4de1ff", "#ffb347", "#ff4fd8", "#a78bfa", "#ff6b6b", "#f9f871", "#7dffcf"];
const col = (p: string) => p === "idle" ? "transparent" : PAL[(parseInt(p.replace(/\D/g, "")) || 0) % PAL.length];
const KLOG = `ROHIT OS kernel booting
[ok] GDT with ring 3 segments and TSS loaded
[ok] page allocator reuses freed pages
[ok] paging enabled, kernel identity-mapped as supervisor-only
[ok] IDT: 32 exception gates, timer, keyboard, int 0x80
[exc] breakpoint handled at eip=0x101955
[ok] demand paging: unmapped pages mapped on page fault
[user] hello from ring 3 via int 0x80; motd file says: welcome to ROHIT OS
[exc] general protection (vector 13) err=0x0 eip=0x10000000
[exc] user program killed, kernel survives
[exc] page fault at 0x100000 err=0x5 eip=0x10000000
[ok] user read of kernel memory blocked by paging, killed
[ok] ramfs write and read back
Scheduler event log (300 ticks, quantum 5): 60 dispatches
  t=5 kernel -> worker1   t=10 worker1 -> worker2   t=15 worker2 -> worker3
ROHITOS SELFTEST PASS`.split("\n");

function usePlay(max: number, ms: number) {
  const [i, setI] = useState(0), [on, setOn] = useState(false);
  useEffect(() => { if (!on) return; const t = setInterval(() => setI(v => { if (v >= max) { setOn(false); return v; } return v + 1; }), ms); return () => clearInterval(t); }, [on, max, ms]);
  return { i, setI, on, setOn };
}
function Win({ title, children, tag }: { title: string; children: any; tag?: string }) {
  return <section className="win"><div className="bar"><i /><i /><i /><b>{title}</b><span>{tag}</span></div><div className="body">{children}</div></section>;
}
function Controls({ pl, n, speed, setSpeed }: { pl: ReturnType<typeof usePlay>; n: number; speed: number; setSpeed: (v: number) => void }) {
  return <div className="ctl"><button className="ghost" onClick={() => pl.setI(0)}>reset</button><button className="ghost" onClick={() => pl.setI(Math.max(0, pl.i - 1))}>back</button>
    <button onClick={() => { if (pl.i >= n) pl.setI(0); pl.setOn(!pl.on); }}>{pl.on ? "pause" : "play"}</button><button className="ghost" onClick={() => pl.setI(Math.min(n, pl.i + 1))}>step</button>
    <input aria-label="timeline" type="range" min={0} max={n} value={pl.i} onChange={e => { pl.setOn(false); pl.setI(+e.target.value); }} />
    <select aria-label="speed" value={speed} onChange={e => setSpeed(+e.target.value)}><option value={900}>slow</option><option value={450}>normal</option><option value={150}>fast</option></select><span className="dim">{pl.i}/{n}</span></div>;
}

function Sched({ log }: { log: (s: string) => void }) {
  const [wl, setWl] = useState<Proc[]>(DEFAULT_WORKLOAD), [pol, setPol] = useState("fcfs"), [q, setQ] = useState(2), [speed, setSpeed] = useState(450);
  const [res, setRes] = useState<any>(null), [cmp, setCmp] = useState<any>(null), [err, setErr] = useState("");
  const n = res ? res.events.length : 0, pl = usePlay(n, speed);
  const create = async () => { try {
    const r: any = await api("/api/runs", { workload: wl, policy: pol, quantum: q });
    const ev: any = await api("/api/runs/" + r.id + "/events"), st: any = await api("/api/runs/" + r.id + "/state");
    setRes({ id: r.id, hash: r.event_hash, events: ev.events, gantt: st.gantt }); pl.setI(0);
    setCmp(await api("/api/compare", { workload: wl, policies: ["fcfs", "sjf", "prio", "rr"], quantum: q })); setErr(""); log("run " + r.id + " " + pol + " hash " + r.event_hash);
  } catch (e: any) { setErr(e.message); } };
  const view = useMemo(() => { if (!res) return null; let ready: string[] = [], run: string | null = null;
    for (const e of res.events.slice(0, pl.i)) { if (e.type === "arrive") ready.push(e.pid); if (e.type === "dispatch") { ready = ready.filter(x => x !== e.pid); run = e.pid; } if (e.type === "preempt") { ready.push(e.pid); run = null; } if (e.type === "complete") run = null; }
    return { ready, run, t: pl.i ? res.events[pl.i - 1].t : 0, e: pl.i ? res.events[pl.i - 1] : null }; }, [res, pl.i]);
  const upd = (i: number, k: keyof Proc, v: string) => setWl(wl.map((p, j) => j === i ? { ...p, [k]: k === "pid" ? v : Number(v) } : p));
  const M: [string, string, number][] = [["avg_waiting", "average waiting", -1], ["avg_turnaround", "average turnaround", -1], ["avg_response", "average response", -1], ["context_switches", "context switches", -1], ["cpu_utilization", "cpu utilization", 1]];
  return <><Win title="workload.cfg" tag="input">
    <div className="grid4">{wl.map((p, i) => <div className="proc" key={i} style={{ borderColor: col(p.pid) }}>
      {(["pid", "arrival", "burst", "priority"] as (keyof Proc)[]).map(k => <label key={k}>{k}<input value={p[k]} onChange={e => upd(i, k, e.target.value)} /></label>)}
      <button className="ghost sm" onClick={() => setWl(wl.filter((_, j) => j !== i))}>drop</button></div>)}</div>
    <div className="ctl"><button className="ghost" onClick={() => setWl([...wl, { pid: "P" + (wl.length + 1), arrival: 0, burst: 1, priority: 1 }])}>+ process</button>
      <label>policy<select value={pol} onChange={e => setPol(e.target.value)}><option>fcfs</option><option>sjf</option><option>prio</option><option>rr</option></select></label>
      <label>quantum<input type="number" min={1} value={q} onChange={e => setQ(+e.target.value)} style={{ width: 70 }} /></label><button onClick={create}>execute run</button></div>
    {err && <p className="err" role="alert">! {err}</p>}</Win>
  {res && view && <Win title={"time-machine " + res.id} tag={"stream " + res.hash}>
    <Controls pl={pl} n={n} speed={speed} setSpeed={setSpeed} />
    <div className="cpu"><div className="core" style={{ borderColor: view.run ? col(view.run) : undefined, color: view.run ? col(view.run) : undefined }}><small>cpu</small>{view.run ?? "idle"}</div>
      <div className="queue"><small>ready queue</small><div>{view.ready.length ? view.ready.map((p, i) => <span key={p + i} className="chip" style={{ borderColor: col(p), color: col(p) }}>{p}</span>) : <span className="dim">empty</span>}</div></div></div>
    <div className="gantt">{res.gantt.map((g: string, k: number) => <span key={k} style={{ background: col(g), opacity: k < view.t || pl.i >= n ? 1 : 0.12 }}>{g === "idle" ? "" : g}</span>)}<div className="head" style={{ left: (view.t / res.gantt.length * 100) + "%" }} /></div>
    <div className="split"><div className="log">{res.events.map((e: any, i: number) => <div key={i} className={i === pl.i - 1 ? "on" : i >= pl.i ? "fut" : ""} onClick={() => { pl.setOn(false); pl.setI(i + 1); }}>t={String(e.t).padStart(2, "0")} {e.type.padEnd(8)} {e.pid}</div>)}</div>
      <div className="insp">{view.e ? <><b style={{ color: col(view.e.pid) }}>{view.e.type} {view.e.pid}</b><p>{view.e.why}</p></> : <p className="dim">press play. every decision is explained here.</p>}</div></div></Win>}
  {cmp && <Win title="counterfactual.diff" tag="same workload, four policies"><div className="bars">{M.map(([k, label, dir]) => { const vals = Object.keys(cmp).map(p => [p, cmp[p].metrics[k]] as [string, number]); const mx = Math.max(...vals.map(v => v[1])) || 1; const best = dir < 0 ? Math.min(...vals.map(v => v[1])) : mx;
    return <div key={k}><small>{label}</small>{vals.map(([p, v]) => <div className="bar2" key={p}><em>{p}</em><span style={{ width: Math.max(2, v / mx * 100) + "%", background: v === best ? "var(--g)" : "var(--c)" }} /><b>{k === "cpu_utilization" ? (v * 100).toFixed(0) + "%" : v.toFixed(2)}</b></div>)}</div>; })}</div>
    <p className="dim">green = best on that measure. No policy wins every row.</p></Win>}</>;
}

function Memory() {
  const [refs, setRefs] = useState("7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1"), [fr, setFr] = useState(3), [res, setRes] = useState<any>(null), [err, setErr] = useState(""), [speed, setSpeed] = useState(450);
  const n = res ? res.fifo.steps.length : 0, pl = usePlay(n, speed);
  const go = () => api("/api/memory", { refs: refs.trim().split(/\s+/).map(Number), frames: fr }).then((r: any) => { setRes(r); pl.setI(0); setErr(""); }, (e: any) => setErr(e.message));
  return <><Win title="memory.lab" tag="paging"><div className="ctl"><label>reference string<input value={refs} onChange={e => setRefs(e.target.value)} style={{ width: 340 }} /></label>
    <label>frames<input type="number" min={1} max={16} value={fr} onChange={e => setFr(+e.target.value)} style={{ width: 70 }} /></label><button onClick={go}>simulate</button></div>{err && <p className="err" role="alert">! {err}</p>}</Win>
  {res && <Win title="page-frames" tag="fifo vs lru vs optimal"><Controls pl={pl} n={n} speed={speed} setSpeed={setSpeed} />
    <div className="mem3">{["fifo", "lru", "optimal"].map(p => { const steps = res[p].steps.slice(0, pl.i), cur = steps[steps.length - 1], f = steps.filter((s: any) => !s.hit).length;
      return <div key={p} className="mcard"><h4>{p}<span className={cur ? (cur.hit ? "hit" : "miss") : ""}>{cur ? (cur.hit ? "HIT " + cur.ref : "FAULT " + cur.ref) : "ready"}</span></h4>
        <div className="frames">{Array.from({ length: fr }).map((_, k) => <div key={k} className={"frame" + (cur && cur.frames[k] === cur.ref ? (cur.hit ? " h" : " m") : "")}>{cur?.frames[k] ?? "·"}</div>)}</div>
        <div className="dim">faults {f}{pl.i === n && " · final " + res[p].faults + " (" + (res[p].fault_rate * 100).toFixed(0) + "%)"}{cur?.evicted != null && " · evicted " + cur.evicted}</div></div>; })}</div>
    <p className="dim">optimal looks ahead, so it is an offline baseline, not something a kernel can run.</p></Win>}</>;
}

function Deadlock() {
  const [sc, setSc] = useState<any>(null), [name, setName] = useState("classic_deadlock"), [r, setR] = useState<any>(null), [fixed, setFixed] = useState(false);
  const run = async () => { const s: any = sc ?? await api("/api/deadlock/scenarios"); setSc(s); setFixed(false); setR({ s: s[name], ...(await api<any>("/api/deadlock/analyze", s[name])) }); };
  const s = r?.s, np = s ? s.allocation.length : 0, nr = s ? s.available.length : 0, dead = (i: number) => !fixed && r.deadlocked.includes(i), gone = (i: number) => fixed && r.recovery_killed.includes(i);
  const P = (i: number) => ({ x: 90, y: 50 + i * 80 }), R = (j: number) => ({ x: 400, y: 50 + j * 80 + (np - nr) * 40 });
  return <><Win title="deadlock.lab" tag="detect · recover"><div className="ctl"><label>scenario<select value={name} onChange={e => { setName(e.target.value); setR(null); }}><option>classic_deadlock</option><option>no_deadlock</option></select></label><button onClick={run}>analyze</button>
    {r && r.deadlocked.length > 0 && <button className="warn" onClick={() => setFixed(true)}>recover: kill victim</button>}</div></Win>
  {r && <Win title="resource-graph" tag={r.deadlocked.length && !fixed ? "DEADLOCK" : "safe"}>
    <svg viewBox={"0 0 500 " + (Math.max(np, nr) * 80 + 40)} className="rag"><defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="currentColor" /></marker></defs>
      {s.allocation.map((row: number[], i: number) => row.map((v: number, j: number) => v > 0 && !gone(i) && <line key={"a" + i + j} x1={R(j).x - 22} y1={R(j).y} x2={P(i).x + 26} y2={P(i).y} stroke="#3dff9a" color="#3dff9a" strokeWidth="2" markerEnd="url(#a)" />))}
      {s.request.map((row: number[], i: number) => row.map((v: number, j: number) => v > 0 && !gone(i) && <line key={"r" + i + j} x1={P(i).x + 26} y1={P(i).y + 8} x2={R(j).x - 22} y2={R(j).y + 8} stroke="#ffb347" color="#ffb347" strokeDasharray="5 4" strokeWidth="2" markerEnd="url(#a)" />))}
      {Array.from({ length: np }).map((_, i) => <g key={i} opacity={gone(i) ? 0.2 : 1}><circle cx={P(i).x} cy={P(i).y} r="26" fill="#05080d" stroke={dead(i) ? "#ff4d6d" : "#4de1ff"} strokeWidth="3" className={dead(i) ? "pulse" : ""} /><text x={P(i).x} y={P(i).y + 5} textAnchor="middle" fill="#c8f5de">P{i}</text></g>)}
      {Array.from({ length: nr }).map((_, j) => <g key={j}><rect x={R(j).x - 22} y={R(j).y - 22} width="44" height="44" fill="#05080d" stroke="#a78bfa" strokeWidth="3" /><text x={R(j).x} y={R(j).y + 5} textAnchor="middle" fill="#c8f5de">R{j}</text></g>)}</svg>
    <p className="dim">green = resource held by process · amber dashed = process waiting for resource · red = deadlocked</p>
    <p>{fixed ? "recovered: terminated " + r.recovery_killed.map((i: number) => "P" + i).join(", ") + ", freeing " + JSON.stringify(r.available_after) + "." : r.deadlocked.length ? "cycle found: " + r.deadlocked.map((i: number) => "P" + i).join(" ⇄ ") + " cannot proceed." : "no cycle: every process can finish."}</p></Win>}</>;
}

function Security() {
  const [r, setR] = useState<any>(null), n = r ? r.alerts.length : 0, pl = usePlay(n, 700);
  const scan = () => api("/api/security/scan").then((x: any) => { setR(x); pl.setI(0); pl.setOn(true); });
  return <Win title="immune.sys" tag="rule engine over simulated events"><div className="ctl"><button onClick={scan}>scan event stream</button>{r && <span className="dim">{r.events.length} events audited</span>}</div>
    <p className="dim">controlled rule-based demo on synthetic events. not malware detection. responses are simulated.</p>
    <div className="feed">{r?.alerts.slice(0, pl.i).map((a: any, i: number) => <div key={i} className={"alert " + a.severity}><b>[{a.severity}] {a.rule}</b> t={a.t} pid={a.pid}<br /><span>evidence: {a.evidence}</span><br /><span>suggest: {a.suggested_response}</span></div>)}</div></Win>;
}
const Kernel = () => <Win title="kernel.log" tag="captured from a real QEMU boot"><pre className="klog">{KLOG.join("\n")}</pre><p className="dim">this is the recorded serial output of the bootable kernel (make test). run it yourself: cd kernel &amp;&amp; make run</p></Win>;

function Evidence() {
  const [v, setV] = useState<any>(null), [f, setF] = useState<any>(null), [b, setB] = useState<any>(null), [adv, setAdv] = useState<any>(null);
  const [n, setN] = useState(300), [goal, setGoal] = useState("response"), [busy, setBusy] = useState(""), [err, setErr] = useState("");
  const run = async (k: string, fn: () => Promise<void>) => { setBusy(k); setErr(""); try { await fn(); } catch (e: any) { setErr(e.message); } setBusy(""); };
  const segs = (ev: any[], total: number) => { const o: any[] = []; let prev = 0, cur = "kernel"; for (const e of ev) { o.push({ s: prev, e: e.t, p: cur }); prev = e.t; cur = e.to; } o.push({ s: prev, e: total, p: cur }); return o; };
  const strip = (ev: any[], total: number, ok?: boolean[]) => <div className="strip">{segs(ev, total).map((g, i) => <span key={i} title={g.p + " t=" + g.s + "-" + g.e} style={{ flex: g.e - g.s, background: col(g.p), outline: ok && i > 0 && !ok[i - 1] ? "2px solid var(--r)" : undefined }}>{g.e - g.s >= 15 ? g.p.replace("worker", "w") : ""}</span>)}</div>;
  const H = ["avg_waiting", "avg_turnaround", "avg_response", "max_waiting", "context_switches"];
  const csv = () => { const h = ["family", "policy", ...H]; const t = [h.join(","), ...b.rows.map((r: any) => h.map(k => r[k]).join(","))].join("\n"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([t], { type: "text/csv" })); a.download = "rohit-os-benchmark.csv"; a.click(); };
  const best = (fam: string, k: string) => Math.min(...b.rows.filter((r: any) => r.family === fam).map((r: any) => r[k]));
  return <>
    <Win title="kernel-validation" tag="simulator vs real hardware trace"><p className="dim">The engine predicts the order the real kernel dispatches tasks (round-robin, quantum 5). The kernel's actual trace was captured from a QEMU boot.</p>
      <div className="ctl"><button onClick={() => run("v", async () => setV(await api("/api/validate/kernel")))}>{busy === "v" ? "checking…" : "validate against kernel"}</button></div>
      {v && <><div className="big">{v.matched}/{v.total} <small className="dim">dispatches predicted exactly</small></div>
        <small className="dim">real kernel ({v.source})</small>{strip(v.kernel, v.total_ticks)}<small className="dim">simulator prediction (red outline = mismatch)</small>{strip(v.sim, v.total_ticks, v.ok)}</>}</Win>
    <Win title="benchmark.matrix" tag="3 workload families × 4 policies, seeded"><div className="ctl"><button onClick={() => run("b", async () => setB(await api("/api/benchmark?seeds=20")))}>{busy === "b" ? "running…" : "run benchmark (20 seeds)"}</button>{b && <button className="ghost" onClick={csv}>download csv</button>}</div>
      {b && <div className="scroll"><table className="t"><thead><tr><th>family</th><th>policy</th><th>wait</th><th>turnaround</th><th>response</th><th>max wait</th><th>switches</th></tr></thead><tbody>
        {b.rows.map((r: any, i: number) => <tr key={i}><td>{r.family}</td><td>{r.policy}</td>{H.map(k => <td key={k} className={r[k] === best(r.family, k) ? "best" : ""}>{r[k].toFixed(2)}</td>)}</tr>)}</tbody></table></div>}
      {b && <p className="dim">mean over {b.seeds} seeded workloads, quantum {b.quantum}. green = lowest in that family. no policy wins everywhere.</p>}</Win>
    <Win title="fuzz.lab" tag="invariant checking"><div className="ctl"><label>workloads<input type="number" min={10} max={1000} value={n} onChange={e => setN(+e.target.value)} style={{ width: 90 }} /></label>
      <button onClick={() => run("f", async () => setF(await api("/api/fuzz?n=" + n)))}>{busy === "f" ? "fuzzing…" : "fuzz the engine"}</button></div>
      {f && <><div className={"big " + (f.failures ? "bad" : "")}>{f.failures ? f.failures + " violations" : "0 violations"} <small className="dim">{f.checks.toLocaleString()} checks · {f.runs.toLocaleString()} runs</small></div>
        <p className="dim">checks: every burst fully executed, nothing runs before arrival, waiting never negative, replay hash identical.</p>{f.examples.map((x: any, i: number) => <p key={i} className="err">case {x.case} {x.policy}: {x.problem}</p>)}</>}</Win>
    <Win title="policy.advisor" tag="explainable recommendation"><div className="ctl"><label>optimise for<select value={goal} onChange={e => setGoal(e.target.value)}><option value="response">response time</option><option value="waiting">waiting time</option><option value="fairness">fairness (longest wait)</option><option value="switches">fewest context switches</option></select></label>
      <button onClick={() => run("a", async () => setAdv(await api("/api/recommend", { workload: DEFAULT_WORKLOAD, goal })))}>advise</button></div>
      {adv && <><div className="big">use {adv.recommended}</div>{adv.ranking.map((r: any) => <div className="bar2" key={r.policy}><em>{r.policy}</em><span style={{ width: Math.max(4, (adv.ranking[0].value / (r.value || 1)) * 100) + "%", background: r.policy === adv.recommended ? "var(--g)" : "var(--c)" }} /><b>{r.value}</b></div>)}
        <ul>{adv.evidence.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul><p className="dim">{adv.caveat}</p></>}</Win>
    {err && <p className="err" role="alert">! {err}</p>}</>;
}

type Line = { k: "in" | "out" | "err"; s: string };
function Terminal({ go, lines, push }: { go: (t: Tab) => void; lines: Line[]; push: (l: Line[]) => void }) {
  const [v, setV] = useState(""), [hist, setHist] = useState<string[]>([]), [hi, setHi] = useState(-1), end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [lines]);
  const exec = async (c: string) => { const [cmd, ...a] = c.trim().split(/\s+/); const out = (s: string) => push([{ k: "out", s }]);
    try { switch (cmd) {
      case "help": out("run <fcfs|sjf|prio|rr> [q] · compare · validate · fuzz [n] · bench · advise [goal] · mem [frames] · deadlock · scan · open <sched|memory|deadlock|security|evidence|kernel> · clear"); break;
      case "run": { const r: any = await api("/api/runs", { workload: DEFAULT_WORKLOAD, policy: a[0] || "fcfs", quantum: +a[1] || 2 }); const m: any = await api("/api/runs/" + r.id + "/metrics"); out("run " + r.id + " hash " + r.event_hash + " | wait " + m.metrics.avg_waiting + " turn " + m.metrics.avg_turnaround + " resp " + m.metrics.avg_response + " switches " + m.metrics.context_switches); break; }
      case "compare": { const r: any = await api("/api/compare", { workload: DEFAULT_WORKLOAD, policies: ["fcfs", "sjf", "prio", "rr"], quantum: 2 }); push(Object.keys(r).map(p => ({ k: "out" as const, s: p.padEnd(5) + " wait " + r[p].metrics.avg_waiting.toFixed(2) + "  turn " + r[p].metrics.avg_turnaround.toFixed(2) + "  resp " + r[p].metrics.avg_response.toFixed(2) }))); break; }
      case "mem": { const r: any = await api("/api/memory", { refs: [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1], frames: +a[0] || 3 }); out("faults  fifo " + r.fifo.faults + "  lru " + r.lru.faults + "  optimal " + r.optimal.faults); break; }
      case "deadlock": { const s: any = await api("/api/deadlock/scenarios"); const r: any = await api("/api/deadlock/analyze", s.classic_deadlock); out("deadlocked " + JSON.stringify(r.deadlocked) + " → kill " + JSON.stringify(r.recovery_killed)); break; }
      case "scan": { const r: any = await api("/api/security/scan"); push(r.alerts.map((x: any) => ({ k: "out" as const, s: "[" + x.severity + "] " + x.rule + " " + x.pid + ": " + x.evidence }))); break; }
      case "validate": { const r: any = await api("/api/validate/kernel"); out("simulator predicted " + r.matched + "/" + r.total + " real kernel dispatches (" + r.source + ")"); break; }
      case "fuzz": { const r: any = await api("/api/fuzz?n=" + (+a[0] || 200)); out(r.runs + " runs, " + r.checks + " checks, " + r.failures + " violations"); break; }
      case "bench": { const r: any = await api("/api/benchmark?seeds=10"); push(r.rows.filter((x: any) => x.family === "interactive").map((x: any) => ({ k: "out" as const, s: "interactive " + x.policy.padEnd(5) + " response " + x.avg_response.toFixed(2) + " switches " + x.context_switches.toFixed(1) }))); break; }
      case "advise": { const r: any = await api("/api/recommend", { workload: DEFAULT_WORKLOAD, goal: a[0] || "response" }); push([{ k: "out", s: "use " + r.recommended + " (goal " + r.goal + ")" }, ...r.evidence.map((e: string) => ({ k: "out" as const, s: "- " + e }))]); break; }
      case "open": { const t = a[0] as Tab; if (TABS.some(x => x[0] === t)) { go(t); out("opened " + t); } else push([{ k: "err", s: "unknown window" }]); break; }
      case "clear": push([{ k: "out", s: "\u0000" }]); break;
      default: push([{ k: "err", s: "command not found: " + cmd + " (try help)" }]); }
    } catch (e: any) { push([{ k: "err", s: e.message }]); } };
  return <div className="term" onClick={() => document.getElementById("ti")?.focus()}><div className="tl">{lines.map((l, i) => <div key={i} className={l.k}>{l.s}</div>)}<div ref={end} /></div>
    <div className="tin"><span>rohit@os:~$</span><input id="ti" aria-label="terminal" value={v} autoComplete="off" spellCheck={false} onChange={e => setV(e.target.value)}
      onKeyDown={e => { if (e.key === "Enter" && v.trim()) { push([{ k: "in", s: "$ " + v }]); setHist([v, ...hist]); setHi(-1); exec(v); setV(""); }
        if (e.key === "ArrowUp" && hist.length) { const n = Math.min(hist.length - 1, hi + 1); setHi(n); setV(hist[n]); } if (e.key === "ArrowDown") { const n = hi - 1; setHi(n); setV(n >= 0 ? hist[n] : ""); } }} /></div></div>;
}

function Rain() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => { const c = ref.current!, x = c.getContext("2d")!; if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let w = 0, h = 0, drops: number[] = []; const fit = () => { w = c.width = innerWidth; h = c.height = innerHeight; drops = Array(Math.ceil(w / 16)).fill(0).map(() => Math.random() * h / 16); }; fit(); addEventListener("resize", fit);
    const t = setInterval(() => { x.fillStyle = "rgba(5,8,13,.12)"; x.fillRect(0, 0, w, h); x.fillStyle = "#3dff9a"; x.font = "14px monospace";
      drops.forEach((d, i) => { x.fillText(String.fromCharCode(0x30a0 + Math.random() * 60), i * 16, d * 16); drops[i] = d * 16 > h && Math.random() > 0.975 ? 0 : d + 1; }); }, 70);
    return () => { clearInterval(t); removeEventListener("resize", fit); }; }, []);
  return <canvas ref={ref} className="rain" aria-hidden />;
}
function Boot({ done }: { done: () => void }) {
  const L = ["ROHIT OS v1.0  explainable operating-system laboratory", "[ ok ] deterministic simulation engine", "[ ok ] event recorder + replay hash", "[ ok ] scheduler: fcfs sjf prio rr", "[ ok ] memory: fifo lru optimal", "[ ok ] deadlock detective, immune system", "[ ok ] kernel track: ring 3, paging, syscalls (qemu)", "all systems nominal. welcome."];
  const [n, setN] = useState(0);
  useEffect(() => { if (n >= L.length) { const t = setTimeout(done, 500); return () => clearTimeout(t); } const t = setTimeout(() => setN(n + 1), 260); return () => clearTimeout(t); }, [n]);
  return <div className="boot" onClick={done} role="button" aria-label="skip boot">{L.slice(0, n).map((l, i) => <div key={i}>{l}</div>)}<span className="cur">█</span><small>click to skip</small></div>;
}

export default function App() {
  const [booted, setBooted] = useState(false), [tab, setTab] = useState<Tab>("sched"), [up, setUp] = useState(0), [online, setOnline] = useState(false);
  const [lines, setLines] = useState<Line[]>([{ k: "out", s: "ROHIT OS shell. type help." }]);
  const push = (l: Line[]) => setLines(p => l[0]?.s === "\u0000" ? [] : [...p, ...l].slice(-200));
  useEffect(() => { const t = setInterval(() => setUp(u => u + 1), 1000); api("/api/deadlock/scenarios").then(() => setOnline(true), () => setOnline(false)); return () => clearInterval(t); }, []);
  if (!booted) return <><Rain /><Boot done={() => setBooted(true)} /></>;
  const body = { sched: <Sched log={s => push([{ k: "out", s }])} />, memory: <Memory />, deadlock: <Deadlock />, security: <Security />, evidence: <Evidence />, kernel: <Kernel /> }[tab];
  return <><Rain /><div className="app"><header><div className="logo">ROHIT<span>_OS</span></div><div className="dim">uptime {String(Math.floor(up / 60)).padStart(2, "0")}:{String(up % 60).padStart(2, "0")}</div><div className={online ? "ok" : "bad"}>● engine {online ? "online" : "offline"}</div></header>
    <nav aria-label="Launcher">{TABS.map(([t, l]) => <button key={t} className={t === tab ? "on" : ""} onClick={() => setTab(t)}>{l}</button>)}</nav>
    <main>{body}</main><footer><Terminal go={setTab} lines={lines} push={push} /></footer></div></>;
}
