import { ShieldAlert } from "lucide-react";
import { formatCurrency } from "../utils/currency";

// How far above normal the day was, in plain words
function severity(z) {
  if (z >= 10) return ["Very high", "bg-rose-500/20 text-rose-400 border-rose-500/40"];
  if (z >= 5) return ["High", "bg-orange-500/20 text-orange-400 border-orange-500/40"];
  return ["Medium", "bg-amber-500/20 text-amber-400 border-amber-500/40"];
}

export default function AnomalyTable({ data, currency = "USD" }) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-8 text-center text-slate-400">
        <ShieldAlert className="w-8 h-8 mx-auto text-emerald-500 mb-2 opacity-80" />
        <p className="font-bold text-slate-200 text-sm">No cost anomalies detected</p>
        <p className="text-xs mt-0.5">Every workload stayed within its normal range</p>
      </div>
    );
  }

  const sorted = [...data].sort((a, b) => (a.date < b.date ? 1 : -1));

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold text-white">Cost Anomalies</h2>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold text-rose-400 border border-rose-500/30">
            {data.length} spikes
          </span>
        </div>
        <p className="text-xs text-slate-400">
          A day is flagged when its cost is more than 2.5 standard deviations above that workload's last 14 days
        </p>
      </div>

      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead>
            <tr className="border-b border-[#28282e] text-slate-300 uppercase text-[10px] font-bold tracking-wider bg-[#16171d]">
              <th className="py-3 px-4">Date</th>
              <th className="py-3 px-4">Namespace / Workload</th>
              <th className="py-3 px-4 text-right">Cost that day</th>
              <th className="py-3 px-4 text-right">Normal (14-day avg)</th>
              <th className="py-3 px-4 text-right">× normal</th>
              <th className="py-3 px-4 text-right">Z-score</th>
              <th className="py-3 px-4 text-right">Severity</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#28282e]">
            {sorted.map((row) => {
              const z = Number(row.z_score) || 0;
              const ratio = row.baseline_mean ? row.total_cost / row.baseline_mean : null;
              const [label, style] = severity(z);
              return (
                <tr key={`${row.date}-${row.namespace}-${row.app_name}`} className="hover:bg-[#202127]">
                  <td className="py-3 px-4 text-slate-300 whitespace-nowrap">{row.date}</td>
                  <td className="py-3 px-4 font-bold text-white">
                    {row.namespace && <span className="text-slate-500 font-normal">{row.namespace}/</span>}
                    {row.app_name}
                  </td>
                  <td className="py-3 px-4 text-right font-bold text-rose-400">{formatCurrency(row.total_cost, currency)}</td>
                  <td className="py-3 px-4 text-right text-slate-300">
                    {row.baseline_mean != null ? formatCurrency(row.baseline_mean, currency) : "—"}
                  </td>
                  <td className="py-3 px-4 text-right font-bold text-white">{ratio ? `${ratio.toFixed(1)}×` : "—"}</td>
                  <td className="py-3 px-4 text-right text-slate-300">{z.toFixed(1)}</td>
                  <td className="py-3 px-4 text-right">
                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${style}`}>{label}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
