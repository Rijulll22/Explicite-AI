import React, { useEffect, useRef, useState } from "react"
import { useNav } from "../App"
import {
  apiStartTutorSession,
  apiTutorChat,
  apiCompleteResource,
  ApiError,
  type ApiTutorMessage,
} from "../lib/api"

const SUGGESTED_PROMPTS = [
  "Explain with an example",
  "Show me a code snippet",
  "What are common mistakes?",
  "Give me a practical exercise",
  "Quiz me on this topic",
  "Explain in simpler terms",
  "Show the secure fix",
]

function renderContent(text: string): React.ReactElement {
  const parts: React.ReactElement[] = []
  const codeBlockRe = /```(\w*)\n?([\s\S]*?)```/g
  let lastIndex = 0
  let match
  let key = 0

  while ((match = codeBlockRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(
        <span key={key++} className="whitespace-pre-wrap">
          {text.slice(lastIndex, match.index)}
        </span>,
      )
    }
    const lang = match[1] || "code"
    parts.push(
      <pre
        key={key++}
        className="code-block bg-gray-900 text-gray-100 rounded p-3 my-2 overflow-x-auto text-xs leading-relaxed"
        data-lang={lang}
      >
        <div className="text-gray-500 text-xs mb-1 font-mono">{lang}</div>
        <code>{match[2]}</code>
      </pre>,
    )
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    parts.push(
      <span key={key++} className="whitespace-pre-wrap">
        {text.slice(lastIndex)}
      </span>,
    )
  }
  return <>{parts}</>
}

function difficultyColor(tag: string | null): string {
  if (!tag) return "bg-gray-100 text-gray-600"
  if (tag === "Security") return "bg-red-50 text-red-600"
  if (tag === "Quality") return "bg-blue-50 text-blue-600"
  return "bg-gray-100 text-gray-600"
}

