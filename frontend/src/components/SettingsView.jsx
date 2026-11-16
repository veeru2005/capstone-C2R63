import { useState } from "react";
import { ExternalLink, Check, Activity } from "lucide-react";
import { CURRENCIES } from "../utils/currency";

export default function SettingsView({ currency, setCurrency }) {
  const [selectedCurrency, setSelectedCurrency] = useState(currency || "INR");
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setCurrency(selectedCurrency);
    localStorage.setItem("finops_currency", selectedCurrency);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Title & Subtitle matching Screenshot 2 */}
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-xs text-finops-muted mt-1">
          Global preferences applied across dashboards and reports.
        </p>
      </div>

      {/* Card 1: Display */}
      <div className="bg-finops-card border border-finops-border rounded overflow-hidden shadow-sm">
        <div className="px-5 py-3 border-b border-finops-border">
          <h2 className="text-sm font-semibold text-white">Display</h2>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-200 mb-1">
              Default Currency
            </label>
            <p className="text-xs text-finops-muted mb-2">
              Used as the default currency when creating new reports and dashboards.
            </p>
            <select
              value={selectedCurrency}
              onChange={(e) => setSelectedCurrency(e.target.value)}
              className="w-full sm:w-64 bg-finops-input border border-finops-border rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              {Object.values(CURRENCIES).map((c) => (
                <option key={c.code} value={c.code}>
                  {c.code} ({c.symbol}) - {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="pt-2">
            <button
              onClick={handleSave}
              className="px-4 py-2 rounded text-xs font-medium bg-[#282932] hover:bg-[#343542] text-slate-200 transition-colors flex items-center gap-1.5"
            >
              {saved ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Saved!</span>
                </>
              ) : (
                <span>Save changes</span>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Card 2: About */}
      <div className="bg-finops-card border border-finops-border rounded overflow-hidden shadow-sm">
        <div className="px-5 py-3 border-b border-finops-border">
          <h2 className="text-sm font-semibold text-white">About</h2>
        </div>

        <div className="p-5 space-y-4">
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 32 32" className="w-5 h-5 text-emerald-500 fill-current">
              <path d="M16 2L3 9.5v13L16 30l13-7.5v-13L16 2zm0 3.8l8.9 5.1-4 2.3-4.9-2.8-4.9 2.8-4-2.3L16 5.8zM5.6 11.2l3.7 2.1v9.6L5.6 21v-9.8zm12.4 13.9l-4-2.3 4.9-2.8 4.9 2.8-4 2.3zm4.7-4.3v-9.6l3.7-2.1V21l-3.7-.2z" />
            </svg>
            <span className="font-bold text-base text-white">FinOps</span>
          </div>

          <p className="text-xs text-finops-muted leading-relaxed">
            FinOps is a cloud cost optimization platform for measuring and allocating Kubernetes and cloud infrastructure costs in real time.
          </p>

          <div className="pt-2 space-y-2 text-xs">
            <div>
              <a
                href="https://www.opencost.io/docs"
                target="_blank"
                rel="noreferrer"
                className="text-blue-500 hover:text-blue-400 hover:underline flex items-center gap-1.5"
              >
                <span>Documentation</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <div>
              <a
                href="https://github.com/opencost/opencost"
                target="_blank"
                rel="noreferrer"
                className="text-blue-500 hover:text-blue-400 hover:underline flex items-center gap-1.5"
              >
                <span>GitHub Repository</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <div>
              <a
                href="https://cloud-native.slack.com/archives/C03D56FPD44"
                target="_blank"
                rel="noreferrer"
                className="text-blue-500 hover:text-blue-400 hover:underline flex items-center gap-1.5"
              >
                <span>Community Slack</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
