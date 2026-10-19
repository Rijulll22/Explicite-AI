const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000/api/v1"

// ─── Token storage (sessionStorage: cleared when tab closes) ──────────────────
const TOKEN_KEY = "explicite_token"

export function getStoredToken(): string | null {
  try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function storeToken(token: string): void {
  try { sessionStorage.setItem(TOKEN_KEY, token) } catch {}
}
export function clearToken(): void {
  try { sessionStorage.removeItem(TOKEN_KEY) } catch {}
}

// ─── Response types ───────────────────────────────────────────────────────────
export interface UserPreferences {
  email_notifications: string
  default_issue_sort: string
  ai_explain_level: string
  default_branch: string
  auto_run_analysis: string
  analysis_exclusions: string
  quality_gate_max_bugs: number
  quality_gate_max_vulnerabilities: number
  quality_gate_max_code_smells: number
  quality_gate_coverage_threshold: number
  quality_gate_debt_hours: number
}

export const DEFAULT_PREFERENCES: UserPreferences = {
  email_notifications: "Critical and High only",
  default_issue_sort: "Severity (highest first)",
  ai_explain_level: "intermediate",
  default_branch: "main",
  auto_run_analysis: "Enabled",
  analysis_exclusions: "**/test/**, **/generated/**",
  quality_gate_max_bugs: 0,
  quality_gate_max_vulnerabilities: 0,
  quality_gate_max_code_smells: 20,
  quality_gate_coverage_threshold: 0,
  quality_gate_debt_hours: 24,
}

export interface UserPublic {
  id: string
  email: string
  full_name: string
  system_role: string
  department: string | null
  experience_level: string
  is_email_verified: boolean
  created_at: string
  preferences: UserPreferences
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: UserPublic
}

export interface ApiProject {
  id: string
  name: string
  status: string
  bugs: number
  vulnerabilities: number
  code_smells: number
  coverage: string | null
  last_analysis: string | null
  branch: string
  source_type: string | null
  archived: boolean
  risk_score: number | null
}

export interface ApiIssueSummary {
  id: string
  severity: string
  type: string
  title: string
  rule: string | null
  file: string | null
  line: number | null
  risk: string
  status: string
  created_at: string
}

export interface ApiIssueListResponse {
  total: number
  skip: number
  limit: number
  items: ApiIssueSummary[]
}

export interface ApiIssueDetail {
  id: string
  severity: string
  type: string
  title: string
  rule: string | null
  file: string | null
  line: number | null
  risk: string
  risk_score: number | null
  risk_score_version: string | null
  status: string
  description: string | null
  ai_explanation: string | null
  cwe_id: string | null
  owasp_category: string | null
  cvss_score: number | null
  cvss_vector: string | null
  cvss_version: string | null
  cvss_severity: string | null
  analysis_job_id: string
  created_at: string
  updated_at: string
}

export interface ApiSourceLine {
  number: number
  content: string
  is_target: boolean
}

export interface ApiSourceExcerpt {
  available: boolean
  file: string
  target_line: number | null
  lines: ApiSourceLine[]
  message: string | null
}

export function apiGetSourceExcerpt(
  token: string,
  projectId: string,
  issueId: string,
  contextLines = 10,
): Promise<ApiSourceExcerpt> {
  return apiFetch<ApiSourceExcerpt>(
    `/projects/${projectId}/issues/${issueId}/source?context_lines=${contextLines}`,
    {},
    token,
  )
}

export interface QualityGate {
  passed: boolean
  failed_conditions: string[]
}

export interface KeyMetrics {
  bugs: number
  bugs_delta: number | null
  vulnerabilities: number
  critical_vulnerabilities: number
  high_vulnerabilities: number
  code_smells: number
  technical_debt_display: string | null
  security_hotspots: number
  security_hotspots_needing_review: number
}

export interface SupportingMetrics {
  coverage_pct: number | null
  coverage_target_pct: number | null
  duplications_pct: number | null
  technical_debt_display: string | null
  maintainability_rating: string | null
}

export interface ApiDashboard {
  project_id: string
  project_name: string
  branch: string
  last_analysis_at: string | null
  analysis_job_id: string | null
  quality_gate: QualityGate
  metrics: KeyMetrics
  supporting_metrics: SupportingMetrics
  priority_issues: ApiIssueSummary[]
  risk_score: number | null
  risk_score_version: string | null
  open_findings: number
  findings_by_severity: Record<string, number>
}

// ─── Error class ──────────────────────────────────────────────────────────────
export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message)
    this.name = "ApiError"
  }
}

