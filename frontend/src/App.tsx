import { createContext, useContext, useState } from "react"
import Sidebar from "./components/Sidebar"
import Login from "./screens/Login"
import Dashboard from "./screens/Dashboard"
import Issues from "./screens/Issues"
import IssueDetail from "./screens/IssueDetail"
import AIAssistant from "./screens/AIAssistant"
import SuggestedFix from "./screens/SuggestedFix"
import CodeAnalysis from "./screens/CodeAnalysis"
import Learning from "./screens/Learning"
import Projects from "./screens/Projects"
import Settings from "./screens/Settings"

export type Screen =
  | "login"
  | "dashboard"
  | "issues"
  | "issue-detail"
  | "ai-assistant"
  | "suggested-fix"
  | "code-analysis"
  | "learning"
  | "projects"
  | "settings"

interface NavState {
  screen: Screen
  navigate: (s: Screen) => void
}

export const NavCtx = createContext<NavState>({ screen: "login", navigate: () => {} })
export const useNav = () => useContext(NavCtx)

function AppHeader() {
  return (
    <header className="h-11 border-b border-gray-200 bg-white flex items-center px-4 gap-3 shrink-0">
      <span className="font-semibold text-gray-900 text-sm">Student Management System</span>
      <span className="text-gray-300">·</span>
      <span className="text-gray-500 font-mono text-xs">student-mgmt-v2 / main</span>
      <span className="text-gray-300">·</span>
      <span className="text-gray-500 text-xs">Last analysis: 2h ago</span>
      <div className="ml-auto flex items-center gap-3">
        <span className="text-xs text-gray-400">Jane Doe</span>
        <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-semibold select-none">
          JD
        </div>
      </div>
    </header>
  )
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("login")

  if (screen === "login") {
    return (
      <NavCtx.Provider value={{ screen, navigate: setScreen }}>
        <Login />
      </NavCtx.Provider>
    )
  }

  return (
    <NavCtx.Provider value={{ screen, navigate: setScreen }}>
      <div className="flex h-full bg-gray-50 text-gray-900 text-sm">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <AppHeader />
          <main className="flex-1 overflow-y-auto">
            {screen === "dashboard" && <Dashboard />}
            {screen === "issues" && <Issues />}
            {screen === "issue-detail" && <IssueDetail />}
            {screen === "ai-assistant" && <AIAssistant />}
            {screen === "suggested-fix" && <SuggestedFix />}
            {screen === "code-analysis" && <CodeAnalysis />}
            {screen === "learning" && <Learning />}
            {screen === "projects" && <Projects />}
            {screen === "settings" && <Settings />}
          </main>
        </div>
      </div>
    </NavCtx.Provider>
  )
}
