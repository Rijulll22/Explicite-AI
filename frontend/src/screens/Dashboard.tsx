import { useNav } from "../App"
import { issues } from "../data"
import SeverityBadge from "../components/SeverityBadge"

function StatCard({ label, value, color, sub }: { label: string; value: string | number; color: string; sub?: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded p-4">
      <div className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
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

export default function Dashboard() {
  const { navigate } = useNav()
  const priority = issues.filter(i => i.severity === "Critical" || i.severity === "High").slice(0, 5)

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Project Dashboard</h2>
          <p className="text-sm text-gray-500">Student Management System · Last analysis: 15 Sep 2026, 14:32</p>
        </div>
        <button className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 font-medium">Run Analysis</button>
      </div>

      {/* Project Health — Quality Gate (primary emphasis) */}
      <div className="bg-white border border-gray-200 rounded p-4 mb-5">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Project Health</div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 rounded-full bg-red-500 shrink-0" />
            <div>
              <div className="font-semibold text-gray-900 text-base">Quality Gate: Failed</div>
              <div className="text-xs text-gray-500 mt-0.5">3 conditions failed — coverage below threshold, critical vulnerabilities detected, bug count exceeds limit</div>
            </div>
          </div>
          <div className="ml-auto flex gap-6 text-center shrink-0">
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide">Analysis</div>
              <div className="text-sm font-semibold text-gray-900 mt-0.5">15 Sep 2026</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide">Branch</div>
              <div className="text-sm font-mono font-semibold text-gray-900 mt-0.5">main</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide">Version</div>
              <div className="text-sm font-semibold text-gray-900 mt-0.5">v2.3.1</div>
            </div>
          </div>
        </div>
      </div>

      {/* Primary metrics */}
      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Key Metrics</div>
      <div className="grid grid-cols-4 gap-3 mb-5">
        <StatCard label="Bugs" value={12} color="text-red-600" sub="+2 since last analysis" />
        <StatCard label="Vulnerabilities" value={3} color="text-orange-600" sub="2 Critical, 1 High" />
        <StatCard label="Code Smells" value={24} color="text-amber-600" sub="~4h technical debt" />
        <StatCard label="Security Hotspots" value={5} color="text-purple-600" sub="2 need review" />
      </div>

      {/* Priority Issues — most important action area */}
      <div className="bg-white border border-gray-200 rounded mb-5">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">Priority Issues</h3>
            <p className="text-xs text-gray-400 mt-0.5">Highest severity issues requiring immediate attention</p>
          </div>
          <button onClick={() => navigate("issues")} className="text-xs text-blue-600 hover:underline">View all issues →</button>
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
              {["Severity", "Issue", "File", "Line", "Action"].map(h => (
                <th key={h} className="text-left px-4 py-2 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {priority.map(issue => (
              <tr
                key={issue.id}
                className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                onClick={() => navigate("issue-detail")}
              >
                <td className="px-4 py-2.5"><SeverityBadge severity={issue.severity} /></td>
                <td className="px-4 py-2.5 text-sm font-medium text-gray-900">{issue.title}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-gray-500">{issue.file}</td>
                <td className="px-4 py-2.5 text-sm text-gray-500">{issue.line}</td>
                <td className="px-4 py-2.5">
                  <button
                    className="text-xs text-blue-600 hover:underline"
                    onClick={e => { e.stopPropagation(); navigate("issue-detail") }}
                  >
                    View →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Supporting metrics — visually quieter */}
      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Supporting Metrics</div>
      <div className="grid grid-cols-3 gap-3 mb-5">
        <SecondaryStatCard label="Coverage" value="64%" sub="Target: 80%" />
        <SecondaryStatCard label="Duplications" value="8.3%" sub="1,240 lines" />
        <SecondaryStatCard label="Technical Debt" value="3d 2h" sub="Maintainability: C" />
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { title: "Review Issues", sub: "12 open issues need attention", screen: "issues" as const },
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
