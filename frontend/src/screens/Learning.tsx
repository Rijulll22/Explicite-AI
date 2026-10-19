import { useEffect, useState } from "react"
import { useNav } from "../App"
import {
  apiGetLearningResources,
  apiGetLearningPaths,
  apiGetLearningProgress,
  apiCompleteResource,
  apiGetIssueResources,
  ApiError,
  type ApiLearningResource,
  type ApiLearningPath,
  type ApiLearningProgress,
  type ApiResourceRecommendation,
} from "../lib/api"

type AnyResource = ApiResourceRecommendation | ApiLearningResource

function formatStudyTime(minutes: number): string {
  if (minutes < 60) return `${minutes}min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m > 0 ? `${h}h ${m}min` : `${h}h`
}

export default function Learning() {
  const { token, selectedProjectId, selectedIssueId, selectedIssueSummary, navigate, logout, openTutor } = useNav()
  const [resources, setResources] = useState<ApiLearningResource[]>([])
  const [paths, setPaths] = useState<ApiLearningPath[]>([])
  const [progress, setProgress] = useState<ApiLearningProgress | null>(null)
  const [issueRecs, setIssueRecs] = useState<ApiResourceRecommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set())
  const [completing, setCompleting] = useState<string | null>(null)
  const [completeError, setCompleteError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) { logout(); return }
    let cancelled = false
    setLoading(true)
    setError(null)
    setIssueRecs([])

    const issueFilters = selectedIssueSummary
      ? { issueType: selectedIssueSummary.type, ruleKey: selectedIssueSummary.rule ?? undefined }
      : {}

    const recsFetch =
      selectedProjectId && selectedIssueId
        ? apiGetIssueResources(token, selectedProjectId, selectedIssueId)
        : Promise.resolve([] as ApiResourceRecommendation[])

    Promise.all([
      apiGetLearningResources(token, issueFilters),
      apiGetLearningPaths(token),
      apiGetLearningProgress(token),
      recsFetch,
    ])
      .then(([res, p, prog, recs]) => {
        if (cancelled) return
        setResources(res)
        setPaths(p)
        setProgress(prog)
        // Initialise completed state from the server so it survives a page reload
        setCompletedIds(new Set(prog.completed_resource_ids ?? []))
        setIssueRecs(recs)
        setLoading(false)
      })
      .catch(err => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) { logout(); return }
        setError(err instanceof Error ? err.message : "Failed to load learning resources")
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [token, selectedIssueSummary?.id, selectedProjectId])

  async function markComplete(resourceId: string) {
    if (!token) { logout(); return }
    if (completing) return
    setCompleting(resourceId)
    setCompleteError(null)
    try {
      await apiCompleteResource(token, resourceId)
      setCompletedIds(prev => new Set([...prev, resourceId]))
      const updated = await apiGetLearningProgress(token)
      setProgress(updated)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { logout(); return }
      setCompleteError(err instanceof Error ? err.message : "Failed to mark complete")
    } finally {
      setCompleting(null)
    }
  }

  // Use server-side recommendations when available; fall back to client filter
  const contextResources: (ApiResourceRecommendation | ApiLearningResource)[] =
    issueRecs.length > 0
      ? issueRecs
      : selectedIssueSummary
        ? resources.filter(r =>
            r.related_rule_key === (selectedIssueSummary.rule ?? null) ||
            r.related_issue_type === selectedIssueSummary.type,
          )
        : []

  const contextIds = new Set(contextResources.map(r => r.id))

  const generalResources = selectedIssueSummary
    ? resources.filter(r => !contextIds.has(r.id))
    : resources

  const projectName = selectedProjectId ? "this project" : "your projects"

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Learning & Recommendations</h2>
        <p className="text-sm text-gray-500">
          Resources recommended based on detected issues in {projectName}
        </p>
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">{error}</div>
      )}
      {completeError && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">
          Could not save completion: {completeError}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-gray-400 text-center py-12">Loading learning resources…</div>
      ) : (
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-5">

            {/* Recommended for current issue */}
            {selectedIssueSummary && contextResources.length > 0 && (
              <div className="bg-white border border-gray-200 rounded overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">Recommended for Your Current Issue</h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {selectedIssueSummary.title} ·{" "}
                      <button onClick={() => navigate("issue-detail")} className="text-blue-600 hover:underline">
                        View issue →
                      </button>
                    </p>
                  </div>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded font-medium border ${
                      selectedIssueSummary.severity === "Critical" || selectedIssueSummary.severity === "High"
                        ? "bg-red-50 border-red-200 text-red-600"
                        : selectedIssueSummary.severity === "Medium"
                        ? "bg-amber-50 border-amber-200 text-amber-600"
                        : "bg-gray-50 border-gray-200 text-gray-600"
                    }`}
                  >
                    {selectedIssueSummary.severity}
                  </span>
                </div>
                <div className="divide-y divide-gray-100">
                  {contextResources.map((r, i) => {
                    const done = completedIds.has(r.id)
                    const matchReason = "match_reason" in r ? r.match_reason : null
                    return (
                      <div
                        key={r.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => openTutor(r as ApiLearningResource)}
                        onKeyDown={e => e.key === "Enter" && openTutor(r as ApiLearningResource)}
                        className="flex items-start gap-3 p-4 hover:bg-blue-50 cursor-pointer transition-colors"
                      >
                        <div className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 ${done ? "bg-green-50 text-green-600" : "bg-red-50 text-red-600"}`}>
                          {done ? "✓" : i + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900 hover:text-blue-700">{r.title}</div>
                          {r.description && (
                            <div className="text-xs text-gray-500 mt-0.5">{r.description}</div>
                          )}
                          {matchReason && (
                            <div className="text-xs text-blue-600 mt-0.5 italic">{matchReason}</div>
                          )}
                          <div className="text-xs text-gray-400 mt-1">
                            {r.resource_type}
                            {r.duration_minutes ? ` · ${r.duration_minutes} min read` : ""}
                            <span className="ml-1 text-blue-500">· Start learning →</span>
                          </div>
                        </div>
                        {!done && (
                          <button
                            onClick={e => { e.stopPropagation(); markComplete(r.id) }}
                            disabled={completing === r.id}
                            className="shrink-0 text-xs px-2 py-1 border border-gray-200 rounded hover:border-green-400 hover:text-green-600 text-gray-400 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {completing === r.id ? "…" : "Mark complete"}
                          </button>
                        )}
                        {done && (
                          <span className="shrink-0 text-xs text-green-600 font-medium">Completed</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* General resources */}
            {generalResources.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  {selectedIssueSummary && contextResources.length > 0
                    ? "General Recommended Learning"
                    : "Learning Resources"}
                </h3>
                <div className="space-y-2">
                  {generalResources.map(r => {
                    const done = completedIds.has(r.id)
                    return (
                      <div
                        key={r.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => openTutor(r)}
                        onKeyDown={e => e.key === "Enter" && openTutor(r)}
                        className={`bg-white border rounded p-3 flex items-center gap-3 transition-colors cursor-pointer ${done ? "border-green-200 hover:border-green-400" : "border-gray-200 hover:border-blue-400 hover:bg-blue-50"}`}
                      >
                        <div
                          className={`w-8 h-8 rounded flex items-center justify-center text-xs font-bold shrink-0 ${
                            done ? "bg-green-50 text-green-600" : r.tag === "Security" ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"
                          }`}
                        >
                          {done ? "✓" : r.resource_type[0]}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900 hover:text-blue-700">{r.title}</div>
                          <div className="text-xs text-gray-400 mt-0.5">
                            {r.resource_type}
                            {r.duration_minutes ? ` · ${r.duration_minutes} min read` : ""}
                            <span className="ml-1 text-blue-500">· Start learning →</span>
                          </div>
                        </div>
                        {r.tag && !done && (
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${
                              r.tag === "Security" ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"
                            }`}
                          >
                            {r.tag}
                          </span>
                        )}
                        {!done ? (
                          <button
                            onClick={e => { e.stopPropagation(); markComplete(r.id) }}
                            disabled={completing === r.id}
                            className="shrink-0 text-xs px-2 py-1 border border-gray-200 rounded hover:border-green-400 hover:text-green-600 text-gray-400 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {completing === r.id ? "…" : "Mark complete"}
                          </button>
                        ) : (
                          <span className="shrink-0 text-xs text-green-600 font-medium">Completed</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Learning paths */}
            {paths.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Learning Paths</h3>
                <div className="space-y-2">
                  {paths.map(p => (
                    <div
                      key={p.id}
                      className="bg-white border border-gray-200 rounded p-4 hover:border-blue-300 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="text-sm font-medium text-gray-900">{p.name}</div>
                        <span className="text-xs text-gray-400">
                          {p.module_count} modules · {Math.round(p.progress_pct * 100)}% complete
                        </span>
                      </div>
                      {p.description && (
                        <p className="text-xs text-gray-500 mb-2">{p.description}</p>
                      )}
                      <div className="w-full bg-gray-100 rounded-full h-1.5">
                        <div
                          className="bg-blue-500 h-1.5 rounded-full"
                          style={{ width: `${Math.round(p.progress_pct * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {!loading && resources.length === 0 && paths.length === 0 && (
              <div className="text-sm text-gray-400 text-center py-12">No learning resources available.</div>
            )}
          </div>

          {/* Right sidebar */}
          <div className="space-y-4">
            <div className="bg-white border border-gray-200 rounded p-4">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Learning Progress</h3>
              {progress ? (
                <div className="space-y-2.5">
                  {(
                    [
                      ["Articles read", `${progress.resources_completed} / ${progress.resources_total}`],
                      ["Tutorials completed", `${progress.tutorials_completed} / ${progress.tutorials_total}`],
                      ["Paths started", String(progress.paths_started)],
                      [
                        "Total study time",
                        progress.total_study_minutes > 0 ? formatStudyTime(progress.total_study_minutes) : "—",
                      ],
                    ] as [string, string][]
                  ).map(([label, value]) => (
                    <div key={label} className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">{label}</span>
                      <span className="text-xs font-semibold text-gray-900">{value}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-gray-400 italic">Loading…</div>
              )}
            </div>

            <div className="bg-white border border-gray-200 rounded p-4">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Recently Detected Issues</h3>
              <p className="text-xs text-gray-400">
                <button onClick={() => navigate("issues")} className="text-blue-600 hover:underline">
                  View all issues →
                </button>
              </p>
            </div>

            {resources.length > 0 && (
              <div className="bg-white border border-gray-200 rounded p-4">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Topic Tags</h3>
                <div className="flex flex-wrap gap-1.5">
                  {Array.from(new Set(resources.flatMap(r => [r.tag, r.related_issue_type]).filter(Boolean))).map(
                    tag => (
                      <span
                        key={tag}
                        className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded hover:bg-blue-50 hover:text-blue-600 cursor-pointer"
                      >
                        {tag}
                      </span>
                    ),
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
