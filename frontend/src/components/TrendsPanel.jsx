import { useEffect, useState } from "react";
import { Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart } from "recharts";
import { TrendingUp, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { getJSON, fmtPct } from "../api";
import { formatCurrency } from "../utils/currency";

const COLORS = ["#3B82F6", "#8B5CF6", "#10B981", "#F59E0B", "#EC4899", "#06B6D4", "#84CC16", "#F97316", "#A855F7", "#14B8A6"];

function Delta({ v }) {
  if (v === null || v === undefined) return <span className="text-slate-500">—</span>;
  const up = v > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-0.5 font-mono ${up ? "text-rose-400" : "text-emerald-400"}`}>
      <Icon className="w-3 h-3" />
      {fmtPct(Math.abs(v))}
    </span>
  );
}

// O2 reference — spend visualisation and trend analysis.
export default function TrendsPanel({ currency, compact = false }) {
  const [by, setBy] = useState("team");
  const [data, setData] = useState(null);

  useEffect(() => {
    getJSON(`/trends?by=${by}`).then(setData).catch(() => setData(null));
  }, [by]);

  if (!data || !data.series?.length) return null;
  const keys = data.groups.map((g) => g.key);
  const series = compact ? data.series.slice(-30) : data.series;
  const t = data.total;

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-blue-400" /> Spend Trend {compact ? "(last 30 days)" : `(${data.days} days)`}
          </h2>
          <p className="text-xs text-slate-400">Daily cost stacked by {by} · dashed line = 7-day moving average</p>
        </div>
        <div className="flex gap-1">
          {["team", "namespace"].map((k) => (
            <button
              key={k}
              onClick={() => setBy(k)}
              className={`px-3 py-1.5 rounded text-xs font-semibold capitalize ${
                by === k ? "bg-blue-600 text-white" : "bg-[#1a1a1e] border border-[#28282e] text-slate-300"
              }`}
            >
              By {k}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          ["Last 7 days", formatCurrency(t.last_7d, currency)],
          ["Week-over-week", <Delta key="d" v={t.wow_change_pct} />],
          ["Monthly run-rate", formatCurrency(t.run_rate_monthly, currency)],
          ["Trend (per day)", `${t.slope_per_day >= 0 ? "+" : ""}${formatCurrency(t.slope_per_day, currency)}`],
        ].map(([label, val]) => (
          <div key={label} className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">{label}</div>
            <div className="text-lg font-bold text-white mt-1">{val}</div>
          </div>
        ))}
      </div>

      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-4 h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={series}>
            <CartesianGrid stroke="#28282e" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "#71717A", fontSize: 10 }} tickFormatter={(d) => d.slice(5)} minTickGap={20} />
            <YAxis tick={{ fill: "#71717A", fontSize: 10 }} tickFormatter={(v) => formatCurrency(v, currency)} width={70} />
            <Tooltip
              formatter={(v, n) => [formatCurrency(v, currency), n]}
              contentStyle={{ background: "#1f2027", border: "1px solid #28282e", fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {keys.map((k, i) => (
              <Area isAnimationActive={false} key={k} type="monotone" dataKey={k} stackId="1" stroke={COLORS[i % COLORS.length]} fill={COLORS[i % COLORS.length]} fillOpacity={0.35} />
            ))}
            <Line isAnimationActive={false} type="monotone" dataKey="ma7" name="7-day avg (total)" stroke="#f4f4f5" strokeDasharray="5 4" dot={false} strokeWidth={1.5} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {!compact && (
        <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-[#28282e] text-slate-300 uppercase text-[10px] font-bold bg-[#16171d]">
                <th className="py-2.5 px-4 capitalize">{by}</th>
                <th className="py-2.5 px-4 text-right">Avg / day</th>
                <th className="py-2.5 px-4 text-right">Last 7 days</th>
                <th className="py-2.5 px-4 text-right">Week-over-week</th>
                <th className="py-2.5 px-4 text-right">Next 30 days (linear)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#28282e]">
              {data.groups.map((g) => (
                <tr key={g.key} className="hover:bg-[#202127]">
                  <td className="py-2 px-4 font-semibold text-white">{g.key}</td>
                  <td className="py-2 px-4 text-right font-mono">{formatCurrency(g.avg_daily, currency)}</td>
                  <td className="py-2 px-4 text-right font-mono">{formatCurrency(g.last_7d, currency)}</td>
                  <td className="py-2 px-4 text-right"><Delta v={g.wow_change_pct} /></td>
                  <td className="py-2 px-4 text-right font-mono">{formatCurrency(g.projected_30d, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
