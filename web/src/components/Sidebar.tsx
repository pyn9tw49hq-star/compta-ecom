"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import {
  BarChart3,
  Upload,
  FileText,
  TriangleAlert,
  PieChart,
  Settings,
  Sun,
  Moon,
  Monitor,
} from "lucide-react";

interface SidebarProps {
  activeView: string;
  onViewChange: (view: string) => void;
  anomalyCount?: number;
  hasResult: boolean;
  onOpenHelp: () => void;
}

interface NavItem {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  needsResult: boolean;
}

const NAV_VIEWS: NavItem[] = [
  { key: "flash", label: "Flash e-commerce", icon: BarChart3, needsResult: true },
  { key: "upload", label: "Import fichiers", icon: Upload, needsResult: false },
  { key: "ecritures", label: "Écritures", icon: FileText, needsResult: true },
  { key: "anomalies", label: "Anomalies", icon: TriangleAlert, needsResult: true },
  { key: "resume", label: "Résumé", icon: PieChart, needsResult: true },
];

const NAV_CONFIG: NavItem[] = [
  { key: "parametres", label: "Paramètres", icon: Settings, needsResult: false },
];

function SidebarThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="bg-sidebar-hover rounded-lg p-1 flex gap-0.5 w-full">
        <div className="flex-1 flex items-center justify-center rounded-md p-1.5 text-sidebar-text-muted">
          <Sun className="h-4 w-4" />
        </div>
        <div className="flex-1 flex items-center justify-center rounded-md p-1.5 text-sidebar-text-muted">
          <Moon className="h-4 w-4" />
        </div>
        <div className="flex-1 flex items-center justify-center rounded-md p-1.5 text-sidebar-text-muted">
          <Monitor className="h-4 w-4" />
        </div>
      </div>
    );
  }

  const buttons: { value: string; icon: React.ComponentType<{ className?: string }>; label: string }[] = [
    { value: "light", icon: Sun, label: "Clair" },
    { value: "dark", icon: Moon, label: "Sombre" },
    { value: "system", icon: Monitor, label: "Systeme" },
  ];

  return (
    <div className="bg-sidebar-hover rounded-lg p-1 flex gap-0.5 w-full">
      {buttons.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          onClick={() => setTheme(value)}
          className={`flex-1 flex items-center justify-center rounded-md p-1.5 transition-colors ${
            theme === value
              ? "bg-sidebar-active text-white"
              : "text-sidebar-text-muted hover:text-sidebar-text"
          }`}
          aria-label={label}
        >
          <Icon className="h-4 w-4" />
        </button>
      ))}
    </div>
  );
}

export default function Sidebar({
  activeView,
  onViewChange,
  anomalyCount = 0,
  hasResult,
  onOpenHelp,
}: SidebarProps) {
  const renderNavItem = (item: NavItem) => {
    const isActive = activeView === item.key;
    const isDisabled = item.needsResult && !hasResult;
    const Icon = item.icon;

    return (
      <button
        key={item.key}
        onClick={() => {
          if (!isDisabled) onViewChange(item.key);
        }}
        disabled={isDisabled}
        className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm transition-colors w-full text-left ${
          isActive
            ? "bg-sidebar-active text-white font-medium"
            : isDisabled
              ? "text-sidebar-text-muted opacity-40 cursor-not-allowed pointer-events-none"
              : "text-sidebar-text-muted hover:bg-sidebar-hover"
        }`}
      >
        <Icon className="h-5 w-5 shrink-0" />
        <span className="flex-1">{item.label}</span>
        {item.key === "anomalies" && anomalyCount > 0 && (
          <span className="bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1">
            {anomalyCount}
          </span>
        )}
      </button>
    );
  };

  return (
    <aside className="w-[260px] shrink-0 bg-sidebar flex flex-col min-h-screen pt-8 px-5 pb-5">
      {/* Logo area */}
      <div className="mb-8 px-4">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-9 h-9 rounded-lg bg-teal-500 flex items-center justify-center text-white font-bold text-sm">
            C
          </div>
          <span className="text-base font-bold text-sidebar-text tracking-tight">
            MAPP E-COMMERCE
          </span>
        </div>
        <p className="text-xs text-sidebar-text-muted ml-12">Compta E-commerce</p>
      </div>

      {/* VUES section */}
      <div className="mb-6">
        <p className="text-[10px] font-semibold tracking-[2px] text-sidebar-text-muted uppercase px-4 mb-2">
          Vues
        </p>
        <div className="flex flex-col gap-1">
          {NAV_VIEWS.map(renderNavItem)}
        </div>
      </div>

      {/* CONFIGURATION section */}
      <div className="mb-6">
        <p className="text-[10px] font-semibold tracking-[2px] text-sidebar-text-muted uppercase px-4 mb-2">
          Configuration
        </p>
        <div className="flex flex-col gap-1">
          {NAV_CONFIG.map(renderNavItem)}
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Divider */}
      <div className="h-px bg-sidebar-hover mb-4" />

      {/* Theme toggle */}
      <SidebarThemeToggle />

      {/* Aide link */}
      {activeView === "upload" && (
        <button
          onClick={onOpenHelp}
          className="text-sidebar-text-muted text-xs mt-3 text-left hover:text-sidebar-text transition-colors px-1"
        >
          Aide
        </button>
      )}
    </aside>
  );
}
