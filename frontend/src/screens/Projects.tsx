import { useNav } from "../App"
import { projects } from "../data"

export default function Projects() {
  const { navigate } = useNav()
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Projects</h2>
          <p className="text-sm text-gray-500">{projects.length} projects</p>
        </div>
        <button className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 font-medium">Add Project</button>
      </div>
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
            {projects.map(p => (
              <tr key={p.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="text-sm font-medium text-gray-900">{p.name}</div>
                  <div className="text-xs font-mono text-gray-400">{p.branch}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded ${p.status === "Passed" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${p.status === "Passed" ? "bg-green-500" : "bg-red-500"}`} />
                    {p.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm font-semibold text-red-600">{p.bugs}</td>
                <td className="px-4 py-3 text-sm font-semibold text-orange-600">{p.vulnerabilities}</td>
                <td className="px-4 py-3 text-sm text-amber-600">{p.codeSmells}</td>
                <td className="px-4 py-3 text-sm text-gray-700">{p.coverage}</td>
                <td className="px-4 py-3 text-xs text-gray-400">{p.lastAnalysis}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => navigate("dashboard")}
                      className="text-xs text-blue-600 hover:underline font-medium"
                    >
                      Open
                    </button>
                    <button className="text-xs text-gray-400 hover:text-gray-700">Analyse</button>
                    <button className="text-xs text-gray-400 hover:text-gray-700">Settings</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
