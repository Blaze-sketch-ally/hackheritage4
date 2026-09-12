"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowUpRight, Clock, Eye, Loader2, RefreshCw, Send, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { sendCareerChatMessage } from "@/lib/student/career-chat";
import { cn, formatCompactCount } from "@/lib/utils";
import type { ChatCard, ChatMessage, SuggestedAction } from "@/types/career-chat";

interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  cards?: ChatCard[];
  suggestedActions?: SuggestedAction[];
  error?: boolean;
}

const QUICK_PROMPTS = [
  "What should I learn next?",
  "Show my skill gaps",
  "Recommend jobs for me",
  "What's my career plan?",
  "Show YouTube learning videos",
];

const MATCH_BAND_LABEL: Record<string, string> = {
  STRONG: "Strong match",
  GOOD: "Good match",
  PARTIAL: "Partial match",
  LOW: "Some overlap",
};

let idCounter = 0;
function nextId(): string {
  idCounter += 1;
  return `career-chat-${idCounter}`;
}

/**
 * The Student Dashboard's Career AI launcher + chat drawer. Closed by
 * default; component-local state only (see this feature's own v1 scope
 * -- no persistence, no chat tables). Every card rendered here is
 * server-owned data from POST /api/v1/ai/career-chat -- this component
 * never fabricates a title, score, or URL; it only renders what the
 * response actually contains.
 */
export function CareerChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [lastUserMessage, setLastUserMessage] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages, sending]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  function close() {
    setOpen(false);
    launcherRef.current?.focus();
  }

  function historyForApi(): ChatMessage[] {
    return messages.slice(-6).map((m) => ({ role: m.role, content: m.content }));
  }

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    const history = historyForApi();
    setInput("");
    setLastUserMessage(trimmed);
    setMessages((prev) => [...prev, { id: nextId(), role: "user", content: trimmed }]);
    setSending(true);
    try {
      const response = await sendCareerChatMessage(trimmed, history);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: response.message,
          cards: response.cards,
          suggestedActions: response.suggested_actions,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
          error: true,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  function retry() {
    if (lastUserMessage) void send(lastUserMessage);
  }

  return (
    <>
      <button
        ref={launcherRef}
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open Career AI chat"
        className={cn(
          "fixed bottom-6 right-6 z-50 flex h-12 items-center gap-2 rounded-full bg-primary px-4 text-sm",
          "font-medium text-primary-foreground shadow-lg transition-all hover:bg-primary/90",
          open && "hidden",
        )}
      >
        <Sparkles className="size-4" aria-hidden="true" />
        Career AI
      </button>

      {open && (
        <div className="fixed inset-0 z-50">
          <button
            type="button"
            aria-label="Dismiss Career AI chat"
            className="absolute inset-0 bg-black/20"
            onClick={close}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Career AI chat"
            className="absolute inset-y-0 right-0 flex w-full flex-col bg-card shadow-xl sm:w-[400px]"
          >
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-sm font-semibold">
                  <Sparkles className="size-4 text-violet-600 dark:text-violet-400" aria-hidden="true" />
                  Career AI
                </p>
                <p className="text-xs text-muted-foreground">Your personalized career assistant</p>
              </div>
              <button
                type="button"
                onClick={close}
                aria-label="Close Career AI chat"
                className="shrink-0 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>

            <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
              {messages.length === 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Ask about your skill gaps, courses, videos, jobs, internships, assessments, or your
                    overall career plan.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {QUICK_PROMPTS.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => void send(prompt)}
                        className="rounded-full border px-3 py-1.5 text-xs text-foreground transition-colors hover:bg-muted"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((message) => (
                <ChatBubble key={message.id} message={message} onRetry={message.error ? retry : undefined} />
              ))}

              {sending && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground" aria-live="polite">
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                  Career AI is thinking...
                </div>
              )}
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                void send(input);
              }}
              className="flex items-end gap-2 border-t px-4 py-3"
            >
              <textarea
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void send(input);
                  }
                }}
                placeholder="Ask about your career..."
                rows={1}
                maxLength={1500}
                disabled={sending}
                className="max-h-24 min-h-9 flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
              />
              <Button type="submit" size="icon" disabled={sending || !input.trim()} aria-label="Send message">
                <Send className="size-4" aria-hidden="true" />
              </Button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