export default function TutorSession() {
  const { token, selectedLearningResource, navigate, logout } = useNav()

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ApiTutorMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [input, setInput] = useState("")
  const [pending, setPending] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [completing, setCompleting] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const resource = selectedLearningResource

  useEffect(() => {
    if (!token || !resource) {
      navigate("learning")
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)

    apiStartTutorSession(token, resource.id)
      .then(session => {
        if (cancelled) return
        setSessionId(session.session_id)
        setMessages(session.messages)
        setLoading(false)
        setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "auto" }), 50)
      })
      .catch(err => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) { logout(); return }
        setError(err instanceof Error ? err.message : "Failed to start tutor session")
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [resource?.id])

  const scrollBottom = () =>
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50)

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || pending || !sessionId || !token) return

    const optimisticUser: ApiTutorMessage = {
      id: "optimistic-" + Date.now(),
      session_id: sessionId,
      role: "user",
      content: trimmed,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, optimisticUser])
    setInput("")
    setPending(true)
    scrollBottom()

    try {
      const resp = await apiTutorChat(token, sessionId, trimmed)
      setMessages(prev => [
        ...prev.filter(m => m.id !== optimisticUser.id),
        { ...optimisticUser, id: "user-" + Date.now() },
        resp.message,
      ])
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
      let msg: string
      if (err instanceof ApiError && err.status === 503) {
        msg =
          "The AI tutor is not available right now. Check that your AI provider is configured (LLM_PROVIDER in .env). Your question has been saved."
      } else if (err instanceof ApiError && err.status === 422) {
        msg = "Your message is too long (max 2000 characters). Please shorten it."
      } else {
        msg = err instanceof Error ? err.message : "Failed to get a response. Please try again."
      }
      const errorMsg: ApiTutorMessage = {
        id: "error-" + Date.now(),
        session_id: sessionId,
        role: "assistant",
        content: msg,
        created_at: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setPending(false)
      scrollBottom()
    }
  }

  async function handleComplete() {
    if (!token || !resource || completing || completed) return
    setCompleting(true)
    try {
      await apiCompleteResource(token, resource.id)
      setCompleted(true)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
    } finally {
      setCompleting(false)
    }
  }

  if (!resource) {
    return (
      <div className="p-6 text-center text-sm text-gray-400">
        No learning resource selected.{" "}
        <button onClick={() => navigate("learning")} className="text-blue-600 hover:underline">
          Back to learning →
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-200 bg-white shrink-0">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 min-w-0">
              <button
                onClick={() => navigate("learning")}
                className="text-xs text-gray-400 hover:text-blue-600 shrink-0 mt-0.5"
                title="Back to Learning"
              >
                ← Back
              </button>
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-gray-900 truncate">{resource.title}</h2>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  <span className="text-xs text-gray-500">{resource.resource_type}</span>
                  {resource.duration_minutes && (
                    <>
                      <span className="text-gray-300">·</span>
                      <span className="text-xs text-gray-500">{resource.duration_minutes} min</span>
                    </>
                  )}
                  {resource.tag && (
                    <>
                      <span className="text-gray-300">·</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${difficultyColor(resource.tag)}`}>
                        {resource.tag}
                      </span>
                    </>
                  )}
                  {resource.related_issue_type && (
                    <>
                      <span className="text-gray-300">·</span>
                      <span className="text-xs text-gray-400">{resource.related_issue_type}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded font-medium">
                AI Tutor
              </span>
              {completed ? (
                <span className="text-xs text-green-600 font-medium px-2 py-1 border border-green-200 rounded bg-green-50">
                  ✓ Completed
                </span>
              ) : (
                <button
                  onClick={e => { e.stopPropagation(); handleComplete() }}
                  disabled={completing}
                  className="text-xs px-2 py-1 border border-gray-200 rounded hover:border-green-400 hover:text-green-600 text-gray-400 disabled:opacity-50"
                >
                  {completing ? "Saving…" : "Mark complete"}
                </button>
              )}
            </div>
          </div>
          {resource.description && (
            <p className="text-xs text-gray-500 mt-2 pl-10">{resource.description}</p>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-lg px-3.5 py-3 text-sm text-gray-400">
                Loading your tutor session…
              </div>
            </div>
          )}

          {error && (
            <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm text-amber-700">
              {error}
            </div>
          )}

          {!loading && messages.length === 0 && !error && (
            <div className="flex justify-start">
              <div className="max-w-[80%] bg-white border border-gray-200 rounded-lg rounded-bl-sm overflow-hidden">
                <div className="px-3.5 pt-2.5 pb-1.5 border-b border-gray-100 flex items-center gap-1.5">
                  <span className="text-xs text-gray-400 font-medium">AI Tutor · {resource.title}</span>
                  <span className="text-xs bg-blue-50 text-blue-500 border border-blue-100 px-1 py-0.5 rounded">
                    AI-generated
                  </span>
                </div>
                <div className="px-3.5 py-2.5 text-sm text-gray-700">
                  <p>
                    Welcome! I am your AI tutor for <strong>{resource.title}</strong>.
                  </p>
                  <p className="mt-2">
                    {resource.description
                      ? `${resource.description} Ask me anything about this topic — I can explain concepts, show code examples, and quiz you.`
                      : "Ask me anything about this topic — I can explain concepts, show code examples, walk through real-world scenarios, and quiz you."}
                  </p>
                  <p className="mt-2 text-xs text-gray-400 italic">
                    Responses are AI-generated and should be verified against authoritative sources.
                  </p>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg, i) => {
            const isUser = msg.role === "user"
            const isError = msg.id.startsWith("error-")
            return (
              <div key={msg.id ?? i} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-lg text-sm leading-relaxed ${
                    isUser
                      ? "bg-blue-600 text-white rounded-br-sm px-3.5 py-2.5"
                      : isError
                      ? "bg-amber-50 border border-amber-200 rounded-bl-sm overflow-hidden"
                      : "bg-white border border-gray-200 rounded-bl-sm overflow-hidden"
                  }`}
                >
                  {!isUser && (
                    <div className="px-3.5 pt-2.5 pb-1.5 border-b border-gray-100 flex items-center gap-1.5">
                      <span className="text-xs text-gray-400 font-medium">AI Tutor · {resource.title}</span>
                      {!isError && (
                        <span className="text-xs bg-blue-50 text-blue-500 border border-blue-100 px-1 py-0.5 rounded">
                          AI-generated
                        </span>
                      )}
                    </div>
                  )}
                  <div className={`${isUser ? "" : "px-3.5 py-2.5 text-gray-700"}`}>
                    {isUser ? msg.content : renderContent(msg.content)}
                  </div>
                </div>
              </div>
            )
          })}

          {pending && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-lg rounded-bl-sm px-3.5 py-3 text-sm text-gray-400">
                Thinking…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-200 bg-white shrink-0">
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  send(input)
                }
              }}
              placeholder="Ask a question… (Enter to send, Shift+Enter for new line)"
              disabled={pending || loading}
              rows={2}
              className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed resize-none"
            />
            <button
              onClick={() => send(input)}
              disabled={pending || loading || !input.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed self-end"
            >
              {pending ? "…" : "Send"}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-1.5">
            AI-generated · Responses may not be authoritative · Verify before applying
          </p>
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-52 shrink-0 border-l border-gray-200 bg-white p-4 space-y-5 overflow-y-auto">
        <div>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Suggested Questions
          </h3>
          <div className="space-y-1.5">
            {SUGGESTED_PROMPTS.map(q => (
              <button
                key={q}
                onClick={() => send(q)}
                disabled={pending || loading}
                className="w-full text-left text-xs text-gray-600 p-2 rounded border border-gray-200 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Resource Info
          </h3>
          <div className="space-y-1.5 text-xs">
            {[
              ["Type", resource.resource_type],
              ["Duration", resource.duration_minutes ? `${resource.duration_minutes} min` : "—"],
              ["Category", resource.tag ?? "—"],
              ["Issue type", resource.related_issue_type ?? "—"],
              ["Rule", resource.related_rule_key ?? "—"],
            ].map(([k, v]) => (
              <div key={k} className="flex items-start justify-between gap-2">
                <span className="text-gray-400 shrink-0">{k}</span>
                <span className="text-gray-700 text-right font-mono text-xs truncate max-w-[7rem]">{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Actions
          </h3>
          <div className="space-y-1.5">
            <button
              onClick={() => navigate("learning")}
              className="w-full text-left text-xs text-gray-600 p-2 rounded border border-gray-200 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-colors"
            >
              ← Back to Learning
            </button>
            {!completed && (
              <button
                onClick={handleComplete}
                disabled={completing}
                className="w-full text-left text-xs text-gray-600 p-2 rounded border border-gray-200 hover:border-green-400 hover:text-green-600 hover:bg-green-50 transition-colors disabled:opacity-50"
              >
                {completing ? "Saving…" : "✓ Mark as Complete"}
              </button>
            )}
            {completed && (
              <div className="text-xs text-green-600 font-medium p-2 bg-green-50 rounded border border-green-200">
                ✓ Completed
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
