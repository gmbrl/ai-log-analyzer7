import { useState } from "react";
import DashboardPage from "./pages/DashboardPage";
import "./index.css";

const TABS = ["Monitoring", "Check Box", "Support"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("Monitoring");
  const [search, setSearch] = useState("");

  return (
    <div className="app">
      {/* Top Nav */}
      <nav className="topnav">
        <div className="topnav-logo">
          <span className="logo-icon">◈</span>
          <span className="logo-text">TraceLens</span>
        </div>
        <div className="topnav-tabs">
          {TABS.map((t) => (
            <button
              key={t}
              className={`tab-btn ${activeTab === t ? "active" : ""}`}
              onClick={() => setActiveTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="topnav-right">
          <input
            className="topnav-search"
            placeholder="Search logs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="user-avatar" title="User profile">
            U
          </div>
        </div>
      </nav>

      {/* Sidebar + Content */}
      <div className="app-body">
        <aside className="sidebar">
          <button className="sidebar-icon" title="Favorites">☆</button>
          <button className="sidebar-icon" title="Incidents">⚡</button>
          <button className="sidebar-icon" title="Services">⬡</button>
          <button className="sidebar-icon" title="Filters">⊟</button>
          <div className="sidebar-spacer" />
          <button className="sidebar-icon" title="Settings">⚙</button>
        </aside>

        <div className="content">
          {activeTab === "Monitoring" && <DashboardPage />}
          {activeTab === "Check Box" && (
            <div className="placeholder-tab">Check Box — coming soon</div>
          )}
          {activeTab === "Support" && (
            <div className="placeholder-tab">Support — coming soon</div>
          )}
        </div>
      </div>
    </div>
  );
}