function ChatBubble({ message, onRetry }: { message: DisplayMessage; onRetry?: () => void }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex flex-col gap-2", isUser && "items-end")}>
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
          message.error && "bg-destructive/10 text-destructive",
        )}
      >
        {message.error && (
          <p className="mb-1 flex items-center gap-1.5 text-xs font-medium">
            <AlertCircle className="size-3.5" aria-hidden="true" /> Couldn&apos;t send that
          </p>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <RefreshCw className="size-3" aria-hidden="true" /> Retry
        </button>
      )}

      {message.cards && message.cards.length > 0 && (
        <div className="flex w-full flex-col gap-2">
          {message.cards.map((card, index) => (
            <CardRenderer key={`${card.type}-${index}`} card={card} />
          ))}
        </div>
      )}

      {message.suggestedActions && message.suggestedActions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {message.suggestedActions.map((action) => (
            <Button
              key={action.url}
              size="sm"
              variant="outline"
              render={<Link href={action.url} />}
              nativeButton={false}
            >
              {action.label} <ArrowUpRight className="size-3.5" aria-hidden="true" />
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

function CardRenderer({ card }: { card: ChatCard }) {
  switch (card.type) {
    case "SKILL":
      return (
        <div className="rounded-lg border bg-background p-2.5 text-xs">
          <p className="text-sm font-medium text-foreground">{card.skill_name}</p>
          {(card.current_level || card.target_level) && (
            <p className="text-muted-foreground">
              {card.current_level ?? "Not started"} &rarr; {card.target_level ?? "?"}
            </p>
          )}
          {card.importance && <p className="mt-1 text-muted-foreground">{card.importance}</p>}
          <Button
            size="sm"
            variant="outline"
            className="mt-2 w-full"
            render={<Link href="/student/skill-gap" />}
            nativeButton={false}
          >
            View Skill Gap
          </Button>
        </div>
      );

    case "COURSE":
      return (
        <div className="rounded-lg border bg-background p-2.5 text-xs">
          <p className="text-sm font-medium text-foreground">{card.title}</p>
          {card.provider && <p className="text-muted-foreground">{card.provider}</p>}
          <Button
            size="sm"
            variant="outline"
            className="mt-2 w-full"
            render={<Link href={card.url} target="_blank" rel="noopener noreferrer" />}
            nativeButton={false}
          >
            Open Course <ArrowUpRight className="size-3.5" aria-hidden="true" />
          </Button>
        </div>
      );

    case "YOUTUBE_VIDEO":
      return (
        <div className="overflow-hidden rounded-lg border bg-background text-xs">
          {card.thumbnail_url && (
            // eslint-disable-next-line @next/next/no-img-element -- external YouTube thumbnail
            <img src={card.thumbnail_url} alt={card.title} className="aspect-video w-full object-cover" loading="lazy" />
          )}
          <div className="p-2.5">
            <p className="text-sm font-medium text-foreground">{card.title}</p>
            <p className="text-muted-foreground">{card.channel_title}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-muted-foreground">
              {card.duration_text && (
                <span className="flex items-center gap-1">
                  <Clock className="size-3" aria-hidden="true" /> {card.duration_text}
                </span>
              )}
              {card.view_count != null && (
                <span className="flex items-center gap-1">
                  <Eye className="size-3" aria-hidden="true" /> {formatCompactCount(card.view_count)}
                </span>
              )}
            </div>
            <Button
              size="sm"
              variant="outline"
              className="mt-2 w-full"
              render={<Link href={card.watch_url} target="_blank" rel="noopener noreferrer" />}
              nativeButton={false}
            >
              Watch on YouTube <ArrowUpRight className="size-3.5" aria-hidden="true" />
            </Button>
          </div>
        </div>
      );

    case "OPPORTUNITY":
      return (
        <div className="rounded-lg border bg-background p-2.5 text-xs">
          <p className="text-sm font-medium text-foreground">{card.title}</p>
          {card.company && <p className="text-muted-foreground">{card.company}</p>}
          {card.match_score != null && (
            <p className="mt-1 text-muted-foreground">
              {card.match_score}%{card.match_band ? ` • ${MATCH_BAND_LABEL[card.match_band] ?? card.match_band}` : ""}
            </p>
          )}
          <Button
            size="sm"
            variant="outline"
            className="mt-2 w-full"
            render={<Link href={card.detail_url} />}
            nativeButton={false}
          >
            View Opportunity
          </Button>
        </div>
      );

    case "ASSESSMENT":
      return (
        <div className="rounded-lg border bg-background p-2.5 text-xs">
          <p className="text-sm font-medium text-foreground">{card.skill_name}</p>
          <p className="text-muted-foreground">{card.note}</p>
          <Button
            size="sm"
            variant="outline"
            className="mt-2 w-full"
            render={<Link href={card.cta_url} />}
            nativeButton={false}
          >
            Go to Skill Gap
          </Button>
        </div>
      );

    case "CAREER_ACTION":
      return (
        <div className="rounded-lg border bg-background p-2.5 text-xs">
          <p className="text-sm font-medium text-foreground">{card.label}</p>
          <Button size="sm" variant="outline" className="mt-2 w-full" render={<Link href={card.url} />} nativeButton={false}>
            View
          </Button>
        </div>
      );

    default:
      return null;
  }
}
