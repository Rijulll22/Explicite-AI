import { useEffect, useState } from "react"
import { useNav } from "../App"
import SeverityBadge from "../components/SeverityBadge"
import {
  apiGetIssueDetail,
  apiUpdateIssueStatus,
  apiExplainIssue,
  apiGenerateFix,
  apiGetSourceExcerpt,
  type ApiIssueDetail,
  type ApiExplainResponse,
  type ApiSourceExcerpt,
  ApiError,
} from "../lib/api"

const VALID_STATUSES = ["Open", "In Review", "Resolved"] as const

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
  } catch { return iso }
}

export default function IssueDetail() {
  const { token, selectedProjectId, selectedIssueId, navigate, logout, openFix, preferences } = useNav()
  const [issue, setIssue] = useState<ApiIssueDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentStatus, setCurrentStatus] = useState<string>("Open")
  const [statusSaving, setStatusSaving] = useState(false)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<ApiExplainResponse | null>(null)
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainError, setExplainError] = useState<string | null>(null)
  const [fixGenerating, setFixGenerating] = useState(false)
  const [fixError, setFixError] = useState<string | null>(null)
  const [sourceExcerpt, setSourceExcerpt] = useState<ApiSourceExcerpt | null>(null)
  const [sourceLoading, setSourceLoading] = useState(false)

  useEffect(() => {
    if (!token) { logout(); return }
    if (!selectedProjectId || !selectedIssueId) { setLoading(false); return }
    let cancelled = false
    setLoading(true)
    setSourceLoading(true)
    setError(null)
    setSourceExcerpt(null)
    apiGetIssueDetail(token, selectedProjectId, selectedIssueId)
      .then(d => {
        if (!cancelled) {
          setIssue(d)
          setCurrentStatus(d.status)
          setLoading(false)
          // Load source excerpt in parallel (non-blocking — failure is handled gracefully)
          apiGetSourceExcerpt(token, selectedProjectId!, selectedIssueId!)
            .then(s => { if (!cancelled) { setSourceExcerpt(s); setSourceLoading(false) } })
            .catch(() => { if (!cancelled) setSourceLoading(false) })
        }
      })
      .catch(err => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) { logout(); return }
        setError(err instanceof Error ? err.message : "Failed to load issue")
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [token, selectedProjectId, selectedIssueId])

  async function handleStatusChange(newStatus: string) {
    if (!token || !selectedProjectId || !selectedIssueId) return
    if (statusSaving || newStatus === currentStatus) return
    setStatusSaving(true)
    setStatusError(null)
    try {
      const updated = await apiUpdateIssueStatus(token, selectedProjectId, selectedIssueId, newStatus)
      setCurrentStatus(updated.status)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
      setStatusError(err instanceof Error ? err.message : "Failed to update status")
    } finally {
      setStatusSaving(false)
    }
  }

  async function handleExplain(force = false) {
    if (!token || !selectedProjectId || !selectedIssueId || explainLoading) return
    setExplainLoading(true)
    setExplainError(null)
    try {
      const level = preferences.ai_explain_level as "beginner" | "intermediate" | "advanced"
      const result = await apiExplainIssue(token, selectedProjectId, selectedIssueId, { force, level })
      setExplanation(result)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
      if (err instanceof ApiError && err.status === 503) {
        setExplainError("AI model is not configured. Ask your administrator to set up an AI provider.")
      } else if (err instanceof ApiError && err.status === 502) {
        setExplainError("The AI model returned an unreadable response. Try again later.")
      } else {
        setExplainError(err instanceof Error ? err.message : "Failed to generate explanation")
      }
    } finally {
      setExplainLoading(false)
    }
  }

  async function handleGenerateFix() {
    if (!token || !selectedProjectId || !selectedIssueId || fixGenerating) return
    setFixGenerating(true)
    setFixError(null)
    try {
      const fix = await apiGenerateFix(token, selectedProjectId, selectedIssueId)
      openFix(fix.id)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
      if (err instanceof ApiError && err.status === 503) {
        setFixError("AI model is not configured. Ask your administrator to set up an AI provider.")
      } else {
        setFixError(err instanceof Error ? err.message : "Failed to generate fix")
      }
    } finally {
      setFixGenerating(false)
    }
  }

  if (!selectedProjectId || !selectedIssueId) {
    return (
      <div className="p-6">
        <div className="text-sm text-gray-400 py-12 text-center">
          Select an issue from the <button onClick={() => navigate("issues")} className="text-blue-600 hover:underline">Issues</button> page.
        </div>
      </div>
    )
  }

  if (loading) {
    return <div className="p-6 text-sm text-gray-400 text-center py-12">Loading issue…</div>
  }

  if (error) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">{error}</div>
      </div>
    )
  }

  if (!issue) return null

  const breadcrumbLabel = issue.file
    ? `${issue.title} — ${issue.file}${issue.line ? `:${issue.line}` : ""}`
    : issue.title

  const metaTag = [issue.rule, issue.cwe_id, issue.owasp_category].filter(Boolean).join(" · ")

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-xs text-gray-400 mb-4">
        <button onClick={() => navigate("issues")} className="hover:text-blue-600 text-gray-500">Issues</button>
        <span>›</span>
        <span className="text-gray-900">{breadcrumbLabel}</span>
      </div>

      <div className="flex items-start justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <SeverityBadge severity={issue.severity} />
            <span className={`text-xs px-2 py-0.5 rounded font-medium border ${issue.risk === "High" ? "bg-red-50 border-red-200 text-red-700" : issue.risk === "Medium" ? "bg-amber-50 border-amber-200 text-amber-700" : "bg-gray-50 border-gray-200 text-gray-600"}`}>
              {issue.risk} Risk
            </span>
            {metaTag && <span className="text-xs text-gray-400 font-mono">{metaTag}</span>}
          </div>
          <h2 className="text-xl font-semibold text-gray-900">{issue.title}</h2>
          {(issue.file || issue.line) && (
            <p className="text-sm text-gray-500 font-mono mt-0.5">
              {issue.file ?? "Unknown file"}{issue.line ? ` · Line ${issue.line}` : ""}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => navigate("ai-assistant")} className="px-3 py-1.5 border border-gray-300 rounded text-sm hover:border-blue-400 hover:text-blue-600">
            AI Assistant
          </button>
          <button
            onClick={handleGenerateFix}
            disabled={fixGenerating}
            className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium disabled:opacity-60"
          >
            {fixGenerating ? "Generating…" : "Generate Fix"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Main column */}
        <div className="col-span-2 space-y-4">

          {/* Code Context */}
          <div className="bg-white border border-gray-200 rounded overflow-hidden">
            <div className="px-4 py-2.5 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Code Context</h3>
              {(sourceExcerpt?.file || issue.file) && (
                <span className="font-mono text-xs text-gray-400">
                  {sourceExcerpt?.file || issue.file}
                  {issue.line ? `:${issue.line}` : ""}
                </span>
              )}
            </div>
            {sourceLoading ? (
              <div className="bg-[#0d1117] text-[#5c6370] text-xs font-mono p-4 leading-relaxed text-center py-8">
                Loading source…
              </div>
            ) : sourceExcerpt?.available && sourceExcerpt.lines.length > 0 ? (
              <div className="code-block leading-relaxed overflow-x-auto" style={{ backgroundColor: "#0d1117", color: "#e6edf3" }}>
                {sourceExcerpt.lines.map(ln => (
                  <div
                    key={ln.number}
                    className={ln.is_target ? "code-line-remove" : ""}
                    style={ln.is_target ? {} : {}}
                  >
                    <span
                      className="select-none pr-3 text-right inline-block w-10"
                      style={{ color: ln.is_target ? "#f85149" : "#484f58" }}
                    >
                      {ln.number}
                    </span>
                    <span style={ln.is_target ? { backgroundColor: "#3d1a1a", display: "inline-block", width: "calc(100% - 3rem)", color: "#ff7b72" } : {}}>
                      {ln.content || " "}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-[#0d1117] text-[#5c6370] text-xs font-mono p-4 leading-relaxed text-center py-8">
                {sourceExcerpt?.message || (
                  <>
                    Source code preview not available — view the file in your IDE at{" "}
                    {issue.file
                      ? <span className="text-[#abb2bf]">{issue.file}{issue.line ? `:${issue.line}` : ""}</span>
                      : "the location above"}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Risk Analysis */}
          <div className="bg-white border border-gray-300 rounded overflow-hidden">
            <div className="px-4 py-2.5 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Risk Analysis</h3>
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium border ${issue.risk === "High" ? "bg-red-50 text-red-600 border-red-200" : issue.risk === "Medium" ? "bg-amber-50 text-amber-600 border-amber-200" : "bg-gray-50 text-gray-600 border-gray-200"}`}>
                {issue.risk} Risk
              </span>
            </div>
            <div className="p-4 grid grid-cols-4 gap-4">
              {[
                { label: "Severity", value: issue.severity, color: issue.severity === "Critical" || issue.severity === "High" ? "text-red-600" : issue.severity === "Medium" ? "text-amber-600" : "text-gray-600" },
                { label: "Risk Level", value: issue.risk, color: issue.risk === "High" ? "text-red-600" : issue.risk === "Medium" ? "text-amber-600" : "text-gray-600" },
                { label: "CVSS Score", value: issue.cvss_score !== null ? `${issue.cvss_score.toFixed(1)} / 10` : "Not available", color: issue.cvss_score !== null && issue.cvss_score >= 7 ? "text-red-600" : issue.cvss_score !== null && issue.cvss_score >= 4 ? "text-amber-600" : "text-gray-700" },
                { label: "Status", value: currentStatus, color: currentStatus === "Resolved" ? "text-green-600" : "text-gray-700" },
              ].map(r => (
                <div key={r.label} className="text-center">
                  <div className="text-xs text-gray-400 mb-1">{r.label}</div>
                  <div className={`text-base font-bold ${r.color}`}>{r.value}</div>
                </div>
              ))}
            </div>
            {(issue.cvss_score !== null || issue.cwe_id || issue.owasp_category) && (
              <div className="px-4 pb-3 flex items-center gap-4 border-t border-gray-100 pt-3 flex-wrap">
                {issue.cvss_score !== null && (
                  <div className="text-xs text-gray-500">
                    {issue.cvss_version && <span className="mr-1 font-mono text-gray-400">CVSS v{issue.cvss_version}</span>}
                    <span className={`font-semibold ${issue.cvss_score >= 7 ? "text-red-600" : issue.cvss_score >= 4 ? "text-amber-600" : "text-gray-700"}`}>
                      {issue.cvss_score.toFixed(1)} / 10
                    </span>
                    {issue.cvss_severity && <span className="ml-1 text-gray-400">({issue.cvss_severity})</span>}
                  </div>
                )}
                {issue.cvss_vector && (
                  <div className="text-xs text-gray-400 font-mono break-all">{issue.cvss_vector}</div>
                )}
                {issue.cwe_id && <div className="text-xs text-gray-500">CWE: <span className="font-mono text-gray-700">{issue.cwe_id}</span></div>}
                {issue.owasp_category && <div className="text-xs text-gray-500">OWASP: <span className="font-mono text-gray-700">{issue.owasp_category}</span></div>}
              </div>
            )}
          </div>

          {/* Why Does It Matter */}
          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Why Does it Matter?</h3>
            {issue.description ? (
              <p className="text-sm text-gray-700 leading-relaxed">{issue.description}</p>
            ) : (
              <p className="text-sm text-gray-400 italic">No description available for this issue.</p>
            )}
          </div>

          {/* AI Explanation */}
          <div className="bg-white border border-gray-200 rounded p-4">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">AI Explanation</h3>
                {explanation && (
                  <span className="text-xs bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded font-medium">
                    {explanation.cached ? "Cached" : explanation.model_provider}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {explanation && (
                  <button
                    onClick={() => handleExplain(true)}
                    disabled={explainLoading}
                    className="text-xs text-gray-400 hover:text-blue-600 disabled:opacity-40"
                    title="Regenerate explanation"
                  >
                    Regenerate
                  </button>
                )}
                <button
                  onClick={() => handleExplain(false)}
                  disabled={explainLoading}
                  className="px-2.5 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50 font-medium"
                >
                  {explainLoading ? "Generating…" : explanation ? "Refresh" : issue.ai_explanation ? "Load Explanation" : "Explain with AI"}
                </button>
              </div>
            </div>

            {explainError && (
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-3">{explainError}</div>
            )}

            {explanation ? (
              <div className="space-y-3 text-sm text-gray-700">
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-0.5">What it means</span>
                  <p className="leading-relaxed">{explanation.what}</p>
                </div>
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-0.5">Why it matters</span>
                  <p className="leading-relaxed">{explanation.why}</p>
                </div>
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-0.5">How it arises</span>
                  <p className="leading-relaxed">{explanation.how_it_arises}</p>
                </div>
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-0.5">Remediation</span>
                  <p className="leading-relaxed">{explanation.remediation}</p>
                </div>
                {explanation.caveats && (
                  <div className="bg-gray-50 border border-gray-200 rounded px-3 py-2">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-0.5">Caveats</span>
                    <p className="text-xs text-gray-600 leading-relaxed">{explanation.caveats}</p>
                  </div>
                )}
              </div>
            ) : !explainLoading && !explainError ? (
              <p className="text-sm text-gray-400 italic">
                {issue.ai_explanation
                  ? "An explanation was previously generated. Click \"Load Explanation\" to view it."
                  : "No AI explanation has been generated yet. Click \"Explain with AI\" to generate one."}
              </p>
            ) : null}

            <p className="text-xs text-gray-400 mt-3">AI-generated · Not a substitute for manual review · Verify all AI explanations</p>
          </div>

          {/* Suggested Guidance */}
          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Suggested Guidance</h3>
            <p className="text-sm text-gray-700 leading-relaxed mb-3">
              Review the AI explanation above and generate an AI-proposed fix for remediation. The fix requires explicit approval before any changes can be applied.
            </p>
            {fixError && (
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-3">{fixError}</div>
            )}
            <div className="flex gap-2">
              <button
                onClick={handleGenerateFix}
                disabled={fixGenerating}
                className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium disabled:opacity-60"
              >
                {fixGenerating ? "Generating…" : "Generate Fix"}
              </button>
              <button onClick={() => navigate("ai-assistant")} className="px-3 py-1.5 border border-gray-300 rounded text-sm hover:bg-gray-50">
                Ask AI
              </button>
            </div>
          </div>
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Details</h3>
            <div className="space-y-2">
              {([
                ["Type", issue.type],
                ["Rule", issue.rule ?? "—"],
                ["Detected", formatDate(issue.created_at)],
                ...(issue.cwe_id ? [["CWE", issue.cwe_id]] : []),
                ...(issue.owasp_category ? [["OWASP", issue.owasp_category]] : []),
              ] as [string, string][]).map(([label, value]) => (
                <div key={label} className="flex items-center justify-between gap-2">
                  <span className="text-xs text-gray-500 shrink-0">{label}</span>
                  <span className="text-xs text-gray-900 font-mono text-right">{value}</span>
                </div>
              ))}
              {/* Interactive status row */}
              <div className="flex items-center justify-between gap-2 pt-1">
                <span className="text-xs text-gray-500 shrink-0">Status</span>
                <div className="flex items-center gap-1.5">
                  {statusSaving && <span className="text-xs text-gray-400">Saving…</span>}
                  <select
                    value={currentStatus}
                    disabled={statusSaving}
                    onChange={e => handleStatusChange(e.target.value)}
                    className="text-xs border border-gray-200 rounded px-1.5 py-0.5 bg-white text-gray-900 font-mono focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {VALID_STATUSES.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>
              {statusError && (
                <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1 mt-1">{statusError}</div>
              )}
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded p-3">
            <h3 className="text-xs font-semibold text-blue-700 mb-2">Next Steps</h3>
            <div className="space-y-1.5">
              {["Review the code context", "Assess the risk analysis", "Read the AI explanation", "Apply the suggested fix", "Verify with Code Analysis"].map((step, i) => (
                <div key={step} className="flex items-center gap-2 text-xs text-blue-700">
                  <span className="w-4 h-4 rounded-full bg-blue-200 flex items-center justify-center text-[10px] font-bold shrink-0">
                    {i + 1}
                  </span>
                  {step}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
