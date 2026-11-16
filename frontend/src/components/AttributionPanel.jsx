import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { Users } from "lucide-react";
import { getJSON, fmtPct } from "../api";
import { formatCurrency } from "../utils/currency";

const COLORS = ["#3B82F6", "#8B5CF6", "#10B981", "#F59E0B", "#EC4899", "#06B6D4", "#84CC16", "#F97316", "#A855F7", "#14B8A6"];
const IDLE_COLOR = "#52525b";

// O1 — "who is spending how much?" by team / namespace / workload, incl. idle cluster cost.
export default function AttributionPanel({ currency }) {
  const [by, setBy] = useState("team");
  const [data, setData] = useState(null);

  useEffect(() => {
    getJSON(`/attribution?by=${by}`).then(setData).catch(() => setData(null));
  }, [by]);

  if (!data) return null;
  const isIdle = (k) => k === "__idle__" || k === "__idle__/__idle__";
  const items = data.items.map((i) => ({ ...i, label: isIdle(i.key) ? "Idle (unallocated cluster capacity)" : i.key }));

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Users className="w-4 h-4 text-blue-400" /> Cost Attribution — who pays for what
          </h2>
          <p className="text-xs text-slate-400">
            {data.start || "all data"} · total {formatCurrency(data.total_cost, currency)} ·{" "}
            <span className="text-amber-300">idle {fmtPct(data.idle_share_pct)} of the bill</span>
          </p>
        </div>
        <div className="flex gap-1">
          {["team", "namespace", "workload"].map((k) => (
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

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 bg-[#1a1a1e] border border-[#28282e] rounded-md p-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie isAnimationActive={false} data={items} dataKey="cost" nameKey="label" innerRadius="55%" outerRadius="85%" paddingAngle={1}>
                {items.map((it, i) => (
                  <Cell key={it.key} fill={isIdle(it.key) ? IDLE_COLOR : COLORS[i % COLORS.length]} stroke="#1a1a1e" />
                ))}
              </Pie>
              <Tooltip
                formatter={(v, n) => [formatCurrency(v, currency), n]}
                contentStyle={{ background: "#1f2027", border: "1px solid #28282e", fontSize: 12 }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="lg:col-span-3 bg-[#1a1a1e] border border-[#28282e] rounded-md overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-[#28282e] text-slate-300 uppercase text-[10px] font-bold bg-[#16171d]">
                <th className="py-2.5 px-4 capitalize">{by}</th>
                <th className="py-2.5 px-4 text-right">Cost</th>
                <th className="py-2.5 px-4 text-right">Share</th>
                <th className="py-2.5 px-4 text-right">Efficiency</th>
                <th className="py-2.5 px-4 text-right">Workloads</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#28282e]">
              {items.map((it, i) => (
                <tr key={it.key} className="hover:bg-[#202127]">
                  <td className="py-2 px-4 font-semibold text-white flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-sm" style={{ background: isIdle(it.key) ? IDLE_COLOR : COLORS[i % COLORS.length] }} />
                    {it.label}
                  </td>
                  <td className="py-2 px-4 text-right font-mono">{formatCurrency(it.cost, currency)}</td>
                  <td className="py-2 px-4 text-right font-mono">{fmtPct(it.share_pct)}</td>
                  <td className={`py-2 px-4 text-right font-mono ${it.efficiency_pct !== null && it.efficiency_pct < 20 ? "text-rose-400" : ""}`}>
                    {isIdle(it.key) ? "—" : fmtPct(it.efficiency_pct)}
                  </td>
                  <td className="py-2 px-4 text-right">{isIdle(it.key) ? "—" : it.workloads}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
