import { useI18n } from "../i18n";

export function LanguageToggle() {
  const { lang, setLang } = useI18n();
  const base = "px-2 py-1 text-xs font-medium transition-colors";
  return (
    <div className="flex overflow-hidden rounded-lg border border-ink-200">
      <button
        onClick={() => setLang("en")}
        className={`${base} ${lang === "en" ? "bg-ink-100 text-ink-900" : "text-ink-400 hover:bg-ink-50"}`}
      >
        EN
      </button>
      <button
        onClick={() => setLang("zh")}
        className={`${base} ${lang === "zh" ? "bg-ink-100 text-ink-900" : "text-ink-400 hover:bg-ink-50"}`}
      >
        中文
      </button>
    </div>
  );
}
