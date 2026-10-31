import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { readSession, writeSession } from "../storage/session";
import { initialDraft, type Endpoint, type PlanDraft, type When } from "./draft";

// Transient plan state shared by Home, Search and Compare (design: Where state lives).

interface Plan {
  draft: PlanDraft;
  setFrom: (from: Endpoint) => void;
  setTo: (to: Endpoint | null) => void;
  swap: () => void;
  setWhen: (when: When) => void;
  /** Index of the selected option in the current journey answer (Compare). */
  selected: number;
  setSelected: (index: number) => void;
}

const PlanContext = createContext<Plan | null>(null);

function isDraft(value: unknown): value is PlanDraft {
  if (!value || typeof value !== "object") return false;
  const draft = value as Partial<PlanDraft>;
  return typeof draft.from === "object" && draft.from !== null && typeof draft.when === "object" && draft.when !== null;
}

export function PlanProvider({ children, initial }: { children: ReactNode; initial?: PlanDraft }) {
  const [draft, setDraft] = useState<PlanDraft>(() => initial ?? readSession("plan", isDraft) ?? initialDraft);
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    writeSession("plan", draft);
  }, [draft]);

  const setFrom = useCallback((from: Endpoint) => {
    setDraft((d) => ({ ...d, from }));
    setSelected(0);
  }, []);
  const setTo = useCallback((to: Endpoint | null) => {
    setDraft((d) => ({ ...d, to }));
    setSelected(0);
  }, []);
  const swap = useCallback(() => {
    setDraft((d) => (d.to === null ? d : { ...d, from: d.to, to: d.from }));
    setSelected(0);
  }, []);
  const setWhen = useCallback((when: When) => {
    setDraft((d) => ({ ...d, when }));
    setSelected(0);
  }, []);

  const value = useMemo<Plan>(
    () => ({ draft, setFrom, setTo, swap, setWhen, selected, setSelected }),
    [draft, setFrom, setTo, swap, setWhen, selected],
  );
  return <PlanContext.Provider value={value}>{children}</PlanContext.Provider>;
}

export function usePlan(): Plan {
  const value = useContext(PlanContext);
  if (!value) throw new Error("usePlan outside PlanProvider");
  return value;
}
