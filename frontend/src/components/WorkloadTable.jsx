import { formatCurrency } from "../utils/currency";
import { useState } from "react";
import { Search } from "lucide-react";

export default function WorkloadTable({ costs, summary, currency = "USD" }) {
  const [filterText, setFilterText] = useState("");

  const appStats = {};
  (costs || []).forEach((row) => {
    if (!appStats[row.app_name]) {
      appStats[row.app_name] = {
        app_name: row.app_name,
        cpu_requested: row.cpu_requested || 0,
        cpu_used: row.cpu_used || 0,
        ram_requested: row.ram_requested || 0,
        ram_used: row.ram_used || 0,
        total_cost: 0,
        efficiency_sum: 0,
        count: 0,
      };
    }
    appStats[row.app_name].total_cost += Number(row.total_cost) || 0;
    if (row.efficiency_pct !== null) {
      appStats[row.app_name].efficiency_sum += Number(row.efficiency_pct) || 0;
      appStats[row.app_name].count += 1;
    }
  });

  const rows = Object.values(appStats).map((item) => ({
    ...item,
    avg_efficiency: item.count > 0 ? item.efficiency_sum / item.count : 0,
  }));

  const filtered = rows.filter((r) =>
    r.app_name.toLowerCase().includes(filterText.toLowerCase())
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white">
            Workload Allocation Breakdown
          </h2>
          <p className="text-xs text-slate-400">
            Kubernetes controllers with CPU/RAM metrics and cost efficiency
          </p>
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="Filter workloads..."
            className="w-full bg-[#1a1a1e] text-slate-100 text-xs rounded pl-8 pr-3 py-1.5 border border-[#28282e] focus:border-blue-500 focus:outline-none placeholder-slate-400 font-medium"
          />
        </div>
      </div>

      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-[#28282e] text-slate-300 uppercase text-[10px] font-bold tracking-wider bg-[#16171d]">
                <th className="py-3 px-4">Name / Controller</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4 text-right">CPU (Req / Used)</th>
                <th className="py-3 px-4 text-right">RAM (Req / Used)</th>
                <th className="py-3 px-4 text-right">Efficiency</th>
                <th className="py-3 px-4 text-right">Total Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#28282e]">
              {filtered.map((row, idx) => (
                <tr
                  key={idx}
                  className="hover:bg-[#202127] transition-colors"
                >
                  <td className="py-3.5 px-4 font-bold text-white flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                    <span>{row.app_name}</span>
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#252630] text-slate-300 font-semibold">
                      Deployment
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono font-medium text-slate-200">
                    {row.cpu_requested.toFixed(1)} / {row.cpu_used.toFixed(1)} cores
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono font-medium text-slate-200">
                    {row.ram_requested.toFixed(1)} / {row.ram_used.toFixed(1)} GiB
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono font-bold">
                    <span
                      className={
                        row.avg_efficiency >= 70
                          ? "text-emerald-600 dark:text-emerald-400"
                          : row.avg_efficiency >= 40
                          ? "text-amber-600 dark:text-amber-400"
                          : "text-rose-600 dark:text-rose-400"
                      }
                    >
                      {row.avg_efficiency.toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono font-extrabold text-white">
                    {formatCurrency(row.total_cost, currency)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
