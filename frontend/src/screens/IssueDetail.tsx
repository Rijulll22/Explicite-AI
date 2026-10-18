import { useNav } from "../App"
import SeverityBadge from "../components/SeverityBadge"

export default function IssueDetail() {
  const { navigate } = useNav()

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-xs text-gray-400 mb-4">
        <button onClick={() => navigate("issues")} className="hover:text-blue-600 text-gray-500">Issues</button>
        <span>›</span>
        <span className="text-gray-900">SQL Injection — StudentDAO.java:42</span>
      </div>

      <div className="flex items-start justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <SeverityBadge severity="Critical" />
            <span className="text-xs px-2 py-0.5 bg-red-50 border border-red-200 rounded text-red-700 font-medium">High Risk</span>
            <span className="text-xs text-gray-400 font-mono">java:S3649 · CWE-89 · OWASP A03:2021</span>
          </div>
          <h2 className="text-xl font-semibold text-gray-900">SQL Injection</h2>
          <p className="text-sm text-gray-500 font-mono mt-0.5">StudentDAO.java · Line 42 · com.university.sms.dao</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => navigate("ai-assistant")} className="px-3 py-1.5 border border-gray-300 rounded text-sm hover:border-blue-400 hover:text-blue-600">
            AI Assistant
          </button>
          <button onClick={() => navigate("suggested-fix")} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium">
            View Suggested Fix
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Main column — structured flow: Code → Risk → Why → AI → Guidance */}
        <div className="col-span-2 space-y-4">

          {/* 1. Code Context */}
          <div className="bg-white border border-gray-200 rounded overflow-hidden">
            <div className="px-4 py-2.5 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Code Context</h3>
              <span className="font-mono text-xs text-gray-400">StudentDAO.java:38–46</span>
            </div>
            <pre className="bg-[#1e2329] text-[#abb2bf] text-xs font-mono p-4 overflow-x-auto leading-relaxed">
              <code>
                {`38  public Student getStudentById(String studentId) {\n`}
                {`39      // User input directly concatenated into SQL query\n`}
                {`40      String query = "SELECT * FROM students "\n`}
                {`41                   + "WHERE id = '"\n`}
                <span className="bg-red-900/50 text-red-300">{`42                   + studentId + "'";  // ← injection point`}</span>
                {`\n43  \n`}
                {`44      Statement stmt = conn.createStatement();\n`}
                {`45      ResultSet rs = stmt.executeQuery(query);\n`}
                {`46      return mapToStudent(rs);\n`}
                {`47  }`}
              </code>
            </pre>
          </div>

          {/* 2. Risk Analysis — visually distinct, prominent */}
          <div className="bg-white border border-gray-300 rounded overflow-hidden">
            <div className="px-4 py-2.5 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Risk Analysis</h3>
              <span className="text-xs bg-red-50 text-red-600 border border-red-200 px-1.5 py-0.5 rounded font-medium">High Risk</span>
            </div>
            <div className="p-4 grid grid-cols-4 gap-4">
              {[
                { label: "Severity", value: "Critical", color: "text-red-600" },
                { label: "Impact", value: "High", color: "text-red-600" },
                { label: "Likelihood", value: "High", color: "text-red-600" },
                { label: "Overall Risk", value: "High", color: "text-red-600" },
              ].map(r => (
                <div key={r.label} className="text-center">
                  <div className="text-xs text-gray-400 mb-1">{r.label}</div>
                  <div className={`text-base font-bold ${r.color}`}>{r.value}</div>
                </div>
              ))}
            </div>
            <div className="px-4 pb-3 flex items-center gap-4 border-t border-gray-100 pt-3">
              <div className="text-xs text-gray-500">CVSS Score: <span className="font-semibold text-red-600">9.1 / 10</span></div>
              <div className="text-xs text-gray-500">CWE: <span className="font-mono text-gray-700">CWE-89</span></div>
              <div className="text-xs text-gray-500">OWASP: <span className="font-mono text-gray-700">A03:2021</span></div>
            </div>
          </div>

          {/* 3. Why Does It Matter */}
          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Why Does it Matter?</h3>
            <p className="text-sm text-gray-700 leading-relaxed">
              SQL Injection is ranked in the OWASP Top 10 (A03:2021) and is one of the most frequently exploited vulnerability
              classes. In this application, a successful attack could expose the full student database, allow unauthorised
              modification or deletion of records, and potentially provide access to other database tables. For a university
              system holding sensitive student data, this could violate GDPR and institutional data protection obligations.
            </p>
          </div>

          {/* 4. AI Explanation */}
          <div className="bg-white border border-gray-200 rounded p-4">
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">AI Explanation</h3>
              <span className="text-xs bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded font-medium">AI-generated</span>
            </div>
            <p className="text-sm text-gray-700 leading-relaxed mb-2">
              The vulnerability arises because the query is assembled by string concatenation before being sent to the database.
              The database engine has no way to distinguish between the intended SQL structure and injected input — the entire
              string is parsed as SQL.
            </p>
            <p className="text-sm text-gray-700 leading-relaxed">
              For example, if an attacker provides{" "}
              <code className="font-mono text-xs bg-gray-100 px-1 rounded">{"' OR '1'='1"}</code>, the resulting query becomes{" "}
              <code className="font-mono text-xs bg-gray-100 px-1 rounded">
                {"SELECT * FROM students WHERE id = '' OR '1'='1'"}
              </code>
              , returning all student records regardless of the intended filter.
            </p>
            <p className="text-xs text-gray-400 mt-3">AI-generated · Not a substitute for manual review · Verify all AI explanations</p>
          </div>

          {/* 5. Suggested Guidance */}
          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Suggested Guidance</h3>
            <p className="text-sm text-gray-700 leading-relaxed mb-3">
              Consider replacing the{" "}
              <code className="font-mono text-xs bg-gray-100 px-1 rounded">Statement</code> with a{" "}
              <code className="font-mono text-xs bg-gray-100 px-1 rounded">PreparedStatement</code>. Parameterised queries
              separate the SQL structure from the data values, preventing injection. An allow-list check on the format of{" "}
              <code className="font-mono text-xs bg-gray-100 px-1 rounded">studentId</code> (e.g. numeric-only) provides
              an extra layer of defence.
            </p>
            <div className="flex gap-2">
              <button onClick={() => navigate("suggested-fix")} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium">
                View Suggested Fix
              </button>
              <button onClick={() => navigate("ai-assistant")} className="px-3 py-1.5 border border-gray-300 rounded text-sm hover:bg-gray-50">
                Ask AI
              </button>
            </div>
          </div>
        </div>

        {/* Right sidebar — metadata and next steps */}
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Details</h3>
            <div className="space-y-2">
              {[
                ["Type", "Vulnerability"],
                ["Rule", "java:S3649"],
                ["Status", "Open"],
                ["Detected", "15 Sep 2026"],
                ["CWE", "CWE-89"],
                ["OWASP", "A03:2021"],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between gap-2">
                  <span className="text-xs text-gray-500 shrink-0">{label}</span>
                  <span className="text-xs text-gray-900 font-mono">{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded p-3">
            <h3 className="text-xs font-semibold text-blue-700 mb-2">Next Steps</h3>
            <div className="space-y-1.5">
              {["Review the code context", "Assess the risk analysis", "Read the AI explanation", "Apply the suggested fix", "Verify with Code Analysis"].map((step, i) => (
                <div key={step} className="flex items-center gap-2 text-xs text-blue-700">
                  <span className="w-4 h-4 rounded-full bg-blue-200 flex items-center justify-center text-[10px] font-bold shrink-0">
                    {i + 1}
                  </span>
                  {step}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
