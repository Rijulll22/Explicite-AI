import { useEffect, useState } from "react"
import { useNav } from "../App"
import SeverityBadge from "../components/SeverityBadge"
import { apiGetIssues, type ApiIssueSummary, ApiError } from "../lib/api"

const riskColor: Record<string, string> = {
  High: "text-red-600 font-semibold",
  Medium: "text-amber-600 font-semibold",
  Low: "text-gray-400",
}

const statusStyle: Record<string, string> = {
  Open: "bg-gray-100 text-gray-700",
  "In Review": "bg-blue-100 text-blue-700",
  Resolved: "bg-green-100 text-green-700",
}

const rowAccent: Record<string, string> = {
  Critical: "border-l-2 border-l-red-400",
  High: "border-l-2 border-l-orange-400",
  Medium: "border-l-2 border-l-amber-300",
  Low: "border-l-2 border-l-gray-200",
}

const SEVERITY_ORDER: Record<string, number> = { Critical: 0, High: 1, Medium: 2, Low: 3 }

function sortIssues(items: ApiIssueSummary[], sortBy: string): ApiIssueSummary[] {
  const copy = [...items]
  if (sortBy === "Severity (highest first)") {
    copy.sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9))
  } else if (sortBy === "Date detected") {
    copy.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  } else if (sortBy === "File name") {
    copy.sort((a, b) => (a.file ?? "").localeCompare(b.file ?? ""))
  }
  return copy
}

export default function Issues() {
  const { token, selectedProjectId, openIssue, navigate, logout, preferences } = useNav()
  const [severity, setSeverity] = useState("All")
  const [type, setType] = useState("All")
  const [status, setStatus] = useState("All")
  const [search, setSearch] = useState("")
  const [sortBy, setSortBy] = useState(preferences.default_issue_sort)
  const [issues, setIssues] = useState<ApiIssueSummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Re-sync sort if the preference changes (e.g. after settings save)
  useEffect(() => { setSortBy(preferences.default_issue_sort) }, [preferences.default_issue_sort])

  useEffect(() => {
    if (!token) { logout(); return }
    if (!selectedProjectId) { setLoading(false); return }
    let cancelled = false
    setLoading(true)
    setError(null)
    apiGetIssues(token, selectedProjectId, { severity, type, status, q: search })
      .then(res => {
        if (cancelled) return
        setIssues(res.items)
        setTotal(res.total)
        setLoading(false)
      })
      .catch(err => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) { logout(); return }
        setError(err instanceof Error ? err.message : "Failed to load issues")
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [token, selectedProjectId, severity, type, status, search])

  if (!selectedProjectId) {
    return (
      <div className="p-6">
        <div className="text-sm text-gray-400 py-12 text-center">
          Select a project from the <button onClick={() => navigate("projects")} className="text-blue-600 hover:underline">Projects</button> page.
        </div>
      </div>
    )
  }

  const sorted = sortIssues(issues, sortBy)
  const criticalCount = issues.filter(i => i.severity === "Critical").length
  const highCount = issues.filter(i => i.severity === "High").length

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Issues</h2>
          <p className="text-sm text-gray-500">
            {loading ? "Loading…" : `${total} issue${total !== 1 ? "s" : ""} · sorted by ${sortBy.toLowerCase()}`}
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">{error}</div>
      )}

      {!loading && !error && (criticalCount > 0 || highCount > 0) && (
        <div className="flex items-center gap-3 mb-4 p-3 bg-red-50 border border-red-200 rounded">
          <span className="text-xs font-semibold text-red-700 uppercase tracking-wide">Fix first:</span>
          {criticalCount > 0 && (
            <span className="text-xs bg-red-100 text-red-700 border border-red-200 px-2 py-0.5 rounded font-medium">
              {criticalCount} Critical
            </span>
          )}
          {highCount > 0 && (
            <span className="text-xs bg-orange-100 text-orange-700 border border-orange-200 px-2 py-0.5 rounded font-medium">
              {highCount} High
            </span>
          )}
          <span className="text-xs text-red-600">
            {criticalCount + highCount} issue{criticalCount + highCount !== 1 ? "s" : ""} require immediate attention
          </span>
        </div>
      )}

      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <input
          type="text"
          placeholder="Search issues or files..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="px-3 py-1.5 border border-gray-300 rounded text-sm w-60 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
        {[
          { label: "Severity", value: severity, set: setSeverity, opts: ["All", "Critical", "High", "Medium", "Low"] },
          { label: "Type", value: type, set: setType, opts: ["All", "Vulnerability", "Bug", "Code Smell", "Security Hotspot"] },
          { label: "Status", value: status, set: setStatus, opts: ["All", "Open", "In Review", "Resolved"] },
        ].map(f => (
          <select
            key={f.label}
            value={f.value}
            onChange={e => f.set(e.target.value)}
            className="px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white"
          >
            {f.opts.map(o => <option key={o}>{o}</option>)}
          </select>
        ))}
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          className="px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white ml-auto"
        >
          {["Severity (highest first)", "Date detected", "File name"].map(o => (
            <option key={o}>{o}</option>
          ))}
        </select>
      </div>

      <div className="bg-white border border-gray-200 rounded overflow-hidden">
        {loading ? (
          <div className="text-center py-10 text-sm text-gray-400">Loading issues…</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-xs text-gray-400 border-b border-gray-200 bg-gray-50">
                <th className="w-1" />
                {["Severity", "Issue", "Rule", "File", "Line", "Risk", "Status", "Action"].map(h => (
                  <th key={h} className="text-left px-4 py-2.5 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map(issue => (
                <tr
                  key={issue.id}
                  className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${rowAccent[issue.severity] ?? ""}`}
                  onClick={() => openIssue(issue.id, issue)}
                >
                  <td />
                  <td className="px-4 py-3"><SeverityBadge severity={issue.severity} /></td>
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-gray-900">{issue.title}</div>
                    <div className="text-xs text-gray-400">{issue.type}</div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{issue.rule ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{issue.file ?? "—"}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{issue.line ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs ${riskColor[issue.risk] ?? "text-gray-500"}`}>{issue.risk}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusStyle[issue.status] ?? "bg-gray-100 text-gray-700"}`}>
                      {issue.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      className="text-xs text-blue-600 hover:underline"
                      onClick={e => { e.stopPropagation(); openIssue(issue.id, issue) }}
                    >
                      View →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && !error && issues.length === 0 && (
          <div className="text-center py-10 text-sm text-gray-400">No issues match the current filters.</div>
        )}
      </div>
    </div>
  )
}
