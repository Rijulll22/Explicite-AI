import { useEffect, useState } from "react"
import { useNav } from "../App"
import {
  apiGetFix,
  apiApproveFix,
  apiRejectFix,
  apiDownloadFix,
  type ApiFixResponse,
  ApiError,
} from "../lib/api"

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    proposed: "bg-blue-50 text-blue-700 border-blue-200",
    approved: "bg-green-50 text-green-700 border-green-200",
    rejected: "bg-red-50 text-red-700 border-red-200",
    applied: "bg-purple-50 text-purple-700 border-purple-200",
    stale: "bg-amber-50 text-amber-700 border-amber-200",
    failed: "bg-gray-50 text-gray-600 border-gray-200",
  }
  const cls = styles[status] ?? "bg-gray-50 text-gray-600 border-gray-200"
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium capitalize ${cls}`}>
      {status}
    </span>
  )
}

function DiffView({ diff }: { diff: string }) {
  if (!diff) {
    return <p className="text-xs text-gray-400 italic p-4">No diff available.</p>
  }
  const lines = diff.split("\n")
  return (
    <div className="code-block leading-relaxed overflow-x-auto rounded">
      {lines.map((line, i) => {
        let lineClass = ""
        if (line.startsWith("+++") || line.startsWith("---")) lineClass = "code-line-header"
        else if (line.startsWith("+")) lineClass = "code-line-add"
        else if (line.startsWith("-")) lineClass = "code-line-remove"
        else if (line.startsWith("@@")) lineClass = "code-line-meta"
        return (
          <div key={i} className={`px-4 py-px ${lineClass}`}>
            {line || " "}
          </div>
        )
      })}
    </div>
  )
}

export default function SuggestedFix() {
  const { token, selectedProjectId, selectedIssueId, selectedFixId, navigate, logout } = useNav()

  const [fix, setFix] = useState<ApiFixResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) { logout(); return }
    if (!selectedProjectId || !selectedFixId) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    apiGetFix(token, selectedProjectId, selectedFixId)
      .then(f => { if (!cancelled) { setFix(f); setLoading(false) } })
      .catch(err => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) { logout(); return }
        setError(err instanceof Error ? err.message : "Failed to load fix")
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [token, selectedProjectId, selectedFixId])

  async function handleApprove() {
    if (!token || !selectedProjectId || !fix || actionLoading) return
    setActionLoading(true)
    setActionError(null)
    try {
      const updated = await apiApproveFix(token, selectedProjectId, fix.id)
      setFix(updated)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
      setActionError(err instanceof ApiError ? err.message : "Failed to approve fix")
    } finally {
      setActionLoading(false)
    }
  }

  async function handleReject() {
    if (!token || !selectedProjectId || !fix || actionLoading) return
    setActionLoading(true)
    setActionError(null)
    try {
      const updated = await apiRejectFix(token, selectedProjectId, fix.id)
      setFix(updated)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
      setActionError(err instanceof ApiError ? err.message : "Failed to reject fix")
    } finally {
      setActionLoading(false)
    }
  }

  async function handleDownload() {
    if (!token || !selectedProjectId || !fix || actionLoading) return
    setActionLoading(true)
    setActionError(null)
    try {
      const blob = await apiDownloadFix(token, selectedProjectId, fix.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `fix-${fix.id}.zip`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      // Reload fix to pick up applied status
      const updated = await apiGetFix(token, selectedProjectId, fix.id)
      setFix(updated)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
      if (err instanceof ApiError && err.status === 409) {
        setActionError(err.message)
        // Reload to pick up stale status
        try {
          const reloaded = await apiGetFix(token, selectedProjectId, fix.id)
          setFix(reloaded)
        } catch { /* ignore */ }
      } else {
        setActionError(err instanceof Error ? err.message : "Failed to download fix")
      }
    } finally {
      setActionLoading(false)
    }
  }

  const breadcrumb = fix?.target_file
    ? `${fix.target_file}${fix.snippet_start_line ? ` · Line ${fix.snippet_start_line}` : ""}`
    : "Suggested Fix"

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-xs text-gray-400 mb-4">
        <button onClick={() => navigate("issues")} className="hover:text-blue-600 text-gray-500">Issues</button>
        {selectedIssueId && (
          <>
            <span>›</span>
            <button onClick={() => navigate("issue-detail")} className="hover:text-blue-600 text-gray-500">Issue Detail</button>
          </>
        )}
        <span>›</span>
        <span className="text-gray-900">{breadcrumb}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-xl font-semibold text-gray-900">Suggested Fix</h2>
            {fix && <StatusBadge status={fix.status} />}
          </div>
          {fix?.model_provider && (
            <p className="text-xs text-gray-400">
              Generated by {fix.model_provider} · {fix.model_name}
            </p>
          )}
        </div>
      </div>

      {loading && (
        <div className="text-sm text-gray-400 text-center py-12">Loading fix…</div>
      )}

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3 mb-4">{error}</div>
      )}

      {!loading && !error && !fix && (
        <div className="text-sm text-gray-400 text-center py-12">
          No fix selected. Go to an <button onClick={() => navigate("issue-detail")} className="text-blue-600 hover:underline">issue</button> and click Generate Fix.
        </div>
      )}

      {fix && (
        <div className="space-y-4">

          {/* Source availability notice */}
          {!fix.source_available && (
            <div className="bg-amber-50 border border-amber-200 rounded px-4 py-3 text-sm text-amber-800">
              Source code was not available when this fix was generated. The proposal is based on the finding metadata only — verify carefully before applying.
            </div>
          )}

          {/* Stale notice */}
          {fix.status === "stale" && (
            <div className="bg-amber-50 border border-amber-200 rounded px-4 py-3 text-sm text-amber-800">
              This fix is stale — the source file changed after the fix was generated. Go back and generate a new fix.
            </div>
          )}

          {/* Action error */}
          {actionError && (
            <div className="bg-red-50 border border-red-200 rounded px-4 py-3 text-sm text-red-700">{actionError}</div>
          )}

          {/* Diff panel */}
          <div className="bg-white border border-gray-200 rounded overflow-hidden">
            <div className="px-4 py-2.5 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                Proposed Change
                {fix.snippet_start_line && fix.snippet_end_line
                  ? ` — Lines ${fix.snippet_start_line}–${fix.snippet_end_line}`
                  : ""}
              </h3>
              {fix.target_file && (
                <span className="text-xs font-mono text-gray-400">{fix.target_file}</span>
              )}
            </div>
            {fix.unified_diff ? (
              <DiffView diff={fix.unified_diff} />
            ) : fix.proposed_snippet ? (
              <pre className="text-xs font-mono p-4 bg-[#1e2329] text-[#abb2bf] overflow-x-auto leading-relaxed">
                {fix.proposed_snippet}
              </pre>
            ) : (
              <div className="p-4 text-xs text-gray-400 italic">
                No diff or proposed code is available for this fix.
              </div>
            )}
          </div>

          {/* Rationale and Caveats */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white border border-gray-200 rounded p-4">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Rationale</h3>
              <p className="text-sm text-gray-700 leading-relaxed">
                {fix.rationale ?? "No rationale provided."}
              </p>
            </div>
            <div className="bg-white border border-gray-200 rounded p-4">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Caveats</h3>
              <p className="text-sm text-gray-700 leading-relaxed">
                {fix.caveats ?? "No caveats noted."}
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Actions</h3>
            <p className="text-xs text-gray-500 mb-4">
              AI-generated fixes must be reviewed and explicitly approved before download. The original source files are never modified — you receive a ZIP with the patch applied.
            </p>
            <div className="flex items-center gap-3">
              {fix.status === "proposed" && (
                <>
                  <button
                    onClick={handleApprove}
                    disabled={actionLoading}
                    className="px-4 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 font-medium disabled:opacity-60"
                  >
                    {actionLoading ? "Saving…" : "Approve Fix"}
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={actionLoading}
                    className="px-4 py-1.5 border border-red-300 text-red-700 rounded text-sm hover:bg-red-50 font-medium disabled:opacity-60"
                  >
                    Reject
                  </button>
                </>
              )}
              {fix.status === "approved" && fix.source_available && (
                <>
                  <button
                    onClick={handleDownload}
                    disabled={actionLoading}
                    className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium disabled:opacity-60"
                  >
                    {actionLoading ? "Preparing…" : "Download Patched ZIP"}
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={actionLoading}
                    className="px-4 py-1.5 border border-gray-300 text-gray-700 rounded text-sm hover:bg-gray-50 disabled:opacity-60"
                  >
                    Reject
                  </button>
                </>
              )}
              {fix.status === "approved" && !fix.source_available && (
                <p className="text-sm text-amber-700">
                  Source not available — ZIP download is not possible for this fix. Apply the proposed changes manually using the diff above.
                </p>
              )}
              {fix.status === "applied" && (
                <p className="text-sm text-purple-700 font-medium">Fix applied — ZIP has been downloaded.</p>
              )}
              {fix.status === "rejected" && (
                <p className="text-sm text-gray-500">This fix has been rejected.</p>
              )}
              {fix.status === "stale" && (
                <p className="text-sm text-amber-700">
                  Fix is stale. Go back to <button onClick={() => navigate("issue-detail")} className="text-blue-600 hover:underline">the issue</button> and generate a new fix.
                </p>
              )}
            </div>
          </div>

          <p className="text-xs text-gray-400">
            AI-generated · Not verified by automated tests · Review all proposed changes before applying
          </p>
        </div>
      )}
    </div>
  )
}
