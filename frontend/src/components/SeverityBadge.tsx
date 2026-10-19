const colors: Record<string, string> = {
  Critical: "bg-red-100 text-red-700 border border-red-200",
  High: "bg-orange-100 text-orange-700 border border-orange-200",
  Medium: "bg-amber-100 text-amber-700 border border-amber-200",
  Low: "bg-sky-100 text-sky-700 border border-sky-200",
}

export default function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors[severity] ?? "bg-gray-100 text-gray-600"}`}>
      {severity}
    </span>
  )
}
