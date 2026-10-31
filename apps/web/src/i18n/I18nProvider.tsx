import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { loadLocalState, updateLocalState } from "../storage/local";
import { directionOf, translate, type Lang, type MessageKey } from "./messages";

interface I18n {
  lang: Lang;
  dir: "rtl" | "ltr";
  setLang: (lang: Lang) => void;
  t: (key: MessageKey, values?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children, initialLang }: { children: ReactNode; initialLang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(() => initialLang ?? loadLocalState().state.settings.lang);

  // The root element carries lang and dir so the whole document mirrors (design: RTL).
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = directionOf(lang);
    document.title = translate(lang, "app.name");
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    updateLocalState((state) => ({ ...state, settings: { ...state.settings, lang: next } }));
  }, []);

  const value = useMemo<I18n>(
    () => ({ lang, dir: directionOf(lang), setLang, t: (key, values) => translate(lang, key, values) }),
    [lang, setLang],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n outside I18nProvider");
  return value;
}
