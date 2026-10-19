import { createContext, useContext, useEffect, useState } from "react"
import Sidebar from "./components/Sidebar"
import Login from "./screens/Login"
import Dashboard from "./screens/Dashboard"
import Issues from "./screens/Issues"
import IssueDetail from "./screens/IssueDetail"
import AIAssistant from "./screens/AIAssistant"
import SuggestedFix from "./screens/SuggestedFix"
import CodeAnalysis from "./screens/CodeAnalysis"
import Learning from "./screens/Learning"
import TutorSession from "./screens/TutorSession"
import Projects from "./screens/Projects"
import Settings from "./screens/Settings"
import { type UserPublic, type ApiIssueSummary, type UserPreferences, type ApiLearningResource, DEFAULT_PREFERENCES, getStoredToken, storeToken, clearToken } from "./lib/api"
import { applyAppearance, loadAppearance } from "./lib/appearance"

export type Screen =
  | "login"
  | "dashboard"
  | "issues"
  | "issue-detail"
  | "ai-assistant"
  | "suggested-fix"
  | "code-analysis"
  | "learning"
  | "tutor"
  | "projects"
  | "settings"

interface NavState {
  screen: Screen
  navigate: (s: Screen) => void
  // Auth
  token: string | null
  currentUser: UserPublic | null
  login: (token: string, user: UserPublic) => void
  logout: () => void
  // Project / issue selection
  selectedProjectId: string | null
  selectedProjectName: string | null
  openProject: (id: string, name: string) => void
  selectedIssueId: string | null
  selectedIssueSummary: ApiIssueSummary | null
  openIssue: (id: string, summary?: ApiIssueSummary) => void
  selectedFixId: string | null
  openFix: (fixId: string) => void
  updateCurrentUser: (user: UserPublic) => void
  // Derived preferences shortcut (from currentUser.preferences)
  preferences: UserPreferences
  // Learning tutor
  selectedLearningResource: ApiLearningResource | null
  openTutor: (resource: ApiLearningResource) => void
}

export const NavCtx = createContext<NavState>({
  screen: "login",
  navigate: () => {},
  token: null,
  currentUser: null,
  login: () => {},
  logout: () => {},
  selectedProjectId: null,
  selectedProjectName: null,
  openProject: () => {},
  selectedIssueId: null,
  selectedIssueSummary: null,
  openIssue: () => {},
  selectedFixId: null,
  openFix: () => {},
  updateCurrentUser: () => {},
  preferences: DEFAULT_PREFERENCES,
  selectedLearningResource: null,
  openTutor: () => {},
})
export const useNav = () => useContext(NavCtx)

function initials(name: string): string {
  return name.split(" ").map(w => w[0] ?? "").join("").slice(0, 2).toUpperCase()
}

function AppHeader({ currentUser, projectName }: { currentUser: UserPublic | null; projectName: string | null }) {
  const displayName = currentUser?.full_name ?? "Jane Doe"
  const displayInitials = currentUser ? initials(currentUser.full_name) : "JD"
  const displayProject = projectName ?? "Student Management System"

  return (
    <header className="h-11 border-b border-gray-200 bg-white flex items-center px-4 gap-3 shrink-0">
      <span className="font-semibold text-gray-900 text-sm">{displayProject}</span>
      <span className="text-gray-300">·</span>
      <span className="text-gray-500 font-mono text-xs">main</span>
      <div className="ml-auto flex items-center gap-3">
        <span className="text-xs text-gray-400">{displayName}</span>
        <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-semibold select-none">
          {displayInitials}
        </div>
      </div>
    </header>
  )
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("login")
  const [token, setToken] = useState<string | null>(getStoredToken)
  const [currentUser, setCurrentUser] = useState<UserPublic | null>(null)

  // Apply saved appearance settings on first render
  useEffect(() => { applyAppearance(loadAppearance()) }, [])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [selectedProjectName, setSelectedProjectName] = useState<string | null>(null)
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null)
  const [selectedIssueSummary, setSelectedIssueSummary] = useState<ApiIssueSummary | null>(null)
  const [selectedFixId, setSelectedFixId] = useState<string | null>(null)
  const [selectedLearningResource, setSelectedLearningResource] = useState<ApiLearningResource | null>(null)

  function login(newToken: string, user: UserPublic) {
    storeToken(newToken)
    setToken(newToken)
    setCurrentUser(user)
    setScreen("projects")
  }

  function logout() {
    clearToken()
    setToken(null)
    setCurrentUser(null)
    setSelectedProjectId(null)
    setSelectedProjectName(null)
    setSelectedIssueId(null)
    setSelectedIssueSummary(null)
    setSelectedFixId(null)
    setScreen("login")
  }

  function openProject(id: string, name: string) {
    setSelectedProjectId(id)
    setSelectedProjectName(name)
    setScreen("dashboard")
  }

  function openIssue(id: string, summary?: ApiIssueSummary) {
    setSelectedIssueId(id)
    setSelectedIssueSummary(summary ?? null)
    setScreen("issue-detail")
  }

  function openFix(fixId: string) {
    setSelectedFixId(fixId)
    setScreen("suggested-fix")
  }

  function openTutor(resource: ApiLearningResource) {
    setSelectedLearningResource(resource)
    setScreen("tutor")
  }

  function updateCurrentUser(user: UserPublic) {
    setCurrentUser(user)
  }

  const ctx: NavState = {
    screen,
    navigate: setScreen,
    token,
    currentUser,
    login,
    logout,
    selectedProjectId,
    selectedProjectName,
    openProject,
    selectedIssueId,
    selectedIssueSummary,
    openIssue,
    selectedFixId,
    openFix,
    updateCurrentUser,
    preferences: currentUser?.preferences ?? DEFAULT_PREFERENCES,
    selectedLearningResource,
    openTutor,
  }

  if (screen === "login") {
    return (
      <NavCtx.Provider value={ctx}>
        <Login />
      </NavCtx.Provider>
    )
  }

  return (
    <NavCtx.Provider value={ctx}>
      <div className="flex h-full bg-gray-50 text-gray-900 text-sm">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <AppHeader currentUser={currentUser} projectName={selectedProjectName} />
          <main className="flex-1 overflow-y-auto">
            {screen === "dashboard" && <Dashboard />}
            {screen === "issues" && <Issues />}
            {screen === "issue-detail" && <IssueDetail />}
            {screen === "ai-assistant" && <AIAssistant />}
            {screen === "suggested-fix" && <SuggestedFix />}
            {screen === "code-analysis" && <CodeAnalysis />}
            {screen === "learning" && <Learning />}
            {screen === "tutor" && <TutorSession />}
            {screen === "projects" && <Projects />}
            {screen === "settings" && <Settings />}
          </main>
        </div>
      </div>
    </NavCtx.Provider>
  )
}
