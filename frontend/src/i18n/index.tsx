import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { dict, Lang, TKey } from "./dict";

interface I18nState {
  lang: Lang;
  setLang: (l: Lang) => void;
  /** Translate a key, with optional `{placeholder}` substitutions. */
  t: (key: TKey, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nState>(null as unknown as I18nState);

const STORAGE_KEY = "finwing_lang";

export function LanguageProvider({ children }: { children: ReactNode }) {
  const { user, refresh } = useAuth();
  const [lang, setLangState] = useState<Lang>(
    () => (localStorage.getItem(STORAGE_KEY) as Lang) || "en"
  );

  // Adopt the signed-in user's stored preference when it loads.
  useEffect(() => {
    if (user?.language && user.language !== lang) {
      setLangState(user.language as Lang);
      localStorage.setItem(STORAGE_KEY, user.language);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.language]);

  function setLang(l: Lang) {
    setLangState(l);
    localStorage.setItem(STORAGE_KEY, l);
    document.documentElement.lang = l === "zh" ? "zh-CN" : "en";
    if (user) {
      api
        .patch("/users/me", { language: l })
        .then(() => refresh())
        .catch(() => {});
    }
  }

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  }, [lang]);

  function t(key: TKey, vars?: Record<string, string | number>): string {
    let s: string = dict[lang][key] ?? dict.en[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
    return s;
  }

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export const useI18n = () => useContext(I18nContext);
