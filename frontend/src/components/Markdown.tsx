import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Renders a markdown string (summaries, chat replies) with Tailwind styling.
 *  Raw HTML is not rendered, so this is safe for model-generated content. */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h3 className="mt-3 text-base font-semibold text-ink-900" {...p} />,
          h2: (p) => <h3 className="mt-3 text-sm font-semibold text-ink-900" {...p} />,
          h3: (p) => <h4 className="mt-2 text-sm font-semibold text-ink-800" {...p} />,
          p: (p) => <p {...p} />,
          ul: (p) => <ul className="list-disc space-y-1 pl-5" {...p} />,
          ol: (p) => <ol className="list-decimal space-y-1 pl-5" {...p} />,
          li: (p) => <li {...p} />,
          strong: (p) => <strong className="font-semibold" {...p} />,
          em: (p) => <em className="italic" {...p} />,
          a: (p) => (
            <a className="text-wing-600 underline hover:text-wing-500" target="_blank" rel="noreferrer" {...p} />
          ),
          code: (p) => <code className="rounded bg-ink-100 px-1 py-0.5 text-xs" {...p} />,
          hr: () => <hr className="my-3 border-ink-200" />,
          blockquote: (p) => <blockquote className="border-l-2 border-ink-200 pl-3 text-ink-600" {...p} />,
          table: (p) => <table className="w-full border-collapse text-xs" {...p} />,
          th: (p) => <th className="border border-ink-200 px-2 py-1 text-left font-medium" {...p} />,
          td: (p) => <td className="border border-ink-200 px-2 py-1" {...p} />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
