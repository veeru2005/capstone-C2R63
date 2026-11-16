import { formatCurrency } from "../utils/currency";
import { useState } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  BarChart2,
  LineChart as LineChartIcon,
  SlidersHorizontal,
  List,
  Maximize2,
  MoreVertical,
  ChevronDown,
} from "lucide-react";

const COLORS = [
  "#06B6D4", // Cyan
  "#8B5CF6", // Purple
  "#10B981", // Emerald
  "#F59E0B", // Amber
  "#EC4899", // Pink
  "#3B82F6", // Blue
];

function FinOpsTooltip({ active, payload, label, currency = "USD" }) {
  if (active && payload && payload.length) {
    const totalForDay = payload.reduce((acc, p) => acc + (Number(p.value) || 0), 0);
    return (
      <div className="bg-[#1f2027] border border-[#28282e] rounded p-3 shadow-2xl text-xs font-sans">
        <div className="flex items-center justify-between border-b border-[#28282e] pb-1.5 mb-2 gap-6">
          <span className="font-bold text-white">{label}</span>
          <span className="font-extrabold text-blue-600 text-cyan-400 font-mono">
            Total: {formatCurrency(totalForDay, currency)}
          </span>
        </div>
        <div className="space-y-1">
          {payload.map((entry, idx) => (
            <div key={`tooltip-${idx}`} className="flex items-center justify-between gap-6">
              <span className="flex items-center gap-2 text-slate-300">
                <span
                  className="w-2.5 h-2.5 rounded-sm inline-block flex-shrink-0"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="truncate max-w-[140px] font-medium">{entry.name}</span>
              </span>
              <span className="font-bold text-white font-mono">
                {formatCurrency(Number(entry.value), currency)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return null;
}

export default function CostAllocationChart({ data, isDark = false, currency = "USD" }) {
  const [chartType, setChartType] = useState("bar");
  const [windowVal, setWindowVal] = useState("Last 7 days");
  const [aggregateVal, setAggregateVal] = useState("Namespace");
  const [granularityVal, setGranularityVal] = useState("Daily");
  const [includeIdle, setIncludeIdle] = useState(true);
  const [includeUnallocated, setIncludeUnallocated] = useState(true);

  if (!data || data.length === 0) {
    return (
      <div className="bg-[#1a1a1e] border border-[#28282e] rounded p-12 text-center text-slate-400 text-xs">
        No allocation data available.
      </div>
    );
  }

  const appNames = [...new Set(data.map((r) => r.app_name))];

  const byDate = {};
  data.forEach((row) => {
    if (!byDate[row.date]) byDate[row.date] = { date: row.date };
    byDate[row.date][row.app_name] = row.total_cost;
  });

  const chartData = Object.values(byDate).sort(
    (a, b) => new Date(a.date) - new Date(b.date)
  );

  const gridColor = isDark ? "#28282e" : "#E2E8F0";
  const axisColor = isDark ? "#A1A1AA" : "#64748B";

  return (
    <div className="space-y-3">
      {/* Top Title & View Switcher Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white">
            Cost Allocation
          </h2>
          <p className="text-xs text-slate-400">
            Cost breakdown by cluster, namespace, pod, or other dimension
          </p>
        </div>

        {/* View Switcher buttons */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setChartType("bar")}
            className={`p-2 rounded text-xs transition-colors ${ chartType === "bar" ? "bg-blue-600 text-white shadow-sm" : "bg-white bg-[#1a1a1e] border border-[#28282e] hover:text-white" }`}
            title="Bar Chart"
          >
            <BarChart2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setChartType("line")}
            className={`p-2 rounded text-xs transition-colors ${ chartType === "line" ? "bg-blue-600 text-white shadow-sm" : "bg-white bg-[#1a1a1e] border border-[#28282e] hover:text-white" }`}
            title="Line Chart"
          >
            <LineChartIcon className="w-4 h-4" />
          </button>
          <button
            className="p-2 rounded bg-[#1a1a1e] border border-[#28282e] hover:text-white transition-colors"
            title="Configure aggregation"
          >
            <SlidersHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter Row */}
      <div className="flex flex-wrap items-center gap-4 text-xs">
        {/* Window */}
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-slate-400">Window</label>
          <div className="relative">
            <select
              value={windowVal}
              onChange={(e) => setWindowVal(e.target.value)}
              className="appearance-none bg-[#1a1a1e] border border-[#28282e] rounded px-3 py-1.5 pr-8 text-xs font-medium text-slate-100 focus:outline-none focus:border-blue-500 cursor-pointer min-w-[140px] shadow-sm"
            >
              <option>Last 7 days</option>
              <option>Last 30 days</option>
              <option>Today</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Aggregate by */}
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-slate-400">Aggregate by</label>
          <div className="relative">
            <select
              value={aggregateVal}
              onChange={(e) => setAggregateVal(e.target.value)}
              className="appearance-none bg-[#1a1a1e] border border-[#28282e] rounded px-3 py-1.5 pr-8 text-xs font-medium text-slate-100 focus:outline-none focus:border-blue-500 cursor-pointer min-w-[160px] shadow-sm"
            >
              <option>Namespace</option>
              <option>Controller</option>
              <option>Application</option>
              <option>Cluster</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Granularity */}
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-slate-400">Granularity</label>
          <div className="relative">
            <select
              value={granularityVal}
              onChange={(e) => setGranularityVal(e.target.value)}
              className="appearance-none bg-[#1a1a1e] border border-[#28282e] rounded px-3 py-1.5 pr-8 text-xs font-medium text-slate-100 focus:outline-none focus:border-blue-500 cursor-pointer min-w-[140px] shadow-sm"
            >
              <option>Daily</option>
              <option>Hourly</option>
              <option>Cumulative</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Checkbox: Include idle costs */}
        <div className="flex items-center gap-2 self-end pb-2">
          <input
            type="checkbox"
            id="alloc-idle"
            checked={includeIdle}
            onChange={(e) => setIncludeIdle(e.target.checked)}
            className="w-3.5 h-3.5 rounded text-blue-600 bg-[#1a1a1e] border-[#28282e] focus:ring-blue-500 cursor-pointer"
          />
          <label htmlFor="alloc-idle" className="text-xs font-medium text-slate-300 cursor-pointer select-none">
            Include idle costs
          </label>
        </div>

        {/* Checkbox: Include unallocated costs */}
        <div className="flex items-center gap-2 self-end pb-2">
          <input
            type="checkbox"
            id="alloc-unalloc"
            checked={includeUnallocated}
            onChange={(e) => setIncludeUnallocated(e.target.checked)}
            className="w-3.5 h-3.5 rounded text-blue-600 bg-[#1a1a1e] border-[#28282e] focus:ring-blue-500 cursor-pointer"
          />
          <label htmlFor="alloc-unalloc" className="text-xs font-medium text-slate-300 cursor-pointer select-none">
            Include unallocated costs
          </label>
        </div>
      </div>

      {/* Main Chart Box */}
      <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md overflow-hidden shadow-sm">
        {/* Subheader bar */}
        <div className="px-4 py-2.5 border-b border-[#28282e] flex items-center justify-between text-xs">
          <span className="font-bold text-white">
            Last 7 days by {aggregateVal.toLowerCase()} (Daily)
          </span>

          <div className="flex items-center gap-3 text-slate-400">
            <List className="w-3.5 h-3.5 hover:text-white cursor-pointer" />
            <Maximize2 className="w-3.5 h-3.5 hover:text-white cursor-pointer" />
            <MoreVertical className="w-3.5 h-3.5 hover:text-white cursor-pointer" />
          </div>
        </div>

        {/* Chart */}
        <div className="p-4 h-[320px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            {chartType === "bar" ? (
              <BarChart data={chartData} margin={{ top: 15, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: axisColor, fontWeight: 500 }}
                  stroke={gridColor}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: axisColor, fontWeight: 500 }}
                  tickFormatter={(v) => formatCurrency(v, currency)}
                  stroke={gridColor}
                />
                <Tooltip content={<FinOpsTooltip currency={currency} />} />
                <Legend
                  wrapperStyle={{ paddingTop: "12px", fontSize: "11px" }}
                  formatter={(value) => (
                    <span className="text-slate-200 font-semibold px-1">
                      {value}
                    </span>
                  )}
                />
                {appNames.map((name, idx) => (
                  <Bar
                    key={name}
                    dataKey={name}
                    stackId="a"
                    fill={COLORS[idx % COLORS.length]}
                    radius={idx === appNames.length - 1 ? [2, 2, 0, 0] : [0, 0, 0, 0]}
                  />
                ))}
              </BarChart>
            ) : (
              <LineChart data={chartData} margin={{ top: 15, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: axisColor, fontWeight: 500 }}
                  stroke={gridColor}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: axisColor, fontWeight: 500 }}
                  tickFormatter={(v) => formatCurrency(v, currency)}
                  stroke={gridColor}
                />
                <Tooltip content={<FinOpsTooltip currency={currency} />} />
                <Legend
                  wrapperStyle={{ paddingTop: "12px", fontSize: "11px" }}
                  formatter={(value) => (
                    <span className="text-slate-200 font-semibold px-1">
                      {value}
                    </span>
                  )}
                />
                {appNames.map((name, idx) => (
                  <Line
                    key={name}
                    type="monotone"
                    dataKey={name}
                    stroke={COLORS[idx % COLORS.length]}
                    strokeWidth={2.5}
                    dot={{ r: 2.5 }}
                    activeDot={{ r: 5 }}
                  />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
