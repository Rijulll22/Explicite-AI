import { useNav } from "../App"

export default function SuggestedFix() {
  const { navigate } = useNav()
  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-xs text-gray-400 mb-4">
        <button onClick={() => navigate("issues")} className="hover:text-blue-600 text-gray-500">Issues</button>
        <span>›</span>
        <button onClick={() => navigate("issue-detail")} className="hover:text-blue-600 text-gray-500">SQL Injection</button>
        <span>›</span>
        <span className="text-gray-900">Suggested Fix</span>
      </div>

      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Suggested Fix — SQL Injection</h2>
          <p className="text-sm text-gray-500">StudentDAO.java · Line 42 · java:S3649</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => navigate("ai-assistant")} className="px-3 py-1.5 border border-gray-300 rounded text-sm hover:bg-gray-50">Ask AI</button>
          <button className="px-3 py-1.5 border border-red-300 rounded text-sm text-red-600 hover:bg-red-50">Reject Suggestion</button>
          <button onClick={() => navigate("code-analysis")} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium">Apply Fix</button>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">AI Explanation</h3>
          <span className="text-xs bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded font-medium">AI-generated</span>
        </div>
        <p className="text-sm text-gray-700 leading-relaxed">
          The suggested fix replaces string concatenation with a{" "}
          <code className="font-mono text-xs bg-gray-100 px-1 rounded">PreparedStatement</code>. The SQL structure is
          defined first using a placeholder (<code className="font-mono text-xs bg-gray-100 px-1 rounded">?</code>), and the
          value is bound separately via{" "}
          <code className="font-mono text-xs bg-gray-100 px-1 rounded">setString()</code>. This prevents the database engine
          from interpreting the bound value as SQL syntax, eliminating the injection risk entirely.
        </p>
        <p className="text-xs text-gray-400 mt-2">
          AI-generated suggestion · Review before applying · This prototype does not modify real source files
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        {[
          {
            label: "Original Code",
            accent: "red",
            lines: [
              { text: "public Student getStudentById(", mark: false },
              { text: "    String studentId) {", mark: false },
              { text: `    String query = "SELECT * FROM students "`, mark: true },
              { text: `                   + "WHERE id = '"`, mark: true },
              { text: "                   + studentId + \"'\";", mark: true },
              { text: "", mark: false },
              { text: "    Statement stmt = conn.createStatement();", mark: false },
              { text: "    ResultSet rs = stmt.executeQuery(query);", mark: false },
              { text: "    return mapToStudent(rs);", mark: false },
              { text: "}", mark: false },
            ],
          },
          {
            label: "Suggested Code",
            accent: "green",
            lines: [
              { text: "public Student getStudentById(", mark: false },
              { text: "    String studentId) {", mark: false },
              { text: `    String query = "SELECT * FROM students "`, mark: true },
              { text: `                   + "WHERE id = ?";`, mark: true },
              { text: "", mark: false },
              { text: "    PreparedStatement pstmt =", mark: true },
              { text: "        conn.prepareStatement(query);", mark: true },
              { text: "    pstmt.setString(1, studentId);", mark: true },
              { text: "    ResultSet rs = pstmt.executeQuery();", mark: false },
              { text: "    return mapToStudent(rs);", mark: false },
              { text: "}", mark: false },
            ],
          },
        ].map(col => (
          <div key={col.label} className="bg-white border border-gray-200 rounded overflow-hidden">
            <div className={`px-3 py-2 border-b border-gray-200 flex items-center gap-2 ${col.accent === "red" ? "bg-red-50" : "bg-green-50"}`}>
              <span className={`w-2 h-2 rounded-full ${col.accent === "red" ? "bg-red-500" : "bg-green-500"}`} />
              <span className={`text-xs font-semibold ${col.accent === "red" ? "text-red-700" : "text-green-700"}`}>
                {col.label}
              </span>
            </div>
            <pre className="bg-[#1e2329] text-[#abb2bf] text-xs font-mono p-4 overflow-x-auto leading-relaxed">
              <code>
                {col.lines.map((line, i) =>
                  line.mark ? (
                    <span
                      key={i}
                      className={`block ${col.accent === "red" ? "bg-red-900/40 text-red-300" : "bg-green-900/40 text-green-300"}`}
                    >
                      {line.text + "\n"}
                    </span>
                  ) : (
                    <span key={i} className="block">{line.text + "\n"}</span>
                  )
                )}
              </code>
            </pre>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded p-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Why This Approach Helps</h3>
          <ul className="space-y-2 text-sm text-gray-700">
            {[
              "PreparedStatements separate SQL structure from data values",
              "The JDBC driver handles all escaping automatically",
              "Injected SQL syntax is treated as a literal string, not SQL",
              "Aligns with OWASP secure-by-default coding recommendations",
              "No change to business logic — behaviour is preserved",
            ].map(p => (
              <li key={p} className="flex items-start gap-2">
                <span className="text-green-500 mt-0.5 shrink-0 font-bold">✓</span>
                {p}
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white border border-gray-200 rounded p-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Next Steps</h3>
          <ol className="space-y-2 text-sm text-gray-700 list-decimal list-inside">
            <li>Review the suggested change above carefully</li>
            <li>Apply the fix to your local source code</li>
            <li>Run the unit test suite to verify behaviour is preserved</li>
            <li>Re-run code analysis to confirm the issue is resolved</li>
            <li>Check for similar concatenation patterns in other DAO classes</li>
          </ol>
          <button
            onClick={() => navigate("code-analysis")}
            className="mt-4 text-xs text-blue-600 hover:underline"
          >
            Run Code Analysis →
          </button>
        </div>
      </div>
    </div>
  )
}
