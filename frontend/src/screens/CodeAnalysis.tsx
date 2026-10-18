import { useNav } from "../App"

const metrics = [
  { metric: "Bugs", before: 12, after: 12 },
  { metric: "Vulnerabilities", before: 3, after: 2 },
  { metric: "Code Smells", before: 24, after: 24 },
  { metric: "Security Hotspots", before: 5, after: 5 },
  { metric: "Coverage", before: "64%", after: "65%" },
  { metric: "Duplications", before: "8.3%", after: "8.3%" },
]

export default function CodeAnalysis() {
  const { navigate } = useNav()
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Code Analysis</h2>
          <p className="text-sm text-gray-500">Student Management System · 15 Sep 2026, 15:04 — Verification run</p>
        </div>
        <button className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 font-medium">Run New Analysis</button>
      </div>

      {/* Issue investigation summary — connects this screen to the workflow */}
      <div className="bg-white border border-gray-200 rounded p-4 mb-5">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Issue Investigation Summary</div>
        <div className="grid grid-cols-3 gap-6">
          <div>
            <div className="text-xs text-gray-400 mb-0.5">Issue Investigated</div>
            <div className="text-sm font-semibold text-gray-900">SQL Injection</div>
            <div className="text-xs font-mono text-gray-400 mt-0.5">StudentDAO.java:42 · java:S3649</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-0.5">Previous Status</div>
            <div className="text-sm font-semibold text-gray-700">Open</div>
            <div className="text-xs text-gray-400 mt-0.5">Detected 15 Sep 2026</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-0.5">Current Analysis</div>
            <div className="text-sm font-semibold text-green-600">Analysis Completed</div>
            <div className="text-xs text-gray-400 mt-0.5">Verification run · 15 Sep 2026, 15:04</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-5">
        {[
          { label: "Before Changes", gatePassed: false },
          { label: "After Changes", gatePassed: true },
        ].map((col, ci) => (
          <div key={col.label} className="bg-white border border-gray-200 rounded p-4">
            <div className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-3">{col.label}</div>
            <div className={`flex items-center gap-2 px-3 py-2 rounded border mb-4 ${col.gatePassed ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
              <div className={`w-2.5 h-2.5 rounded-full ${col.gatePassed ? "bg-green-500" : "bg-red-500"}`} />
              <span className={`text-sm font-semibold ${col.gatePassed ? "text-green-700" : "text-red-700"}`}>
                Quality Gate: {col.gatePassed ? "Passed" : "Failed"}
              </span>
            </div>
            <div className="space-y-2.5">
              {metrics.map(row => {
                const val = ci === 0 ? row.before : row.after
                const improved = ci === 1 && row.before !== row.after
                return (
                  <div key={row.metric} className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">{row.metric}</span>
                    <span className={`font-medium ${improved ? "text-green-600" : "text-gray-900"}`}>
                      {val}
                      {improved && <span className="text-xs text-green-500 ml-1">↓</span>}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white border border-gray-200 rounded mb-4">
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="font-medium text-gray-900 text-sm">Issues Resolved (1)</h3>
        </div>
        <div className="p-4">
          <div className="flex items-start gap-3 p-3 bg-green-50 border border-green-200 rounded">
            <span className="text-green-600 font-bold mt-0.5">✓</span>
            <div>
              <div className="text-sm font-medium text-gray-900">SQL Injection — StudentDAO.java:42</div>
              <div className="text-xs text-gray-500 mt-0.5">Resolved by applying PreparedStatement fix · rule java:S3649 · verified clean</div>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-medium text-gray-900 text-sm">Issues Remaining (7)</h3>
          <button onClick={() => navigate("issues")} className="text-xs text-blue-600 hover:underline">View all →</button>
        </div>
        <div className="divide-y divide-gray-100">
          {[
            { sev: "Critical", title: "Hard-coded Password", file: "DatabaseConfig.java:15" },
            { sev: "High", title: "Null Pointer Dereference", file: "StudentService.java:87" },
            { sev: "High", title: "Resource Leak", file: "ReportGenerator.java:134" },
            { sev: "High", title: "Weak Cryptography Algorithm", file: "AuthService.java:67" },
            { sev: "Medium", title: "High Cognitive Complexity", file: "EnrollmentManager.java:201" },
            { sev: "Medium", title: "Duplicate Code", file: "GradeCalculator.java:56" },
            { sev: "Low", title: "Unused Variable", file: "CourseController.java:23" },
          ].map(i => (
            <div
              key={i.title}
              className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer"
              onClick={() => navigate("issues")}
            >
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                i.sev === "Critical" ? "bg-red-100 text-red-700" :
                i.sev === "High" ? "bg-orange-100 text-orange-700" :
                i.sev === "Medium" ? "bg-amber-100 text-amber-700" :
                "bg-sky-100 text-sky-700"
              }`}>{i.sev}</span>
              <div>
                <div className="text-sm font-medium text-gray-900">{i.title}</div>
                <div className="text-xs font-mono text-gray-400">{i.file}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
