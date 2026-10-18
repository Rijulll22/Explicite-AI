import { useNav, type Screen } from "../App"
import { DashboardIcon, IssuesIcon, ChatIcon, CodeIcon, FolderIcon, BookIcon, SettingsIcon } from "./Icons"

const navItems: { label: string; screen: Screen; Icon: React.FC<{ className?: string }> }[] = [
  { label: "Dashboard", screen: "dashboard", Icon: DashboardIcon },
  { label: "Issues", screen: "issues", Icon: IssuesIcon },
  { label: "AI Code Assistant", screen: "ai-assistant", Icon: ChatIcon },
  { label: "Code Analysis", screen: "code-analysis", Icon: CodeIcon },
  { label: "Projects", screen: "projects", Icon: FolderIcon },
  { label: "Learning", screen: "learning", Icon: BookIcon },
  { label: "Settings", screen: "settings", Icon: SettingsIcon },
]

const issueScreens: Screen[] = ["issue-detail", "suggested-fix"]

export default function Sidebar() {
  const { screen, navigate } = useNav()
  return (
    <aside className="w-52 shrink-0 border-r border-gray-200 bg-white flex flex-col">
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-blue-600 rounded flex items-center justify-center shrink-0">
            <CodeIcon className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-semibold text-gray-900 text-sm">CodeReview AI</span>
        </div>
        <div className="text-xs text-gray-400 mt-0.5 pl-8">v1.0 — University Project</div>
      </div>
      <nav className="flex-1 py-1.5 overflow-y-auto">
        {navItems.map(({ label, screen: s, Icon }) => {
          const active = screen === s || (s === "issues" && issueScreens.includes(screen))
          return (
            <button
              key={s}
              onClick={() => navigate(s)}
              className={`w-full text-left flex items-center gap-2.5 px-4 py-2 text-sm transition-colors ${
                active
                  ? "bg-blue-50 text-blue-700 font-medium border-r-2 border-blue-600"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              }`}
            >
              <Icon className={`w-4 h-4 shrink-0 ${active ? "text-blue-600" : "text-gray-400"}`} />
              {label}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
