import { useEffect, useState, useCallback } from "react";
import { Radio, RefreshCw, WifiOff } from "lucide-react";
import { getJSON, fmtPct } from "../api";
import { formatCurrency } from "../utils/currency";
import LiveTimeline from "./LiveTimeline";

const BADGE = {
  IDLE: "bg-rose-500/20 text-rose-400 border-rose-500/30",
  "OVER-PROVISIONED": "bg-amber-500/20 text-amber-400 border-amber-500/30",
  OK: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  SYSTEM: "bg-slate-500/20 text-slate-300 border-slate-500/30",
};
const ALERT = {
  SPIKE: "bg-rose-600 text-white border-rose-500",
  GROWING: "bg-amber-500/20 text-amber-300 border-amber-500/40",
};

// What is running on the cluster RIGHT NOW (OpenCost, last 10 minutes). Refreshes every 30 s,
// so `kubectl apply -f k8s/demo-new-app.yaml` shows up here within ~1-2 minutes.
export default function LivePanel({ currency }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [alerts, setAlerts] = useState({});

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setData(await getJSON("/live?window=10m"));
      setErr(null);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  const items = data?.workloads || [];
  const idle = items.filter((w) => w.status === "IDLE");

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Radio className={`w-4 h-4 ${data?.connected ? "text-emerald-400" : "text-slate-500"}`} />
            Live Workloads (last 10 min)
          </h2>
          <p className="text-xs text-slate-400">
            Straight from OpenCost at {data?.opencost_url || "…"} · auto-refresh 30 s
            {data?.auto_sync_minutes > 0 && ` · history sync every ${data.auto_sync_minutes} min`}
          </p>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#1a1a1e] border border-[#28282e] text-xs">
          <RefreshCw className={`w-3 h-3 ${busy ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {(err || (data && !data.connected)) && (
        <div className="rounded border border-[#28282e] bg-[#16171d] p-4 text-xs text-slate-300 space-y-2">
          <div className="flex items-center gap-2 font-semibold text-amber-300">
            <WifiOff className="w-4 h-4" /> Not connected to a live cluster
          </div>
          <p>The rest of the dashboard still works on stored data. To go live:</p>
          <pre className="bg-black/40 rounded p-2 font-mono text-[11px] overflow-x-auto">
{`./start.sh setup     # once: kind cluster + OpenCost + test apps
./start.sh live      # port-forward + auto-sync every 2 min`}
          </pre>
          <p className="text-slate-500">{err || data?.error}</p>
        </div>
      )}

      {data?.connected && (
        <>
          {idle.length > 0 && (
            <div className="rounded border border-rose-800 bg-rose-950/30 p-3 text-xs text-rose-200">
              <b>{idle.length} idle workload(s)</b> are paying for resources they do not use:{" "}
              {idle.map((w) => `${w.namespace}/${w.workload}`).join(", ")}
            </div>
          )}
          <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-[#28282e] text-slate-300 uppercase text-[10px] font-bold bg-[#16171d]">
                  <th className="py-2.5 px-4">Namespace / Workload</th>
                  <th className="py-2.5 px-4">Team</th>
                  <th className="py-2.5 px-4 text-right">CPU reserved / used</th>
                  <th className="py-2.5 px-4 text-right">Efficiency</th>
                  <th className="py-2.5 px-4 text-right">Cost (10 min)</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4">Alert (last hour)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#28282e]">
                {items.map((w) => (
                  <tr key={`${w.namespace}/${w.workload}`} className="hover:bg-[#202127]">
                    <td className="py-2.5 px-4 font-semibold text-white">
                      <span className="text-slate-500">{w.namespace}/</span>
                      {w.workload}
                    </td>
                    <td className="py-2.5 px-4 text-slate-300">{w.team}</td>
                    <td className="py-2.5 px-4 text-right font-mono">
                      {(w.cpu_request ?? 0).toFixed(3)} / {(w.cpu_usage ?? 0).toFixed(4)}
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono">{fmtPct(w.efficiency_pct, 2)}</td>
                    <td className="py-2.5 px-4 text-right font-mono">{formatCurrency(w.total_cost, currency)}</td>
                    <td className="py-2.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${BADGE[w.status]}`}>{w.status}</span>
                    </td>
                    <td className="py-2.5 px-4">
                      {alerts[`${w.namespace}/${w.workload}`] && (
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${ALERT[alerts[`${w.namespace}/${w.workload}`]]}`}>
                          {alerts[`${w.namespace}/${w.workload}`]}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <LiveTimeline currency={currency} onStatus={setAlerts} />
        </>
      )}
    </div>
  );
}
