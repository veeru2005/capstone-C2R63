import { Info } from "lucide-react";

// Explains why a daily-history page can look empty (e.g. a fresh live cluster with 1 day of data)
export default function HistoryNote({ health, minDays, what }) {
  if (!health?.data_start || !health?.data_end) return null;
  const days = Math.round((new Date(health.data_end) - new Date(health.data_start)) / 86400000) + 1;
  if (days >= minDays) return null;
  const live = health.data_source === "opencost";
  return (
    <div className="rounded border border-blue-900 bg-blue-950/30 p-3 text-xs text-blue-100 flex gap-2">
      <Info className="w-4 h-4 flex-shrink-0 text-blue-300 mt-0.5" />
      <div>
        <b>Daily {what} needs at least {minDays} days of history — this {live ? "live cluster" : "dataset"} has {days} day{days === 1 ? "" : "s"} so far.</b>
        <div className="text-blue-200/80 mt-0.5">
          {live
            ? "It fills up automatically as the cluster keeps running. For minute-level spikes and a 30-minute forecast right now, use the live timeline below (also on the Live Cluster page). To see the 90-day results, run ./start.sh (demo mode)."
            : "Run ./start.sh to load the 90-day sandbox dataset."}
        </div>
      </div>
    </div>
  );
}
