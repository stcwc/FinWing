import { createContext, useContext } from "react";
import { ArticleAttachment } from "../api/types";

/** Shared chat state so the feed (under the router Outlet) can attach an article
 *  to the chat panel (a sibling in Shell) — the touch-friendly replacement for
 *  desktop drag-and-drop, which doesn't fire from touch events on mobile. */
export interface ChatContextValue {
  attachments: ArticleAttachment[];
  addAttachment: (a: ArticleAttachment) => void;
  removeAttachment: (id: string) => void;
  openChat: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export const ChatProvider = ChatContext.Provider;

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within <ChatProvider>");
  return ctx;
}
