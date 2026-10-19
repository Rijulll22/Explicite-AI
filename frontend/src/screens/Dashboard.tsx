import { useEffect, useRef, useState } from "react"
import { useNav } from "../App"
import SeverityBadge from "../components/SeverityBadge"
import {
  apiGetDashboard,
  apiSubmitAnalysis,
  apiGetAnalysisJob,
  type ApiDashboard,
  type ApiIssueSummary,
  type ApiAnalysisJob,
  ApiError,
} from "../lib/api"

function StatCard({ label, value, color, sub }: { label: string; value: string | number; color: string; sub?: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded p-4">
      <div className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function RiskScoreCard({ score, version, openFindings }: { score: number | null; version: string | null; openFindings: number }) {
  if (score === null) {
    return (
      <div className="bg-white border border-gray-200 rounded p-4">
        <div className="text-xs text-gray-400 font-medium uppercase tracking-wide">Project Risk Score</div>
        <div className="text-2xl font-bold mt-1 text-gray-400">—</div>
        <div className="text-xs text-gray-400 mt-0.5">No analysis yet</div>
      </div>
    )
  }

  const band =
    score >= 75 ? { label: "Critical Risk", color: "text-red-600", bar: "bg-red-500" } :
    score >= 50 ? { label: "High Risk",     color: "text-orange-600", bar: "bg-orange-500" } :
    score >= 25 ? { label: "Moderate Risk", color: "text-yellow-600", bar: "bg-yellow-500" } :
                  { label: "Low Risk",      color: "text-green-600",  bar: "bg-green-500" }

  return (
    <div className="bg-white border border-gray-200 rounded p-4">
      <div className="text-xs text-gray-400 font-medium uppercase tracking-wide">Project Risk Score</div>
      <div className={`text-2xl font-bold mt-1 ${band.color}`}>{score.toFixed(1)} <span className="text-base font-normal text-gray-400">/ 100</span></div>
      <div className="mt-2 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${band.bar}`} style={{ width: `${score}%` }} />
      </div>
      <div className="text-xs text-gray-400 mt-1.5">
        {band.label} · {openFindings} unresolved{version ? ` · model ${version}` : ""}
      </div>
    </div>
  )
}

function SecondaryStatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white border border-gray-100 rounded px-4 py-3">
      <div className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</div>
      <div className="text-base font-semibold text-gray-600 mt-0.5">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function formatAnalysisDate(iso: string | null): string {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
  } catch { return iso }
}

function AnalysisModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void
  onSubmit: (file: File) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4"
        onClick={e => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold text-gray-900 mb-1">Run Analysis</h3>
        <p className="text-sm text-gray-500 mb-4">
          Upload a ZIP archive of your source files (max 10 MB). Supported: .py .java .js .ts .jsx .tsx
        </p>
        <div
          className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors mb-4"
          onClick={() => inputRef.current?.click()}
        >
          {file ? (
            <div className="text-sm text-gray-700 font-medium">{file.name} ({(file.size / 1024).toFixed(0)} KB)</div>
          ) : (
            <>
              <div className="text-gray-400 text-sm">Click to select a ZIP file</div>
              <div className="text-xs text-gray-400 mt-1">or drag and drop</div>
            </>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".zip,application/zip"
          className="hidden"
          onChange={e => setFile(e.target.files?.[0] ?? null)}
        />
        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm text-gray-600 border border-gray-200 rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            disabled={!file}
            onClick={() => file && onSubmit(file)}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Analysis
          </button>
        </div>
      </div>
    </div>
  )
}

function JobStatusBar({ job, onDismiss }: { job: ApiAnalysisJob; onDismiss: () => void }) {
  const isTerminal = job.status === "completed" || job.status === "failed"
  const color = job.status === "completed"
    ? "bg-green-50 border-green-200 text-green-800"
    : job.status === "failed"
    ? "bg-red-50 border-red-200 text-red-800"
    : "bg-blue-50 border-blue-200 text-blue-800"

  const label =
    job.status === "queued" ? "Analysis queued…"
    : job.status === "running" ? "Analysis running…"
    : job.status === "completed"
    ? `Analysis complete — ${job.findings_count ?? 0} finding${job.findings_count !== 1 ? "s" : ""}`
    : `Analysis failed: ${job.failure_reason ?? "unknown error"}`

  return (
    <div className={`border rounded px-4 py-2 text-sm flex items-center gap-3 mb-4 ${color}`}>
      {!isTerminal && (
        <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
      )}
      <span className="flex-1">{label}</span>
      {isTerminal && (
        <button onClick={onDismiss} className="text-xs underline opacity-70 hover:opacity-100">Dismiss</button>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { token, selectedProjectId, navigate, openIssue, logout } = useNav()
  const [data, setData] = useState<ApiDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [currentJob, setCurrentJob] = useState<ApiAnalysisJob | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) { logout(); return }
    if (!selectedProjectId) { setLoading(false); return }
    let cancelled = false
    setLoading(true)
    setError(null)
    apiGetDashboard(token, selectedProjectId)
      .then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(err => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) { logout(); return }
        setError(err instanceof Error ? err.message : "Failed to load dashboard")
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [token, selectedProjectId])

  // Poll running job until terminal, then reload dashboard
  useEffect(() => {
    if (!currentJob || !token || !selectedProjectId) return
    if (currentJob.status === "completed" || currentJob.status === "failed") return
    let cancelled = false
    const interval = setInterval(() => {
      apiGetAnalysisJob(token, selectedProjectId, currentJob.id)
        .then(updated => {
          if (cancelled) return
          setCurrentJob(updated)
          if (updated.status === "completed") {
            // Reload dashboard data to reflect new findings
            apiGetDashboard(token, selectedProjectId)
              .then(d => { if (!cancelled) setData(d) })
              .catch(() => {})
          }
        })
        .catch(() => {})
    }, 2000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [currentJob?.id, currentJob?.status, token, selectedProjectId])

  async function handleSubmit(file: File) {
    if (!token || !selectedProjectId) return
    setShowModal(false)
    setSubmitError(null)
    try {
      const job = await apiSubmitAnalysis(token, selectedProjectId, file)
      setCurrentJob(job)
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Failed to start analysis")
    }
  }

  if (!selectedProjectId) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="text-sm text-gray-400 py-12 text-center">
          Select a project from the <button onClick={() => navigate("projects")} className="text-blue-600 hover:underline">Projects</button> page.
        </div>
      </div>
    )
  }

  if (loading) {
    return <div className="p-6 text-sm text-gray-400 text-center py-12">Loading dashboard…</div>
  }

  if (error) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">{error}</div>
      </div>
    )
  }

  if (!data) return null

  const { metrics: m, supporting_metrics: sm, quality_gate: qg } = data
  const vulnSub = m.critical_vulnerabilities > 0 || m.high_vulnerabilities > 0
    ? `${m.critical_vulnerabilities} Critical, ${m.high_vulnerabilities} High`
    : undefined

  function handleIssueClick(issue: ApiIssueSummary) {
    openIssue(issue.id, issue)
  }

  const jobRunning = currentJob && currentJob.status !== "completed" && currentJob.status !== "failed"

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {showModal && (
        <AnalysisModal onClose={() => setShowModal(false)} onSubmit={handleSubmit} />
      )}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Project Dashboard</h2>
          <p className="text-sm text-gray-500">
            {data.project_name} · Last analysis: {formatAnalysisDate(data.last_analysis_at)}
          </p>
        </div>
        <button
          disabled={!!jobRunning}
          onClick={() => setShowModal(true)}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {jobRunning ? "Analysis running…" : "Run Analysis"}
        </button>
      </div>
      {submitError && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded px-4 py-2 mb-4">
          {submitError}
          <button onClick={() => setSubmitError(null)} className="ml-3 text-xs underline">Dismiss</button>
        </div>
      )}
      {currentJob && (
        <JobStatusBar job={currentJob} onDismiss={() => setCurrentJob(null)} />
      )}

      {/* Project Health */}
      <div className="bg-white border border-gray-200 rounded p-4 mb-5">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Project Health</div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className={`w-4 h-4 rounded-full shrink-0 ${qg.passed ? "bg-green-500" : "bg-red-500"}`} />
            <div>
              <div className="font-semibold text-gray-900 text-base">
                Quality Gate: {qg.passed ? "Passed" : "Failed"}
              </div>
              {qg.failed_conditions.length > 0 && (
                <div className="text-xs text-gray-500 mt-0.5">
                  {qg.failed_conditions.length} condition{qg.failed_conditions.length !== 1 ? "s" : ""} failed — {qg.failed_conditions.join(", ")}
                </div>
              )}
            </div>
          </div>
          <div className="ml-auto flex gap-6 text-center shrink-0">
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide">Analysis</div>
              <div className="text-sm font-semibold text-gray-900 mt-0.5">{formatAnalysisDate(data.last_analysis_at)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide">Branch</div>
              <div className="text-sm font-mono font-semibold text-gray-900 mt-0.5">{data.branch}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Primary metrics */}
      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Key Metrics</div>
      <div className="grid grid-cols-4 gap-3 mb-3">
        <StatCard label="Bugs" value={m.bugs} color="text-red-600" sub={m.bugs_delta !== null ? `${m.bugs_delta > 0 ? "+" : ""}${m.bugs_delta} since last analysis` : undefined} />
        <StatCard label="Vulnerabilities" value={m.vulnerabilities} color="text-orange-600" sub={vulnSub} />
        <StatCard label="Code Smells" value={m.code_smells} color="text-amber-600" sub={m.technical_debt_display ? `~${m.technical_debt_display} technical debt` : undefined} />
        <StatCard label="Security Hotspots" value={m.security_hotspots} color="text-purple-600" sub={m.security_hotspots_needing_review > 0 ? `${m.security_hotspots_needing_review} need review` : undefined} />
      </div>
      <div className="grid grid-cols-4 gap-3 mb-5">
        <RiskScoreCard score={data.risk_score} version={data.risk_score_version} openFindings={data.open_findings} />
        {Object.keys(data.findings_by_severity).length > 0 && (
          <div className="col-span-3 bg-white border border-gray-200 rounded p-4">
            <div className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-2">Findings by Severity</div>
            <div className="flex gap-4 flex-wrap">
              {(["Critical","High","Medium","Low"] as const).map(sev => {
                const count = data.findings_by_severity[sev] ?? 0
                if (count === 0) return null
                const colors: Record<string, string> = { Critical: "bg-red-100 text-red-700", High: "bg-orange-100 text-orange-700", Medium: "bg-yellow-100 text-yellow-700", Low: "bg-green-100 text-green-700" }
                return (
                  <div key={sev} className={`px-3 py-1.5 rounded text-sm font-semibold ${colors[sev]}`}>
                    {sev}: {count}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Priority Issues */}
      <div className="bg-white border border-gray-200 rounded mb-5">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">Priority Issues</h3>
            <p className="text-xs text-gray-400 mt-0.5">Highest severity issues requiring immediate attention</p>
          </div>
          <button onClick={() => navigate("issues")} className="text-xs text-blue-600 hover:underline">View all issues →</button>
        </div>
        {data.priority_issues.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-gray-400">No open critical or high issues.</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                {["Severity", "Issue", "File", "Line", "Action"].map(h => (
                  <th key={h} className="text-left px-4 py-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.priority_issues.map(issue => (
                <tr
                  key={issue.id}
                  className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                  onClick={() => handleIssueClick(issue)}
                >
                  <td className="px-4 py-2.5"><SeverityBadge severity={issue.severity} /></td>
                  <td className="px-4 py-2.5 text-sm font-medium text-gray-900">{issue.title}</td>
                  <td className="px-4 py-2.5 text-xs font-mono text-gray-500">{issue.file ?? "—"}</td>
                  <td className="px-4 py-2.5 text-sm text-gray-500">{issue.line ?? "—"}</td>
                  <td className="px-4 py-2.5">
                    <button
                      className="text-xs text-blue-600 hover:underline"
                      onClick={e => { e.stopPropagation(); handleIssueClick(issue) }}
                    >
                      View →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Supporting metrics */}
      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Supporting Metrics</div>
      <div className="grid grid-cols-3 gap-3 mb-5">
        <SecondaryStatCard
          label="Coverage"
          value={sm.coverage_pct !== null ? `${sm.coverage_pct.toFixed(1)}%` : "—"}
          sub={sm.coverage_target_pct !== null ? `Target: ${sm.coverage_target_pct}%` : undefined}
        />
        <SecondaryStatCard
          label="Duplications"
          value={sm.duplications_pct !== null ? `${sm.duplications_pct.toFixed(1)}%` : "—"}
        />
        <SecondaryStatCard
          label="Technical Debt"
          value={sm.technical_debt_display ?? "—"}
          sub={sm.maintainability_rating ? `Maintainability: ${sm.maintainability_rating}` : undefined}
        />
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { title: "Review Issues", sub: `${m.bugs + m.vulnerabilities} open issues need attention`, screen: "issues" as const },
          { title: "Ask AI Assistant", sub: "Get explanations and fix guidance", screen: "ai-assistant" as const },
          { title: "Learning Resources", sub: "4 resources recommended for you", screen: "learning" as const },
        ].map(a => (
          <button
            key={a.screen}
            onClick={() => navigate(a.screen)}
            className="bg-white border border-gray-200 rounded p-3 text-left hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div className="text-sm font-medium text-gray-900">{a.title}</div>
            <div className="text-xs text-gray-500 mt-0.5">{a.sub}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
