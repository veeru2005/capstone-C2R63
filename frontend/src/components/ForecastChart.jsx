import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, Sparkles } from "lucide-react";

const COLORS = [
  "#06B6D4", "#8B5CF6", "#10B981", "#F59E0B", "#EC4899", "#3B82F6",
];

function ForecastTooltip({ active, payload, label, isDark }) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#1f2027] border border-finops-border rounded-lg p-3.5 shadow-2xl text-xs font-sans">
        <div className="border-b border-finops-border/80 pb-2 mb-2">
          <span className="font-semibold text-slate-300">{label}</span>
        </div>
        <div className="space-y-1.5">
          {payload.map((entry, idx) => (
            <div key={`item-${idx}`} className="flex items-center justify-between gap-6">
              <span className="flex items-center gap-2 text-slate-300">
                <span
                  className="w-2.5 h-2.5 rounded-sm inline-block"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="truncate max-w-[140px]">{entry.name}:</span>
              </span>
              <span className="font-semibold text-white font-mono">
                ${Number(entry.value).toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return null;
}

export default function ForecastChart({ costData, forecastData, isDark = true }) {
  if ((!costData || costData.length === 0) && (!forecastData || forecastData.length === 0)) {
    return (
      <div className="bg-finops-card border border-finops-border rounded-lg p-10 text-center">
        No forecast data available.
      </div>
    );
  }

  const appNames = [
    ...new Set([
      ...(costData || []).map((r) => r.app_name),
      ...(forecastData || []).map((r) => r.app_name),
    ]),
  ];

  const byDate = {};

  (costData || []).forEach((row) => {
    if (!byDate[row.date]) byDate[row.date] = { date: row.date };
    byDate[row.date][`${row.app_name}_hist`] = row.total_cost;
  });

  (forecastData || []).forEach((row) => {
    if (!byDate[row.date]) byDate[row.date] = { date: row.date };
    byDate[row.date][`${row.app_name}_fc`] = row.forecast_value;
  });

  const chartData = Object.values(byDate).sort(
    (a, b) => new Date(a.date) - new Date(b.date)
  );

  const gridColor = isDark ? "#262730" : "#F1F5F9";
  const axisColor = isDark ? "#71717A" : "#94A3B8";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-200">
              Cost Forecast (seasonal + trend model, 14 days)
            </h2>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">
              3-Day Horizon
            </span>
          </div>
          <p className="text-xs text-finops-muted">
            <span className="font-semibold">Solid Line</span> = Historical Telemetry &nbsp;|&nbsp;
            <span className="font-semibold">Dashed Line</span> = Forecasted Run-Rate
          </p>
        </div>
      </div>

      <div className="bg-finops-card border border-finops-border rounded-lg p-5 shadow-sm">
        <div className="h-[320px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 15, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: axisColor }}
                stroke={gridColor}
              />
              <YAxis
                tick={{ fontSize: 11, fill: axisColor }}
                tickFormatter={(v) => `$${v}`}
                stroke={gridColor}
              />
              <Tooltip content={<ForecastTooltip isDark={isDark} />} />
              <Legend
                wrapperStyle={{ paddingTop: "14px", fontSize: "11px" }}
                formatter={(value) => (
                  <span className="text-slate-300 font-medium px-1">
                    {value}
                  </span>
                )}
              />

              {appNames.map((name, idx) => {
                const color = COLORS[idx % COLORS.length];
                return [
                  <Line
                    key={`${name}_hist`}
                    type="monotone"
                    dataKey={`${name}_hist`}
                    name={`${name} (actual)`}
                    stroke={color}
                    strokeWidth={2}
                    dot={{ r: 2 }}
                    connectNulls
                  />,
                  <Line
                    key={`${name}_fc`}
                    type="monotone"
                    dataKey={`${name}_fc`}
                    name={`${name} (forecast)`}
                    stroke={color}
                    strokeWidth={2}
                    strokeDasharray="5 4"
                    dot={false}
                    connectNulls
                  />,
                ];
              })}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
