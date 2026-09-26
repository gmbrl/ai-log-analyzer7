import { create } from "zustand";
import type { Filters, Severity } from "./types";

const DEFAULT_FILTERS: Filters = {
  time_range: "1h",
  severities: ["FATAL", "ERROR", "WARN", "INFO", "DEBUG"],
  services: [],
  incident_types: [],
  auto_refresh: true,
};

function readFiltersFromURL(): Filters {
  const p = new URLSearchParams(window.location.search);
  const f: Filters = { ...DEFAULT_FILTERS };
  const tr = p.get("time_range");
  if (tr) f.time_range = tr as Filters["time_range"];
  const svcs = p.get("services");
  if (svcs) f.services = svcs.split(",").filter(Boolean);
  const sevs = p.get("severities");
  if (sevs)
    f.severities = sevs.split(",").filter(Boolean) as Severity[];
  const it = p.get("incident_types");
  if (it) f.incident_types = it.split(",").filter(Boolean);
  const ar = p.get("auto_refresh");
  if (ar !== null) f.auto_refresh = ar === "true";
  return f;
}

function writeFiltersToURL(f: Filters) {
  const p = new URLSearchParams();
  p.set("time_range", f.time_range);
  if (f.services.length) p.set("services", f.services.join(","));
  p.set("severities", f.severities.join(","));
  if (f.incident_types.length)
    p.set("incident_types", f.incident_types.join(","));
  p.set("auto_refresh", String(f.auto_refresh));
  const url = `${window.location.pathname}?${p.toString()}`;
  window.history.replaceState({}, "", url);
}

interface Store {
  filters: Filters;
  setFilters: (patch: Partial<Filters>) => void;
  activeService: string | null;
  setActiveService: (s: string | null) => void;
  activeBubble: string | null;
  setActiveBubble: (s: string | null) => void;
}

export const useStore = create<Store>((set) => ({
  filters: readFiltersFromURL(),
  setFilters: (patch) =>
    set((state) => {
      const next = { ...state.filters, ...patch };
      writeFiltersToURL(next);
      return { filters: next };
    }),
  activeService: null,
  setActiveService: (s) => set({ activeService: s }),
  activeBubble: null,
  setActiveBubble: (s) => set({ activeBubble: s }),
}));
