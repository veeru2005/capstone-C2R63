/**
 * StatCard — displays a FinOps style summary metric.
 * Props:
 *   title      – short label (e.g. "Total Cost")
 *   value      – formatted number/string to display prominently
 *   subvalue   – optional secondary detail (e.g. "7-day window", "vs last week")
 *   icon       – React element or icon string
 *   badge      – optional status pill (e.g. "Optimal", "3 Actions")
 *   variant    – "default" | "cyan" | "emerald" | "amber" | "rose"
 */
export default function StatCard({ title, value, subvalue, icon, badge, variant = "default" }) {
  const variantStyles = {
    default: {
      border: "border-slate-200 dark:border-slate-800",
      iconBg: "bg-blue-50 text-blue-600 dark:bg-blue-950/60 dark:text-blue-400",
      accent: "text-slate-900 dark:text-slate-100",
    },
    cyan: {
      border: "border-cyan-200/80 dark:border-cyan-900/50",
      iconBg: "bg-cyan-50 text-cyan-600 dark:bg-cyan-950/60 dark:text-cyan-400",
      accent: "text-cyan-600 dark:text-cyan-400",
    },
    emerald: {
      border: "border-emerald-200/80 dark:border-emerald-900/50",
      iconBg: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400",
      accent: "text-emerald-600 dark:text-emerald-400",
    },
    amber: {
      border: "border-amber-200/80 dark:border-amber-900/50",
      iconBg: "bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400",
      accent: "text-amber-600 dark:text-amber-400",
    },
    rose: {
      border: "border-rose-200/80 dark:border-rose-900/50",
      iconBg: "bg-rose-50 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400",
      accent: "text-rose-600 dark:text-rose-400",
    },
  };

  const style = variantStyles[variant] || variantStyles.default;

  return (
    <div className={`bg-slate-900/90 rounded-2xl p-5 border ${style.border} shadow-sm shadow-none hover:shadow-md transition-all duration-200 flex flex-col justify-between backdrop-blur-sm relative overflow-hidden group`}>
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            {title}
          </span>
          <p className="text-3xl font-extrabold text-white mt-1.5 tracking-tight font-sans">
            {value}
          </p>
        </div>
        {icon && (
          <div className={`p-2.5 rounded-xl ${style.iconBg} text-xl flex items-center justify-center`}>
            {icon}
          </div>
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
        <span>{subvalue || "Kubernetes Workloads"}</span>
        {badge && (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-800 text-slate-300">
            {badge}
          </span>
        )}
      </div>
    </div>
  );
}
