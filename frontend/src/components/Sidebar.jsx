import { useState } from "react";
import {
  Home,
  LayoutDashboard,
  BarChart3,
  AlertTriangle,
  TrendingUp,
  Zap,
  Settings,
  Search,
  Menu,
  Activity,
  Radio,
  FlaskConical,
} from "lucide-react";

export default function Sidebar({ activeTab, setActiveTab, anomalyCount = 0, liveAlertCount = 0 }) {
  const [collapsed, setCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const menuItems = [
    { id: "home", label: "Overview", icon: Home },
    { id: "live", label: "Live Cluster", icon: Radio, badge: liveAlertCount },
    { id: "allocation", label: "Cost Allocation", icon: BarChart3 },
    { id: "trends", label: "Spend Trends", icon: LayoutDashboard },
    { id: "anomalies", label: "Anomalies", icon: AlertTriangle, badge: anomalyCount },
    { id: "forecast", label: "Forecast", icon: TrendingUp },
    { id: "recommendations", label: "Savings", icon: Zap },
    { id: "evaluation", label: "Evaluation (KPIs)", icon: FlaskConical },
  ];
  const visible = menuItems.filter((m) => m.label.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <aside
      className={`bg-[#0f0f11] border-r border-[#262730] transition-all duration-200 flex flex-col justify-between select-none z-30 flex-shrink-0 ${ collapsed ? "w-14" : "w-60" }`}
    >
      {/* Top Section */}
      <div>
        {/* FinOps Brand Header */}
        <div className={`h-14 flex items-center border-b border-[#262730] ${collapsed ? "justify-center" : "px-4 gap-2.5"}`}>
          {!collapsed && (
            <>
              <div className="w-8 h-8 flex items-center justify-center flex-shrink-0 bg-blue-600 rounded-lg shadow-lg shadow-blue-500/20">
                <Activity className="w-5 h-5 text-white" strokeWidth={2.5} />
              </div>
              <span className="font-bold text-base text-white tracking-tight flex-1">
                FinOps
              </span>
            </>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded text-slate-300 hover:text-white hover:bg-[#1c1d22] transition-colors"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>

        {/* Search Box */}
        {!collapsed ? (
          <div className="p-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search..."
                className="w-full bg-[#161619] text-xs rounded pl-8 pr-7 py-1.5 border border-[#2e2f38] focus:border-blue-500 focus:outline-none placeholder-slate-500"
              />
              <kbd className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono bg-[#282932] px-1 py-0.5 rounded">
                /
              </kbd>
            </div>
          </div>
        ) : (
          <div className="p-3 flex justify-center">
            <button
              onClick={() => setCollapsed(false)}
              className="p-1.5 hover:text-white rounded"
              title="Search"
            >
              <Search className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Navigation Items */}
        <div className="px-2 space-y-1">
          {visible.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                title={collapsed ? item.label : undefined}
                className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-semibold transition-colors ${ isActive ? "bg-blue-600 text-white shadow-sm" : "text-slate-300 hover:bg-[#1c1d22] hover:text-white" }`}
              >
                <div className="flex items-center gap-3 truncate">
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </div>
                {!collapsed && item.badge !== undefined && item.badge > 0 && (
                  <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${ isActive ? "bg-white/20 text-white" : "bg-rose-500/20 text-rose-400 border border-rose-500/30" }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Bottom Section: Settings & Collapse Toggle */}
      <div className="p-2 border-t border-[#262730] space-y-1">
        <button
          onClick={() => setActiveTab("settings")}
          title={collapsed ? "Settings" : undefined}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded text-xs font-semibold transition-colors ${ activeTab === "settings" ? "bg-blue-600 text-white shadow-sm" : "text-slate-300 hover:bg-[#1c1d22] hover:text-white" }`}
        >
          <Settings className="w-4 h-4 flex-shrink-0" />
          {!collapsed && <span>Settings</span>}
        </button>
      </div>
    </aside>
  );
}
