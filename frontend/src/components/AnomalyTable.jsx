import { ShieldAlert } from "lucide-react";

export default function AnomalyTable({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-8 text-center text-slate-400">
        <ShieldAlert className="w-8 h-8 mx-auto text-emerald-500 mb-2 opacity-80" />
        <p className="font-bold text-slate-200 text-sm">No cost anomalies detected</p>
        <p className="text-xs mt-0.5">All Kubernetes workloads are operating within standard variance threshold</p>
      </div>
    );
  }

  // Sort newest first
  const sorted = [...data].sort((a, b) => new Date(b.date) - new Date(a.date));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-white">
              Workload Anomaly Detection
            </h2>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold text-rose-600 text-rose-400 border border-rose-500/30">
              {data.length} Spikes
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Statistical Z-Score outlier detection comparing actual daily cost vs historical baseline
          </p>
        </div>
      </div>

      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-[#28282e] text-slate-300 uppercase text-[10px] font-bold tracking-wider bg-[#16171d]">
                <th className="py-3 px-4">Observed Date</th>
                <th className="py-3 px-4">Kubernetes Workload</th>
                <th className="py-3 px-4">Controller</th>
                <th className="py-3 px-4 text-right">Cost Spike</th>
                <th className="py-3 px-4 text-center">Z-Score</th>
                <th className="py-3 px-4 text-right">Severity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#28282e]">
              {sorted.map((row, idx) => {
                const z = Number(row.z_score);
                const isHigh = z >= 2.5;
                return (
                  <tr
                    key={idx}
                    className="hover:bg-[#202127] transition-colors"
                  >
                    <td className="py-3 px-4 font-mono font-medium text-slate-300 whitespace-nowrap">
                      {row.date}
                    </td>
                    <td className="py-3 px-4 font-bold text-white flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full"></span>
                      <span>{row.app_name}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#252630] text-slate-300 font-semibold">
                        Deployment
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-extrabold text-rose-400">
                      ${Number(row.total_cost).toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-center font-mono font-bold text-slate-100">
                      +{z.toFixed(2)}σ
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${ isHigh ? "bg-rose-500/20 text-rose-700 text-rose-400 border border-rose-500/40" : "bg-amber-500/20 text-amber-700 text-amber-400 border border-amber-500/40" }`}
                      >
                        {isHigh ? "Critical" : "Warning"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
