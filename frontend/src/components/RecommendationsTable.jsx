import { formatCurrency } from "../utils/currency";
import { CheckCircle2 } from "lucide-react";

export default function RecommendationsTable({ data, currency = "USD" }) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-8 text-center text-slate-400">
        <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500 mb-2 opacity-80" />
        <p className="font-bold text-slate-200 text-sm">No optimization recommendations</p>
        <p className="text-xs mt-0.5">All workload allocations are currently optimal</p>
      </div>
    );
  }

  const sorted = [...data].sort((a, b) => b.estimated_savings - a.estimated_savings);
  const totalSavings = sorted.reduce((sum, r) => sum + (Number(r.estimated_savings) || 0), 0);

  const getDiagnosis = (rec) => {
    const r = (rec || "").toUpperCase();
    if (r.includes("IDLE")) {
      return {
        badge: "Idle Workload (0% CPU)",
        action: "Scale pods to 0 / Terminate deployment",
        style: "bg-rose-500/20 text-rose-700 dark:text-rose-400 border-rose-500/30",
      };
    }
    if (r.includes("COMMITMENT")) {
      return {
        badge: "Stable spend → commit",
        action: "Buy 1-year committed use / reserved capacity for the baseline",
        style: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      };
    }
    if (r.includes("RIGHT-SIZE") || r.includes("RIGHTSIZE")) {
      return {
        badge: "Overprovisioned Pods",
        action: "Reduce CPU & RAM requests in Helm/YAML",
        style: "bg-amber-500/20 text-amber-700 dark:text-amber-400 border-amber-500/30",
      };
    }
    return {
      badge: "Optimal Sizing",
      action: "Workload sized within target bounds",
      style: "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
    };
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-white">
              Savings &amp; Rightsizing Recommendations
            </h2>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-700 text-emerald-400 border border-emerald-500/30 font-mono">
              +{formatCurrency(totalSavings, currency)}/mo potential
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Last 30 days · right-size target = p95 usage × 1.3 headroom · system components are never deleted
          </p>
        </div>
      </div>

      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-[#28282e] text-slate-300 uppercase text-[10px] font-bold tracking-wider bg-[#16171d]">
                <th className="py-3 px-4">Application / Workload</th>
                <th className="py-3 px-4">Resource Diagnosis</th>
                <th className="py-3 px-4">Remediation Action</th>
                <th className="py-3 px-4 text-right">Estimated Savings</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#28282e]">
              {sorted.map((row, idx) => {
                const diag = getDiagnosis(row.recommendation);
                const savings = Number(row.estimated_savings) || 0;
                return (
                  <tr
                    key={idx}
                    className="hover:bg-[#202127] transition-colors"
                  >
                    <td className="py-3 px-4 font-bold text-white">
                      {row.namespace && <span className="text-slate-500 font-normal">{row.namespace}/</span>}
                      {row.app_name}
                      {row.confidence && (
                        <div className="text-[10px] font-normal text-slate-500">confidence: {row.confidence}</div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${diag.style}`}
                      >
                        {diag.badge}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-300 font-medium max-w-md">
                      {diag.action}
                      {row.detail && <div className="text-[11px] font-normal text-slate-400 mt-0.5">{row.detail}</div>}
                      {row.safety_note && <div className="text-[11px] font-normal text-amber-300/80 mt-0.5">⚠ {row.safety_note}</div>}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-extrabold">
                      {savings > 0 ? (
                        <span className="text-emerald-600 text-emerald-400">
                          +{formatCurrency(savings, currency)}/mo
                        </span>
                      ) : (
                        <span className="text-slate-600">{formatCurrency(0, currency)}</span>
                      )}
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
