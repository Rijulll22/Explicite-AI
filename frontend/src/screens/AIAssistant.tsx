import { useState } from "react"

interface Message {
  role: "user" | "assistant"
  content: string
}

const initial: Message[] = [
  { role: "user", content: "What does the SQL Injection issue in StudentDAO.java mean?" },
  {
    role: "assistant",
    content: `The SQL Injection issue (java:S3649) in StudentDAO.java means that at line 42, user-supplied data is being concatenated directly into a SQL query string without sanitisation.

When a query is built by string concatenation, an attacker can supply a crafted value that alters the intended SQL logic. For example, providing ' OR '1'='1 as a student ID could cause the query to return all student records rather than a single one.

This is a Critical severity issue because it can lead to:
  • Unauthorised access to student data
  • Data modification or deletion
  • Potential access to other database objects

The recommended fix is to replace string concatenation with a PreparedStatement, which separates the query structure from data values and prevents injection.`,
  },
]

const suggested = [
  "What does this issue mean?",
  "Why is this risky?",
  "How should I investigate this?",
  "What should I check in the code?",
  "Show me a safer approach.",
]

export default function AIAssistant() {
  const [messages, setMessages] = useState<Message[]>(initial)
  const [input, setInput] = useState("")

  const send = (text: string) => {
    if (!text.trim()) return
    const updated: Message[] = [...messages, { role: "user", content: text }]
    setMessages(updated)
    setInput("")
    setTimeout(() => {
      setMessages([
        ...updated,
        {
          role: "assistant",
          content: "This is a prototype demonstration. In a live system, the AI assistant would provide a detailed, context-aware response based on the issue details, relevant code, and security knowledge base.",
        },
      ])
    }, 600)
  }

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 flex flex-col min-w-0">
        {/* Context header — clearly shows which issue the AI is assisting with */}
        <div className="px-4 py-3 border-b border-gray-200 bg-white shrink-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-gray-900 text-sm">AI Code Assistant</h2>
              <span className="text-xs bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded font-medium">AI-powered</span>
            </div>
            <span className="text-xs text-gray-400">All responses are AI-generated and should be verified</span>
          </div>
          <div className="flex items-center gap-4 p-2.5 bg-gray-50 border border-gray-200 rounded">
            <div className="text-xs">
              <span className="text-gray-400">Current Issue: </span>
              <span className="font-semibold text-gray-900">SQL Injection</span>
            </div>
            <span className="text-gray-300">·</span>
            <div className="text-xs">
              <span className="text-gray-400">Severity: </span>
              <span className="font-semibold text-red-600">Critical</span>
            </div>
            <span className="text-gray-300">·</span>
            <div className="text-xs">
              <span className="text-gray-400">Risk: </span>
              <span className="font-semibold text-red-600">High</span>
            </div>
            <span className="text-gray-300">·</span>
            <div className="text-xs font-mono text-gray-500">StudentDAO.java:42</div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-lg text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm px-3.5 py-2.5"
                    : "bg-white border border-gray-200 rounded-bl-sm overflow-hidden"
                }`}
              >
                {msg.role === "assistant" && (
                  <div className="px-3.5 pt-2.5 pb-1.5 border-b border-gray-100 flex items-center gap-1.5">
                    <span className="text-xs text-gray-400 font-medium">AI Response · SQL Injection</span>
                    <span className="text-xs bg-blue-50 text-blue-500 border border-blue-100 px-1 py-0.5 rounded">AI-generated</span>
                  </div>
                )}
                <div className={`whitespace-pre-wrap ${msg.role === "assistant" ? "px-3.5 py-2.5 text-gray-700" : ""}`}>
                  {msg.content}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="p-4 border-t border-gray-200 bg-white shrink-0">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && send(input)}
              placeholder="Ask about the issue, the fix, or security concepts..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              onClick={() => send(input)}
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium"
            >
              Send
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-1.5">
            AI responses are prototype demonstrations only. Verify all guidance with authoritative sources.
          </p>
        </div>
      </div>

      <div className="w-52 shrink-0 border-l border-gray-200 bg-white p-4 space-y-5 overflow-y-auto">
        <div>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Suggested Questions</h3>
          <div className="space-y-1.5">
            {suggested.map(q => (
              <button
                key={q}
                onClick={() => send(q)}
                className="w-full text-left text-xs text-gray-600 p-2 rounded border border-gray-200 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
        <div>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Issue Context</h3>
          <div className="space-y-1.5 text-xs">
            {[
              ["Issue", "SQL Injection"],
              ["File", "StudentDAO.java"],
              ["Line", "42"],
              ["Rule", "java:S3649"],
              ["Severity", "Critical"],
              ["Risk", "High"],
            ].map(([k, v]) => (
              <div key={k} className="flex items-start justify-between gap-2">
                <span className="text-gray-400 shrink-0">{k}</span>
                <span className={`font-mono text-right ${k === "Severity" || k === "Risk" ? "text-red-600 font-semibold font-sans" : "text-gray-700"}`}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
