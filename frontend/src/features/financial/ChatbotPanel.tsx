import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import type { ChatMessage, SourceChunk } from '../../api/chatbot'
import { useChatbot } from '../../hooks/useChatbot'

export interface ChatbotPanelProps {
  workspaceId: string
  documentCount?: number
}

interface LocalMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceChunk[]
  tookMs?: number
  error?: boolean
}

const SUGGESTED_QUESTIONS = [
  'What was the total revenue reported?',
  'What are the key risks and red flags?',
  'What does management say about future growth outlook?',
  'What is the gross margin and how did it change?',
  'Are there any losses or profit warnings?',
  'What market rate or pricing information is disclosed?',
  'How to upload a document?',
  'What file formats are supported?',
]

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function MarkdownText({ text }: { text: string }) {
  // Simple markdown renderer – bold, bullets, line breaks
  const lines = text.split('\n')
  return (
    <div className="chatbot-markdown space-y-1 text-sm leading-relaxed">
      {lines.map((line, i) => {
        if (line.trim() === '') return <br key={i} />
        // Bold: **text**
        const parts = line.split(/(\*\*[^*]+\*\*)/g)
        return (
          <p key={i} className="m-0">
            {parts.map((part, j) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={j}>{part.slice(2, -2)}</strong>
              }
              return <span key={j}>{part}</span>
            })}
          </p>
        )
      })}
    </div>
  )
}

function SourceCard({ source, index }: { source: SourceChunk; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const label = source.document_title || source.company_name || `Document ${index + 1}`
  const page = source.page_start ? ` · p.${source.page_start}` : ''
  const period = source.fiscal_period ? ` · ${source.fiscal_period}` : ''

  return (
    <div className="rounded border border-line bg-surface-subtle p-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-semibold text-ink">{label}</span>
          <span className="text-ink-muted">{page}{period}</span>
          {source.section_heading && (
            <span className="ml-1 text-ink-subtle">— {source.section_heading}</span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-primary text-[10px]">
            {(source.score * 100).toFixed(0)}%
          </span>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-ink-muted hover:text-ink"
            aria-label={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded ? '▲' : '▼'}
          </button>
        </div>
      </div>
      {expanded && (
        <p className="mt-2 whitespace-pre-wrap text-ink-muted border-t border-line pt-2">
          {source.content}
        </p>
      )}
    </div>
  )
}

function AssistantMessage({ msg }: { msg: LocalMessage }) {
  const [showSources, setShowSources] = useState(false)
  const sources = msg.sources ?? []

  return (
    <div className="flex flex-col gap-2">
      <div className="max-w-[90%] self-start rounded-2xl rounded-tl-sm bg-surface-subtle px-4 py-3">
        {msg.error ? (
          <p className="text-sm text-danger">{msg.content}</p>
        ) : (
          <MarkdownText text={msg.content} />
        )}
        {msg.tookMs !== undefined && (
          <p className="mt-1.5 text-[10px] text-ink-muted">{msg.tookMs.toFixed(0)} ms</p>
        )}
      </div>
      {sources.length > 0 && (
        <div className="ml-2">
          <button
            onClick={() => setShowSources(!showSources)}
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            {showSources ? '▾' : '▸'}
            {sources.length} source{sources.length !== 1 ? 's' : ''} used
          </button>
          {showSources && (
            <div className="mt-2 flex flex-col gap-1.5">
              {sources.map((s, i) => (
                <SourceCard key={s.chunk_id} source={s} index={i} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function ChatbotPanel({ workspaceId, documentCount = 0 }: ChatbotPanelProps) {
  const [messages, setMessages] = useState<LocalMessage[]>([])
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const chatMutation = useChatbot(workspaceId)

  // Scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const history: ChatMessage[] = messages
    .filter((m) => !m.error)
    .map((m) => ({ role: m.role, content: m.content }))

  const sendMessage = async (question: string) => {
    const q = question.trim()
    if (!q || chatMutation.isPending) return

    const userMsg: LocalMessage = { id: makeId(), role: 'user', content: q }
    setMessages((prev) => [...prev, userMsg])
    setInput('')

    try {
      const resp = await chatMutation.mutateAsync({ question: q, history, top_k: 8 })
      const assistantMsg: LocalMessage = {
        id: makeId(),
        role: 'assistant',
        content: resp.answer,
        sources: resp.sources,
        tookMs: resp.took_ms,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      const errorMsg: LocalMessage = {
        id: makeId(),
        role: 'assistant',
        content:
          err instanceof Error
            ? `Error: ${err.message}`
            : 'An unexpected error occurred. Please try again.',
        error: true,
      }
      setMessages((prev) => [...prev, errorMsg])
    }
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    void sendMessage(input)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage(input)
    }
  }

  const clearChat = () => {
    setMessages([])
    chatMutation.reset()
  }

  return (
    <div className="flex h-full min-h-[520px] flex-col rounded-lg border border-line bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">Document Analyst</p>
            <p className="text-xs text-ink-muted">
              {documentCount > 0
                ? `Ask questions about ${documentCount} document${documentCount !== 1 ? 's' : ''}`
                : 'Upload documents to start asking questions'}
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            className="text-xs text-ink-muted hover:text-ink"
            title="Clear conversation"
          >
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
            <div className="rounded-full bg-primary/5 p-4">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-8 w-8 text-primary/60"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                <path d="M12 17h.01" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-ink">Ask anything about your documents</p>
              <p className="mt-1 text-xs text-ink-muted">
                Revenue, profit, losses, forecasts, risks, market data and more
              </p>
            </div>
            {/* Suggested questions */}
            <div className="mt-2 flex flex-wrap justify-center gap-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => void sendMessage(q)}
                  disabled={chatMutation.isPending}
                  className="rounded-full border border-line bg-surface-subtle px-3 py-1.5 text-xs text-ink-muted hover:border-primary/40 hover:bg-primary/5 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) =>
              msg.role === 'user' ? (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-white">
                    {msg.content}
                  </div>
                </div>
              ) : (
                <AssistantMessage key={msg.id} msg={msg} />
              ),
            )}
            {chatMutation.isPending && (
              <div className="flex items-center gap-2 self-start">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-subtle">
                  <span className="animate-pulse text-primary text-xs">●</span>
                </div>
                <div className="flex gap-1">
                  <span className="animate-bounce text-ink-muted text-sm delay-0">·</span>
                  <span className="animate-bounce text-ink-muted text-sm delay-150">·</span>
                  <span className="animate-bounce text-ink-muted text-sm delay-300">·</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-line px-4 py-3">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about revenue, profit, risks, forecasts… (Enter to send, Shift+Enter for new line)"
            disabled={chatMutation.isPending}
            className="flex-1 resize-none rounded-lg border border-line bg-surface-subtle px-3 py-2 text-sm placeholder:text-ink-muted focus:border-primary focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || chatMutation.isPending}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
            title="Send message"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 rotate-90"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M2 21 23 12 2 3v7l15 2-15 2v7z" />
            </svg>
          </button>
        </form>
        <p className="mt-1.5 text-[10px] text-ink-muted">
          Answers are grounded in your uploaded documents · Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}

