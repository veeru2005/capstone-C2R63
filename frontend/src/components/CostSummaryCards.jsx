import { formatCurrency } from "../utils/currency";
import { Wallet, Gauge, PiggyBank, Moon } from "lucide-react";

// Four numbers a mentor understands in 5 seconds.
export default function CostSummaryCards({ summary, recommendations = [], currency = "USD" }) {
  const total = summary?.total_cost ?? 0;
  const idle = summary?.idle_cost ?? 0;
  const savings = recommendations.reduce((s, r) => s + (Number(r.estimated_savings) || 0), 0);
  const actionable = recommendations.filter((r) => r.recommendation !== "OK").length;

  const cards = [
    {
      label: "Total cluster cost",
      value: formatCurrency(total, currency),
      sub: summary?.start ? `${summary.start} – ${summary.end}` : "",
      icon: Wallet,
      color: "text-blue-400",
    },
    {
      label: "Paid for but unused (idle capacity)",
      value: formatCurrency(idle, currency),
      sub: total ? `${((100 * idle) / total).toFixed(1)}% of the bill` : "",
      icon: Moon,
      color: "text-amber-400",
    },
    {
      label: "Avg resource efficiency",
      value: summary?.avg_efficiency != null ? `${Number(summary.avg_efficiency).toFixed(1)}%` : "—",
      sub: "used ÷ requested, cost-weighted",
      icon: Gauge,
      color: "text-purple-400",
    },
    {
      label: "Potential savings / month",
      value: formatCurrency(savings, currency),
      sub: `${actionable} actionable recommendation(s)`,
      icon: PiggyBank,
      color: "text-emerald-400",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map(({ label, value, sub, icon: Icon, color }) => (
        <div key={label} className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-4">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">{label}</span>
            <Icon className={`w-4 h-4 ${color}`} />
          </div>
          <div className="text-2xl font-extrabold text-white mt-2">{value}</div>
          <div className="text-[11px] text-slate-500 mt-1">{sub}</div>
        </div>
      ))}
    </div>
  );
}
