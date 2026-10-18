import { useNav } from "../App"

const currentIssueResources = [
  { title: "Understanding SQL Injection", type: "Article", duration: "8 min", desc: "A plain-language explanation of how SQL injection attacks work and why they are dangerous." },
  { title: "Secure Database Queries in Java", type: "Tutorial", duration: "12 min", desc: "How to use PreparedStatements and parameterised queries to prevent injection." },
  { title: "Input Validation Best Practices", type: "Guide", duration: "10 min", desc: "Techniques for validating and sanitising user-supplied data at system boundaries." },
]

const generalResources = [
  { title: "OWASP Top 10: Injection Attacks (A03:2021)", type: "Guide", duration: "15 min", tag: "Security" },
  { title: "Understanding Code Smells", type: "Article", duration: "10 min", tag: "Quality" },
  { title: "Technical Debt Basics", type: "Article", duration: "6 min", tag: "Quality" },
  { title: "Secure Coding Practices in Java", type: "Tutorial", duration: "25 min", tag: "Security" },
]

const paths = [
  { name: "Secure Java Development", modules: 6, progress: 33, desc: "Secure coding patterns for Java applications" },
  { name: "Code Quality Fundamentals", modules: 4, progress: 50, desc: "Understanding and reducing technical debt" },
  { name: "OWASP Security Essentials", modules: 10, progress: 10, desc: "Cover the OWASP Top 10 vulnerability classes" },
]

export default function Learning() {
  const { navigate } = useNav()
  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Learning & Recommendations</h2>
        <p className="text-sm text-gray-500">Resources recommended based on detected issues in Student Management System</p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-5">

          {/* Recommended for current issue — connected to workflow */}
          <div className="bg-white border border-gray-200 rounded overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Recommended for Your Current Issue</h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  SQL Injection · <button onClick={() => navigate("issue-detail")} className="text-blue-600 hover:underline">View issue →</button>
                </p>
              </div>
              <span className="text-xs bg-red-50 text-red-600 border border-red-200 px-1.5 py-0.5 rounded font-medium">Critical</span>
            </div>
            <div className="divide-y divide-gray-100">
              {currentIssueResources.map((r, i) => (
                <div key={r.title} className="flex items-start gap-3 p-4 hover:bg-gray-50 cursor-pointer transition-colors">
                  <div className="w-6 h-6 rounded bg-red-50 flex items-center justify-center text-xs font-bold text-red-600 shrink-0 mt-0.5">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900">{r.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{r.desc}</div>
                    <div className="text-xs text-gray-400 mt-1">{r.type} · {r.duration} read</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* General recommended learning */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">General Recommended Learning</h3>
            <div className="space-y-2">
              {generalResources.map(r => (
                <div key={r.title} className="bg-white border border-gray-200 rounded p-3 flex items-center gap-3 hover:border-blue-300 cursor-pointer transition-colors">
                  <div className={`w-8 h-8 rounded flex items-center justify-center text-xs font-bold shrink-0 ${r.tag === "Security" ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"}`}>
                    {r.type[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900">{r.title}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{r.type} · {r.duration} read</div>
                  </div>
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${r.tag === "Security" ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"}`}>
                    {r.tag}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Learning paths */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Learning Paths</h3>
            <div className="space-y-2">
              {paths.map(p => (
                <div key={p.name} className="bg-white border border-gray-200 rounded p-4 hover:border-blue-300 cursor-pointer transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-sm font-medium text-gray-900">{p.name}</div>
                    <span className="text-xs text-gray-400">{p.modules} modules · {p.progress}% complete</span>
                  </div>
                  <p className="text-xs text-gray-500 mb-2">{p.desc}</p>
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${p.progress}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Learning Progress</h3>
            <div className="space-y-2.5">
              {[
                ["Articles read", "4 / 12"],
                ["Tutorials completed", "1 / 6"],
                ["Paths started", "3"],
                ["Total study time", "1h 23min"],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">{label}</span>
                  <span className="text-xs font-semibold text-gray-900">{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Recently Detected Issues</h3>
            <div className="space-y-2">
              {[
                { title: "SQL Injection", sev: "Critical" },
                { title: "Hard-coded Password", sev: "Critical" },
                { title: "Null Pointer Dereference", sev: "High" },
                { title: "Weak Cryptography", sev: "High" },
              ].map(i => (
                <div key={i.title} className="flex items-center gap-2 text-xs cursor-pointer hover:text-blue-600" onClick={() => navigate("issues")}>
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${i.sev === "Critical" ? "bg-red-500" : "bg-orange-400"}`} />
                  <span className="text-gray-600">{i.title}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Topic Tags</h3>
            <div className="flex flex-wrap gap-1.5">
              {["SQL Injection", "OWASP", "PreparedStatement", "Code Smells", "Technical Debt", "Secure Coding"].map(tag => (
                <span key={tag} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded cursor-pointer hover:bg-blue-50 hover:text-blue-600">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