// ─── Core fetch ───────────────────────────────────────────────────────────────
async function apiFetch<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (token) headers["Authorization"] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...init, headers })

  if (!res.ok) {
    let detail: string = res.statusText
    try {
      const body = await res.json() as { detail?: unknown }
      if (typeof body.detail === "string") detail = body.detail
      else if (body.detail !== undefined) detail = JSON.stringify(body.detail)
    } catch { /* keep statusText */ }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

// ─── Public API functions ─────────────────────────────────────────────────────
export function apiLogin(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
}

export function apiGetProjects(token: string): Promise<ApiProject[]> {
  return apiFetch<ApiProject[]>("/projects", {}, token)
}

export function apiGetDashboard(token: string, projectId: string): Promise<ApiDashboard> {
  return apiFetch<ApiDashboard>(`/projects/${projectId}/dashboard`, {}, token)
}

export interface IssueFilters {
  severity?: string
  type?: string
  status?: string
  q?: string
}

export function apiGetIssues(
  token: string,
  projectId: string,
  filters: IssueFilters = {},
): Promise<ApiIssueListResponse> {
  const p = new URLSearchParams()
  if (filters.severity && filters.severity !== "All") p.set("severity", filters.severity)
  if (filters.type && filters.type !== "All") p.set("type", filters.type)
  if (filters.status && filters.status !== "All") p.set("status", filters.status)
  if (filters.q?.trim()) p.set("q", filters.q.trim())
  const qs = p.toString()
  return apiFetch<ApiIssueListResponse>(
    `/projects/${projectId}/issues${qs ? `?${qs}` : ""}`,
    {},
    token,
  )
}

export function apiGetIssueDetail(
  token: string,
  projectId: string,
  issueId: string,
): Promise<ApiIssueDetail> {
  return apiFetch<ApiIssueDetail>(`/projects/${projectId}/issues/${issueId}`, {}, token)
}

// ─── Learning ─────────────────────────────────────────────────────────────────
export interface ApiLearningResource {
  id: string
  title: string
  resource_type: string
  duration_minutes: number | null
  description: string | null
  tag: string | null
  related_issue_type: string | null
  related_rule_key: string | null
}

export interface ApiLearningPath {
  id: string
  name: string
  description: string | null
  module_count: number
  progress_pct: number
}

export interface ApiLearningProgress {
  resources_completed: number
  resources_total: number
  tutorials_completed: number
  tutorials_total: number
  paths_started: number
  total_study_minutes: number
  completed_resource_ids: string[]
}

export interface ApiResourceRecommendation extends ApiLearningResource {
  match_reason: string
  is_completed: boolean
}

export function apiGetLearningResources(
  token: string,
  filters: { issueType?: string; ruleKey?: string; tag?: string } = {},
): Promise<ApiLearningResource[]> {
  const p = new URLSearchParams()
  if (filters.issueType) p.set("issue_type", filters.issueType)
  if (filters.ruleKey) p.set("rule_key", filters.ruleKey)
  if (filters.tag) p.set("tag", filters.tag)
  const qs = p.toString()
  return apiFetch<ApiLearningResource[]>(`/learning/resources${qs ? `?${qs}` : ""}`, {}, token)
}

export function apiGetLearningPaths(token: string): Promise<ApiLearningPath[]> {
  return apiFetch<ApiLearningPath[]>("/learning/paths", {}, token)
}

export function apiGetLearningProgress(token: string): Promise<ApiLearningProgress> {
  return apiFetch<ApiLearningProgress>("/learning/progress", {}, token)
}

// ─── Tutor ────────────────────────────────────────────────────────────────────
export interface ApiTutorMessage {
  id: string
  session_id: string
  role: "user" | "assistant"
  content: string
  created_at: string
}

export interface ApiTutorSession {
  session_id: string
  resource: ApiLearningResource
  messages: ApiTutorMessage[]
}

export interface ApiTutorChatResponse {
  message: ApiTutorMessage
  model_provider: string
  model_name: string
}

export function apiStartTutorSession(token: string, resourceId: string): Promise<ApiTutorSession> {
  return apiFetch<ApiTutorSession>("/learning/tutor/start", {
    method: "POST",
    body: JSON.stringify({ resource_id: resourceId }),
  }, token)
}

export function apiTutorChat(
  token: string,
  sessionId: string,
  message: string,
): Promise<ApiTutorChatResponse> {
  return apiFetch<ApiTutorChatResponse>(`/learning/tutor/${sessionId}/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  }, token)
}

// ─── Profile update ───────────────────────────────────────────────────────────
export interface PreferencesUpdateRequest {
  email_notifications?: string
  default_issue_sort?: string
  ai_explain_level?: string
  default_branch?: string
  auto_run_analysis?: string
  analysis_exclusions?: string
  quality_gate_max_bugs?: number
  quality_gate_max_vulnerabilities?: number
  quality_gate_max_code_smells?: number
  quality_gate_coverage_threshold?: number
  quality_gate_debt_hours?: number
}

export interface ProfileUpdateRequest {
  full_name?: string
  department?: string
  experience_level?: string
  preferences?: PreferencesUpdateRequest
}

export function apiUpdateProfile(token: string, data: ProfileUpdateRequest): Promise<UserPublic> {
  return apiFetch<UserPublic>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  }, token)
}

export function apiGetMe(token: string): Promise<UserPublic> {
  return apiFetch<UserPublic>("/auth/me", {}, token)
}

// ─── Project creation ─────────────────────────────────────────────────────────
export interface ProjectCreateRequest {
  name: string
  description?: string
  default_branch?: string
}

export function apiCreateProject(token: string, data: ProjectCreateRequest): Promise<ApiProject> {
  return apiFetch<ApiProject>("/projects", {
    method: "POST",
    body: JSON.stringify(data),
  }, token)
}

// ─── Issue status update ──────────────────────────────────────────────────────
export function apiUpdateIssueStatus(
  token: string,
  projectId: string,
  issueId: string,
  status: string,
): Promise<ApiIssueDetail> {
  return apiFetch<ApiIssueDetail>(
    `/projects/${projectId}/issues/${issueId}`,
    { method: "PATCH", body: JSON.stringify({ status }) },
    token,
  )
}

// ─── Analysis pipeline ───────────────────────────────────────────────────────
export interface ApiAnalysisJob {
  id: string
  project_id: string
  status: string   // queued | running | completed | failed | cancelled
  created_at: string
  started_at: string | null
  completed_at: string | null
  failed_at: string | null
  failure_reason: string | null
  engine_name: string | null
  engine_version: string | null
  findings_count: number | null
  bugs_count: number
  vulnerabilities_count: number
  code_smells_count: number
  security_hotspots_count: number
}

export function apiSubmitAnalysis(
  token: string,
  projectId: string,
  file: File,
): Promise<ApiAnalysisJob> {
  const form = new FormData()
  form.append("source", file)
  // Do NOT set Content-Type header — browser sets it with boundary
  const headers: Record<string, string> = { "Authorization": `Bearer ${token}` }
  return fetch(`${BASE}/projects/${projectId}/analyse`, {
    method: "POST",
    headers,
    body: form,
  }).then(async (res) => {
    if (!res.ok) {
      let detail: string = res.statusText
      try {
        const body = await res.json() as { detail?: unknown }
        if (typeof body.detail === "string") detail = body.detail
        else if (body.detail !== undefined) detail = JSON.stringify(body.detail)
      } catch { /* keep statusText */ }
      throw new ApiError(res.status, detail)
    }
    return res.json() as Promise<ApiAnalysisJob>
  })
}

export function apiGetAnalysisJob(
  token: string,
  projectId: string,
  jobId: string,
): Promise<ApiAnalysisJob> {
  return apiFetch<ApiAnalysisJob>(`/projects/${projectId}/analyse/${jobId}`, {}, token)
}

export function apiListAnalysisJobs(
  token: string,
  projectId: string,
): Promise<ApiAnalysisJob[]> {
  return apiFetch<ApiAnalysisJob[]>(`/projects/${projectId}/analyse`, {}, token)
}

// ─── AI — explanations and assistant ────────────────────────────────────────

export interface ApiExplainRequest {
  level?: "beginner" | "intermediate" | "advanced"
  force?: boolean
}

export interface ApiExplainResponse {
  finding_id: string
  what: string
  why: string
  how_it_arises: string
  remediation: string
  caveats: string
  model_provider: string
  model_name: string
  grounded_in_finding: boolean
  source_context_available: boolean
  cached: boolean
}

export interface ApiAssistantResponse {
  reply: string
  model_provider: string
  model_name: string
  grounded: boolean
}

export function apiExplainIssue(
  token: string,
  projectId: string,
  issueId: string,
  options: ApiExplainRequest = {},
): Promise<ApiExplainResponse> {
  return apiFetch<ApiExplainResponse>(
    `/projects/${projectId}/issues/${issueId}/explain`,
    { method: "POST", body: JSON.stringify({ level: "intermediate", force: false, ...options }) },
    token,
  )
}

export function apiAskAssistant(
  token: string,
  projectId: string,
  message: string,
  issueId?: string,
): Promise<ApiAssistantResponse> {
  return apiFetch<ApiAssistantResponse>(
    `/projects/${projectId}/assistant`,
    {
      method: "POST",
      body: JSON.stringify({ message, ...(issueId ? { issue_id: issueId } : {}) }),
    },
    token,
  )
}

// ─── Suggested fixes ─────────────────────────────────────────────────────────

export interface ApiFixResponse {
  id: string
  finding_id: string
  project_id: string
  analysis_job_id: string
  target_file: string | null
  original_snippet: string | null
  proposed_snippet: string | null
  unified_diff: string | null
  snippet_start_line: number | null
  snippet_end_line: number | null
  rationale: string | null
  caveats: string | null
  status: string   // proposed | approved | rejected | applied | failed | stale
  source_available: boolean
  model_provider: string | null
  model_name: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
  rejected_at: string | null
  applied_at: string | null
}

export interface ApiFixSummary {
  id: string
  finding_id: string
  status: string
  target_file: string | null
  model_provider: string | null
  model_name: string | null
  created_at: string
}

export function apiGenerateFix(
  token: string,
  projectId: string,
  issueId: string,
): Promise<ApiFixResponse> {
  return apiFetch<ApiFixResponse>(
    `/projects/${projectId}/issues/${issueId}/fix`,
    { method: "POST" },
    token,
  )
}

export function apiGetFix(
  token: string,
  projectId: string,
  fixId: string,
): Promise<ApiFixResponse> {
  return apiFetch<ApiFixResponse>(`/projects/${projectId}/fixes/${fixId}`, {}, token)
}

export function apiListFixes(
  token: string,
  projectId: string,
  issueId: string,
): Promise<ApiFixSummary[]> {
  return apiFetch<ApiFixSummary[]>(
    `/projects/${projectId}/issues/${issueId}/fixes`,
    {},
    token,
  )
}

export function apiApproveFix(
  token: string,
  projectId: string,
  fixId: string,
): Promise<ApiFixResponse> {
  return apiFetch<ApiFixResponse>(
    `/projects/${projectId}/fixes/${fixId}/approve`,
    { method: "POST" },
    token,
  )
}

export function apiRejectFix(
  token: string,
  projectId: string,
  fixId: string,
): Promise<ApiFixResponse> {
  return apiFetch<ApiFixResponse>(
    `/projects/${projectId}/fixes/${fixId}/reject`,
    { method: "POST" },
    token,
  )
}

export function apiDownloadFix(
  token: string,
  projectId: string,
  fixId: string,
): Promise<Blob> {
  // Download returns a ZIP blob — cannot use apiFetch (not JSON)
  return fetch(`${BASE}/projects/${projectId}/fixes/${fixId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then(async (res) => {
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json() as { detail?: unknown }
        if (typeof body.detail === "string") detail = body.detail
      } catch { /* keep statusText */ }
      throw new ApiError(res.status, detail)
    }
    return res.blob()
  })
}

// ─── Resource completion ──────────────────────────────────────────────────────
export interface ResourceCompleteResponse {
  completed: boolean
  resource_id: string
}

export function apiCompleteResource(
  token: string,
  resourceId: string,
): Promise<ResourceCompleteResponse> {
  return apiFetch<ResourceCompleteResponse>(
    `/learning/resources/${resourceId}/complete`,
    { method: "POST" },
    token,
  )
}

// ─── Learning recommendations ─────────────────────────────────────────────────

export function apiGetIssueResources(
  token: string,
  projectId: string,
  issueId: string,
): Promise<ApiResourceRecommendation[]> {
  return apiFetch<ApiResourceRecommendation[]>(
    `/projects/${projectId}/issues/${issueId}/learning`,
    {},
    token,
  )
}

export function apiGetProjectRecommendations(
  token: string,
  projectId: string,
): Promise<ApiResourceRecommendation[]> {
  return apiFetch<ApiResourceRecommendation[]>(
    `/projects/${projectId}/learning/recommend`,
    {},
    token,
  )
}
