import { useRef, useState } from "react"
import { useNav } from "../App"
import { apiAskAssistant, type ApiIssueSummary, ApiError } from "../lib/api"

interface Message {
  role: "user" | "assistant"
  content: string
  error?: boolean
}

const SUGGESTED = [
  "What does this issue mean?",
  "Why is this risky?",
  "How should I investigate this?",
  "What should I check in the code?",
  "Show me a safer approach.",
]

function buildInitialMessages(issue: ApiIssueSummary | null): Message[] {
  if (!issue) {
    return [
      {
        role: "assistant",
        content:
          "No issue is currently selected. Navigate to an issue from the Issues page and click 'AI Assistant' to start a context-aware conversation.",
      },
    ]
  }
  return [
    {
      role: "assistant",
      content: `I am ready to help you understand the "${issue.title}" issue${issue.file ? ` in ${issue.file}${issue.line ? `:${issue.line}` : ""}` : ""}.

This is a ${issue.severity} severity issue (${issue.risk} risk). Ask me anything about what it means, why it matters, or how to remediate it.`,
    },
  ]
}

export default function AIAssistant() {
  const { token, selectedProjectId, selectedIssueSummary, selectedIssueId, logout } = useNav()
  const [messages, setMessages] = useState<Message[]>(() =>
    buildInitialMessages(selectedIssueSummary),
  )
  const [input, setInput] = useState("")
  const [pending, setPending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const issueTitle = selectedIssueSummary?.title ?? null

  const severityColor: Record<string, string> = {
    Critical: "text-red-600",
    High: "text-red-500",
    Medium: "text-amber-600",
    Low: "text-gray-500",
  }

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || pending) return
    if (!token || !selectedProjectId) {
      setMessages(prev => [
        ...prev,
        { role: "user", content: trimmed },
        { role: "assistant", content: "No project is selected. Please select a project first.", error: true },
      ])
      return
    }

    const withUser: Message[] = [...messages, { role: "user", content: trimmed }]
    setMessages(withUser)
    setInput("")
    setPending(true)

    // Scroll to bottom after render
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50)

    try {
      const result = await apiAskAssistant(token, selectedProjectId, trimmed, selectedIssueId ?? undefined)
      setMessages([...withUser, { role: "assistant", content: result.reply }])
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
      let msg: string
      if (err instanceof ApiError && err.status === 503) {
        msg = "AI model is not configured. Ask your administrator to set up an AI provider in .env (LLM_PROVIDER=anthropic or LLM_PROVIDER=ollama)."
      } else if (err instanceof ApiError && err.status === 422) {
        msg = "Your message could not be processed (too long or empty). Please shorten it and try again."
      } else {
        msg = err instanceof Error ? err.message : "Failed to get a response. Please try again."
      }
      setMessages([...withUser, { role: "assistant", content: msg, error: true }])
    } finally {
      setPending(false)
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50)
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 flex flex-col min-w-0">
        {/* Context header */}
        <div className="px-4 py-3 border-b border-gray-200 bg-white shrink-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-gray-900 text-sm">AI Code Assistant</h2>
              <span className="text-xs bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded font-medium">
                AI-powered
              </span>
            </div>
            <span className="text-xs text-gray-400">All responses should be verified</span>
          </div>
          <div className="flex items-center gap-4 p-2.5 bg-gray-50 border border-gray-200 rounded flex-wrap">
            {selectedIssueSummary ? (
              <>
                <div className="text-xs">
                  <span className="text-gray-400">Current Issue: </span>
                  <span className="font-semibold text-gray-900">{selectedIssueSummary.title}</span>
                </div>
                <span className="text-gray-300">·</span>
                <div className="text-xs">
                  <span className="text-gray-400">Severity: </span>
                  <span className={`font-semibold ${severityColor[selectedIssueSummary.severity] ?? "text-gray-700"}`}>
                    {selectedIssueSummary.severity}
                  </span>
                </div>
                <span className="text-gray-300">·</span>
                <div className="text-xs">
                  <span className="text-gray-400">Risk: </span>
                  <span className={`font-semibold ${selectedIssueSummary.risk === "High" ? "text-red-600" : selectedIssueSummary.risk === "Medium" ? "text-amber-600" : "text-gray-600"}`}>
                    {selectedIssueSummary.risk}
                  </span>
                </div>
                {selectedIssueSummary.file && (
                  <>
                    <span className="text-gray-300">·</span>
                    <div className="text-xs font-mono text-gray-500">
                      {selectedIssueSummary.file}
                      {selectedIssueSummary.line ? `:${selectedIssueSummary.line}` : ""}
                    </div>
                  </>
                )}
              </>
            ) : (
              <span className="text-xs text-gray-400 italic">No issue selected — navigate to an issue and click AI Assistant</span>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-lg text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm px-3.5 py-2.5"
                    : msg.error
                    ? "bg-amber-50 border border-amber-200 rounded-bl-sm overflow-hidden"
                    : "bg-white border border-gray-200 rounded-bl-sm overflow-hidden"
                }`}
              >
                {msg.role === "assistant" && (
                  <div className="px-3.5 pt-2.5 pb-1.5 border-b border-gray-100 flex items-center gap-1.5">
                    <span className="text-xs text-gray-400 font-medium">
                      AI Response{issueTitle ? ` · ${issueTitle}` : ""}
                    </span>
                    {!msg.error && (
                      <span className="text-xs bg-blue-50 text-blue-500 border border-blue-100 px-1 py-0.5 rounded">
                        AI-generated
                      </span>
                    )}
                  </div>
                )}
                <div className={`whitespace-pre-wrap ${msg.role === "assistant" ? "px-3.5 py-2.5 text-gray-700" : ""}`}>
                  {msg.content}
                </div>
              </div>
            </div>
          ))}
          {pending && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-lg rounded-bl-sm px-3.5 py-3 text-sm text-gray-400">
                Thinking…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="p-4 border-t border-gray-200 bg-white shrink-0">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !e.shiftKey && send(input)}
              placeholder="Ask about the issue, the fix, or security concepts…"
              disabled={pending}
              className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <button
              onClick={() => send(input)}
              disabled={pending || !input.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {pending ? "…" : "Send"}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-1.5">
            AI-generated · Grounded in project findings · Not a substitute for manual review
          </p>
        </div>
      </div>

      <div className="w-52 shrink-0 border-l border-gray-200 bg-white p-4 space-y-5 overflow-y-auto">
        <div>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Suggested Questions</h3>
          <div className="space-y-1.5">
            {SUGGESTED.map(q => (
              <button
                key={q}
                onClick={() => send(q)}
                disabled={pending}
                className="w-full text-left text-xs text-gray-600 p-2 rounded border border-gray-200 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
        <div>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Issue Context</h3>
          {selectedIssueSummary ? (
            <div className="space-y-1.5 text-xs">
              {(
                [
                  ["Issue", selectedIssueSummary.title],
                  ["File", selectedIssueSummary.file ?? "—"],
                  ["Line", selectedIssueSummary.line !== null ? String(selectedIssueSummary.line) : "—"],
                  ["Rule", selectedIssueSummary.rule ?? "—"],
                  ["Severity", selectedIssueSummary.severity],
                  ["Risk", selectedIssueSummary.risk],
                ] as [string, string][]
              ).map(([k, v]) => (
                <div key={k} className="flex items-start justify-between gap-2">
                  <span className="text-gray-400 shrink-0">{k}</span>
                  <span
                    className={`font-mono text-right ${
                      k === "Severity" || k === "Risk"
                        ? `font-semibold font-sans ${severityColor[v] ?? "text-gray-700"}`
                        : "text-gray-700"
                    }`}
                  >
                    {v}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400 italic">No issue selected</p>
          )}
        </div>
      </div>
    </div>
  )
}
