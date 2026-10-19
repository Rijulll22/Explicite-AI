import { useEffect, useRef, useState } from "react"
import { useNav } from "../App"
import {
  apiGetProjects,
  apiCreateProject,
  apiSubmitAnalysis,
  apiGetAnalysisJob,
  type ApiProject,
  type ApiAnalysisJob,
  ApiError,
} from "../lib/api"

// ─── Create project modal ─────────────────────────────────────────────────────

interface CreateModalProps {
  token: string
  onCreated: (project: ApiProject) => void
  onClose: () => void
}

function CreateProjectModal({ token, onCreated, onClose, defaultBranch = "main" }: CreateModalProps & { defaultBranch?: string }) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [branch, setBranch] = useState(defaultBranch)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const nameRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    nameRef.current?.focus()
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmedName = name.trim()
    if (!trimmedName) { setError("Project name is required."); return }
    if (trimmedName.length > 255) { setError("Project name must be 255 characters or fewer."); return }
    setSaving(true)
    setError(null)
    try {
      const created = await apiCreateProject(token, {
        name: trimmedName,
        description: description.trim() || undefined,
        default_branch: branch.trim() || "main",
      })
      onCreated(created)
    } catch (err) {
      setSaving(false)
      if (err instanceof ApiError) {
        setError(err.message || "Failed to create project.")
      } else {
        setError(err instanceof Error ? err.message : "Failed to create project.")
      }
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 text-sm">Create New Project</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Project name <span className="text-red-500">*</span>
            </label>
            <input
              ref={nameRef}
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              maxLength={255}
              placeholder="e.g. Student Management System"
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Description <span className="text-gray-400">(optional)</span></label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={2}
              maxLength={2000}
              placeholder="Short description of the project"
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 resize-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Default branch</label>
            <input
              type="text"
              value={branch}
              onChange={e => setBranch(e.target.value)}
              placeholder="main"
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          {error && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Creating…" : "Create Project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── ZIP upload modal (reused per-row Analyse button) ────────────────────────

function AnalyseModal({
  projectName,
  onClose,
  onSubmit,
}: {
  projectName: string
  onClose: () => void
  onSubmit: (file: File) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 text-sm">Analyse: {projectName}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
        </div>
        <div className="px-5 py-4">
          <p className="text-sm text-gray-500 mb-4">
            Upload a ZIP archive of your source files (max 10 MB).<br />
            Supported: <span className="font-mono text-xs">.py .java .js .ts .jsx .tsx</span>
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
          <div className="flex gap-2 justify-end">
            <button
              onClick={onClose}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              disabled={!file}
              onClick={() => file && onSubmit(file)}
              className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Start Analysis
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Projects screen ──────────────────────────────────────────────────────────

export default function Projects() {
  const { token, openProject, logout, preferences } = useNav()
  const [projects, setProjects] = useState<ApiProject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  // Per-row analysis state: which project is being analysed
  const [analysingProject, setAnalysingProject] = useState<{ id: string; name: string } | null>(null)
  const [activeJobs, setActiveJobs] = useState<Record<string, ApiAnalysisJob>>({})
  const [analyseError, setAnalyseError] = useState<string | null>(null)

  function loadProjects() {
    if (!token) { logout(); return }
    setLoading(true)
    setError(null)
    apiGetProjects(token)
      .then(data => { setProjects(data); setLoading(false) })
      .catch(err => {
        if (err instanceof ApiError && err.status === 401) { logout(); return }
        setError(err instanceof Error ? err.message : "Failed to load projects")
        setLoading(false)
      })
  }

  useEffect(() => {
    loadProjects()
  }, [token])

  function handleCreated(project: ApiProject) {
    setShowModal(false)
    // Add to top of list then refresh full list (to get accurate metrics)
    setProjects(prev => [project, ...prev])
    loadProjects()
  }

  async function handleAnalyseSubmit(file: File) {
    if (!token || !analysingProject) return
    const { id: projectId } = analysingProject
    setAnalysingProject(null)
    setAnalyseError(null)
    try {
      const job = await apiSubmitAnalysis(token, projectId, file)
      setActiveJobs(prev => ({ ...prev, [projectId]: job }))
    } catch (err) {
      setAnalyseError(err instanceof ApiError ? err.message : "Failed to start analysis")
    }
  }

  // Poll any active jobs
  useEffect(() => {
    const running = Object.entries(activeJobs).filter(
      ([, job]) => job.status !== "completed" && job.status !== "failed"
    )
    if (!running.length || !token) return
    let cancelled = false
    const interval = setInterval(() => {
      running.forEach(([projectId, job]) => {
        apiGetAnalysisJob(token, projectId, job.id)
          .then(updated => {
            if (!cancelled) {
              setActiveJobs(prev => ({ ...prev, [projectId]: updated }))
              if (updated.status === "completed") loadProjects()
            }
          })
          .catch(() => {})
      })
    }, 2000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [activeJobs, token])

  return (
    <div className="p-6">
      {showModal && token && (
        <CreateProjectModal
          token={token}
          onCreated={handleCreated}
          onClose={() => setShowModal(false)}
          defaultBranch={preferences.default_branch}
        />
      )}
      {analysingProject && (
        <AnalyseModal
          projectName={analysingProject.name}
          onClose={() => setAnalysingProject(null)}
          onSubmit={handleAnalyseSubmit}
        />
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Projects</h2>
          <p className="text-sm text-gray-500">{loading ? "Loading…" : `${projects.length} project${projects.length === 1 ? "" : "s"}`}</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 font-medium"
        >
          Add Project
        </button>
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">{error}</div>
      )}
      {analyseError && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">
          {analyseError}
          <button onClick={() => setAnalyseError(null)} className="ml-3 text-xs underline">Dismiss</button>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-gray-400 py-12 text-center">Loading projects…</div>
      ) : (
        <div className="bg-white border border-gray-200 rounded overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-200 bg-gray-50">
                {["Project", "Quality Gate", "Bugs", "Vulnerabilities", "Code Smells", "Coverage", "Last Analysis", "Actions"].map(h => (
                  <th key={h} className="text-left px-4 py-2.5 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {projects.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-sm text-gray-400">
                    No projects yet. Click <button onClick={() => setShowModal(true)} className="text-blue-600 hover:underline">Add Project</button> to create one.
                  </td>
                </tr>
              ) : projects.map(p => (
                <tr key={p.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-gray-900">{p.name}</div>
                    <div className="text-xs font-mono text-gray-400">{p.branch}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded ${p.status === "Passed" ? "bg-green-100 text-green-700" : p.status === "Failed" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${p.status === "Passed" ? "bg-green-500" : p.status === "Failed" ? "bg-red-500" : "bg-gray-400"}`} />
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm font-semibold text-red-600">{p.bugs}</td>
                  <td className="px-4 py-3 text-sm font-semibold text-orange-600">{p.vulnerabilities}</td>
                  <td className="px-4 py-3 text-sm text-amber-600">{p.code_smells}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">{p.coverage ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{p.last_analysis ?? "Never"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => openProject(p.id, p.name)}
                        className="text-xs text-blue-600 hover:underline font-medium"
                      >
                        Open
                      </button>
                      {activeJobs[p.id] && activeJobs[p.id].status !== "completed" && activeJobs[p.id].status !== "failed" ? (
                        <span className="text-xs text-blue-500 animate-pulse">Analysing…</span>
                      ) : activeJobs[p.id]?.status === "completed" ? (
                        <span className="text-xs text-green-600">
                          ✓ {activeJobs[p.id].findings_count ?? 0} findings
                        </span>
                      ) : activeJobs[p.id]?.status === "failed" ? (
                        <button
                          onClick={() => setAnalysingProject({ id: p.id, name: p.name })}
                          className="text-xs text-red-500 hover:underline"
                          title={activeJobs[p.id].failure_reason ?? "Analysis failed"}
                        >
                          Retry
                        </button>
                      ) : (
                        <button
                          onClick={() => setAnalysingProject({ id: p.id, name: p.name })}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Analyse
                        </button>
                      )}
                      <button className="text-xs text-gray-400 hover:text-gray-700">Settings</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
