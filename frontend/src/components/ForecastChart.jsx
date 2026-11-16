import { useMemo, useState } from "react";
import { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { TrendingUp } from "lucide-react";
import { formatCurrency } from "../utils/currency";

const TOTAL = "__all__";

// One workload (or the cluster total) at a time: last 30 days actual + next 14 days forecast.
export default function ForecastChart({ costData = [], forecastData = [], currency = "USD" }) {
  const apps = useMemo(
    () => [...new Set(forecastData.map((r) => `${r.namespace}/${r.app_name}`))].sort(),
    [forecastData]
  );
  const [pick, setPick] = useState(TOTAL);

  const rows = useMemo(() => {
    const match = (r) => pick === TOTAL || `${r.namespace}/${r.app_name}` === pick;
    const byDate = {};
    costData.filter(match).forEach((r) => {
      byDate[r.date] = byDate[r.date] || { date: r.date };
      byDate[r.date].actual = (byDate[r.date].actual || 0) + (Number(r.total_cost) || 0);
    });
    forecastData.filter(match).forEach((r) => {
      byDate[r.date] = byDate[r.date] || { date: r.date };
      const d = byDate[r.date];
      d.forecast = (d.forecast || 0) + r.forecast_value;
      d.lo = (d.lo || 0) + (r.lower ?? r.forecast_value);
      d.hi = (d.hi || 0) + (r.upper ?? r.forecast_value);
    });
    const out = Object.values(byDate).sort((a, b) => (a.date < b.date ? -1 : 1));
    out.forEach((d) => {
      if (d.lo !== undefined) d.band = [d.lo, d.hi];
    });
    // join the two lines: last actual day also starts the forecast line
    const lastActual = [...out].reverse().find((d) => d.actual !== undefined);
    if (lastActual && lastActual.forecast === undefined) lastActual.forecast = lastActual.actual;
    return out;
  }, [costData, forecastData, pick]);

  if (!forecastData.length) {
    return <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-10 text-center text-slate-400">No forecast yet — run the pipeline.</div>;
  }

  const next14 = rows.filter((r) => r.actual === undefined).reduce((s, r) => s + (r.forecast || 0), 0);
  const last14 = rows.filter((r) => r.actual !== undefined).slice(-14).reduce((s, r) => s + r.actual, 0);
  const change = last14 ? ((next14 - last14) / last14) * 100 : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-purple-400" /> Cost Forecast — next 14 days
          </h2>
          <p className="text-xs text-slate-400">Solid = actual (last 30 days) · dashed = forecast · shaded = likely range</p>
        </div>
        <select
          value={pick}
          onChange={(e) => setPick(e.target.value)}
          className="bg-[#1a1a1e] border border-[#28282e] rounded px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-blue-500"
        >
          <option value={TOTAL}>Whole cluster (all workloads)</option>
          {apps.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          ["Last 14 days (actual)", formatCurrency(last14, currency)],
          ["Next 14 days (forecast)", formatCurrency(next14, currency)],
          ["Change", change === null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(1)}%`],
        ].map(([l, v]) => (
          <div key={l} className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">{l}</div>
            <div className="text-lg font-bold text-white mt-1">{v}</div>
          </div>
        ))}
      </div>

      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-4 h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows}>
            <CartesianGrid stroke="#28282e" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "#71717A", fontSize: 10 }} tickFormatter={(d) => d.slice(5)} minTickGap={20} />
            <YAxis tick={{ fill: "#71717A", fontSize: 10 }} tickFormatter={(v) => formatCurrency(v, currency)} width={70} />
            <Tooltip
              formatter={(v, n) => [Array.isArray(v) ? `${formatCurrency(v[0], currency)} – ${formatCurrency(v[1], currency)}` : formatCurrency(v, currency), n]}
              contentStyle={{ background: "#1f2027", border: "1px solid #28282e", fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Area isAnimationActive={false} dataKey="band" name="Likely range" stroke="none" fill="#8B5CF6" fillOpacity={0.15} />
            <Line isAnimationActive={false} type="monotone" dataKey="actual" name="Actual" stroke="#3B82F6" strokeWidth={2} dot={false} />
            <Line isAnimationActive={false} type="monotone" dataKey="forecast" name="Forecast" stroke="#A78BFA" strokeWidth={2} strokeDasharray="6 4" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
