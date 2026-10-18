import { useState } from "react"

const sections = ["Profile", "Appearance", "Preferences", "Project Defaults", "Analysis Settings", "Developer Settings"]

function Field({ label, value, type = "text" }: { label: string; value: string; type?: string }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-700 mb-1">{label}</label>
      <input
        type={type}
        defaultValue={value}
        className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
      />
    </div>
  )
}

function Select({ label, options, defaultValue }: { label: string; options: string[]; defaultValue?: string }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-700 mb-1">{label}</label>
      <select
        defaultValue={defaultValue}
        className="w-full px-3 py-2 border border-gray-300 rounded text-sm bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
      >
        {options.map(o => <option key={o}>{o}</option>)}
      </select>
    </div>
  )
}

function SaveButton() {
  return (
    <button className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 font-medium">
      Save Changes
    </button>
  )
}

export default function Settings() {
  const [active, setActive] = useState("Profile")

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-44 shrink-0 border-r border-gray-200 bg-white py-3">
        {sections.map(s => (
          <button
            key={s}
            onClick={() => setActive(s)}
            className={`w-full text-left px-4 py-2 text-sm transition-colors ${active === s ? "text-blue-600 font-medium bg-blue-50 border-r-2 border-blue-600" : "text-gray-600 hover:bg-gray-50"}`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">{active}</h2>
        <p className="text-sm text-gray-500 mb-6">
          {active === "Profile" && "Manage your account information."}
          {active === "Appearance" && "Customise the visual appearance of the application."}
          {active === "Preferences" && "Configure notification and workflow preferences."}
          {active === "Project Defaults" && "Set default values applied to new projects."}
          {active === "Analysis Settings" && "Configure code analysis rules and quality gate thresholds."}
          {active === "Developer Settings" && "Advanced settings and API integrations."}
        </p>

        <div className="max-w-md space-y-4">
          {active === "Profile" && (
            <>
              <Field label="Full name" value="Jane Doe" />
              <Field label="Email address" value="jane.doe@university.ac.uk" type="email" />
              <Field label="Role" value="Developer" />
              <Field label="Department" value="Computer Science" />
              <SaveButton />
            </>
          )}

          {active === "Appearance" && (
            <>
              <Select label="Theme" options={["Light (default)", "Dark", "System"]} defaultValue="Light (default)" />
              <Select label="Code font size" options={["12px", "13px", "14px", "16px"]} defaultValue="13px" />
              <Select label="Code colour scheme" options={["Dark (default)", "Light", "High Contrast"]} defaultValue="Dark (default)" />
              <SaveButton />
            </>
          )}

          {active === "Preferences" && (
            <>
              <Select label="Email notifications" options={["All issues", "Critical and High only", "None"]} defaultValue="Critical and High only" />
              <Select label="Default issue sort" options={["Severity (highest first)", "Date detected", "File name"]} defaultValue="Severity (highest first)" />
              <Select label="AI explanation verbosity" options={["Concise", "Detailed", "Technical"]} defaultValue="Detailed" />
              <SaveButton />
            </>
          )}

          {active === "Project Defaults" && (
            <>
              <Select label="Default branch" options={["main", "develop", "master"]} defaultValue="main" />
              <Select label="Auto-run analysis on push" options={["Enabled", "Disabled"]} defaultValue="Enabled" />
              <Field label="Analysis exclusions (glob patterns)" value="**/test/**, **/generated/**" />
              <SaveButton />
            </>
          )}

          {active === "Analysis Settings" && (
            <>
              <Field label="Coverage threshold (%)" value="80" type="number" />
              <Field label="Maximum bugs (Quality Gate)" value="0" type="number" />
              <Field label="Maximum critical vulnerabilities" value="0" type="number" />
              <Field label="Maximum code smells" value="20" type="number" />
              <Field label="Technical debt threshold (hours)" value="24" type="number" />
              <SaveButton />
            </>
          )}

          {active === "Developer Settings" && (
            <>
              <Field label="SonarQube server URL" value="http://localhost:9000" />
              <Field label="Project key" value="com.university:student-management" />
              <Field label="Analysis token" value="••••••••••••••••" type="password" />
              <Select label="Java version" options={["Java 17", "Java 11", "Java 8"]} defaultValue="Java 17" />
              <SaveButton />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
