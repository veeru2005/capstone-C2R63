import { useEffect, useMemo, useState, useCallback } from "react";
import { ComposedChart, Line, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Activity, TrendingUp, Zap } from "lucide-react";
import { getJSON } from "../api";
import { formatCurrency } from "../utils/currency";

const hhmm = (t) => new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

// Last hour at 2-minute resolution: SPIKE / GROWING alerts + 30-minute forecast (backend: finops/live.py)
export default function LiveTimeline({ currency, onStatus }) {
  const [data, setData] = useState(null);
  const [pick, setPick] = useState(null);

  const load = useCallback(async () => {
    try {
      const d = await getJSON("/live/timeline?minutes=60");
      setData(d);
      onStatus?.(Object.fromEntries((d.workloads || []).map((w) => [`${w.namespace}/${w.workload}`, w.status])));
    } catch {
      setData(null);
    }
  }, [onStatus]);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  const workloads = data?.workloads || [];
  const key = (w) => `${w.namespace}/${w.workload}`;
  const selected = workloads.find((w) => key(w) === pick) || workloads[0];

  const rows = useMemo(() => {
    if (!selected) return [];
    const r = selected.series.map((p) => ({ t: p.t, actual: p.rate, spike: p.anomaly ? p.rate : null }));
    if (r.length) r[r.length - 1].forecast = r[r.length - 1].actual;
    return [...r, ...selected.forecast.map((f) => ({ t: f.t, forecast: f.rate }))];
  }, [selected]);

  if (!data?.connected || !workloads.length) return null;

  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Activity className="w-4 h-4 text-purple-400" /> Live cost timeline (last 60 min, every 2 min)
        </h2>
        <p className="text-xs text-slate-400">
          Spike = cost jumps above 1.5× its own normal · Growing = keeps rising · dashed line = next 30 minutes
        </p>
      </div>

      {data.events.map((e) => (
        <button
          key={`${e.type}-${e.namespace}-${e.workload}`}
          onClick={() => setPick(`${e.namespace}/${e.workload}`)}
          className={`w-full text-left rounded border p-3 text-xs flex items-center gap-2 ${
            e.type === "SPIKE" ? "border-rose-800 bg-rose-950/40 text-rose-200" : "border-amber-800 bg-amber-950/30 text-amber-200"
          }`}
        >
          {e.type === "SPIKE" ? <Zap className="w-4 h-4" /> : <TrendingUp className="w-4 h-4" />}
          <b>{e.type === "SPIKE" ? "COST SPIKE" : "COST GROWING"}</b>
          <span>
            {e.namespace}/{e.workload}{" "}
            {e.type === "SPIKE"
              ? `is costing ${e.ratio?.toFixed(1)}× its normal rate since ${hhmm(e.since)}`
              : `cost is rising about ${Math.round(e.growth_pct_per_hour)}% per hour`}
          </span>
          <span className="ml-auto underline">show</span>
        </button>
      ))}

      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <select
            value={selected ? key(selected) : ""}
            onChange={(e) => setPick(e.target.value)}
            className="bg-[#161619] border border-[#28282e] rounded px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-blue-500"
          >
            {workloads.map((w) => (
              <option key={key(w)} value={key(w)}>
                {key(w)}{w.status ? `  —  ${w.status}` : ""}
              </option>
            ))}
          </select>
          {selected && (
            <div className="flex flex-wrap gap-4 text-xs">
              <span className="text-slate-400">Now <b className="text-white">{formatCurrency(selected.latest_rate, currency)}/h</b></span>
              <span className="text-slate-400">Normal <b className="text-white">{formatCurrency(selected.baseline_rate, currency)}/h</b></span>
              <span className="text-slate-400">Next 30 min <b className="text-white">{formatCurrency(selected.next_30min_cost, currency)}</b></span>
              <span className="text-slate-400">At this rate / day <b className="text-white">{formatCurrency(selected.projected_day_cost, currency)}</b></span>
            </div>
          )}
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows}>
              <CartesianGrid stroke="#28282e" vertical={false} />
              <XAxis dataKey="t" tickFormatter={hhmm} tick={{ fill: "#71717A", fontSize: 10 }} minTickGap={24} />
              <YAxis tickFormatter={(v) => formatCurrency(v, currency)} tick={{ fill: "#71717A", fontSize: 10 }} width={70} />
              <Tooltip
                labelFormatter={hhmm}
                formatter={(v, n) => [`${formatCurrency(v, currency)}/h`, n]}
                contentStyle={{ background: "#1f2027", border: "1px solid #28282e", fontSize: 12 }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line isAnimationActive={false} type="monotone" dataKey="actual" name="Cost per hour" stroke="#3B82F6" strokeWidth={2} dot={false} />
              <Line isAnimationActive={false} type="monotone" dataKey="forecast" name="Forecast (30 min)" stroke="#A78BFA" strokeWidth={2} strokeDasharray="6 4" dot={false} />
              <Scatter isAnimationActive={false} dataKey="spike" name="Spike" fill="#F43F5E" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
