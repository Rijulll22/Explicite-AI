interface IconProps { className?: string }

export function DashboardIcon({ className = "w-4 h-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <rect x="1" y="1" width="6" height="6" rx="0.5"/>
      <rect x="9" y="1" width="6" height="6" rx="0.5"/>
      <rect x="1" y="9" width="6" height="6" rx="0.5"/>
      <rect x="9" y="9" width="6" height="6" rx="0.5"/>
    </svg>
  )
}

export function IssuesIcon({ className = "w-4 h-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <path d="M8 1.5L1.5 13.5h13L8 1.5z" strokeLinejoin="round"/>
      <line x1="8" y1="6" x2="8" y2="9"/>
      <circle cx="8" cy="11.5" r="0.6" fill="currentColor" stroke="none"/>
    </svg>
  )
}

export function ChatIcon({ className = "w-4 h-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <path d="M14 1.5H2a.5.5 0 00-.5.5v8a.5.5 0 00.5.5h3v3l3-3h6a.5.5 0 00.5-.5V2a.5.5 0 00-.5-.5z"/>
    </svg>
  )
}

export function CodeIcon({ className = "w-4 h-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <polyline points="5,4 1,8 5,12"/>
      <polyline points="11,4 15,8 11,12"/>
      <line x1="9.5" y1="2.5" x2="6.5" y2="13.5"/>
    </svg>
  )
}

export function FolderIcon({ className = "w-4 h-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <path d="M1 4.5h4l1.5-2h8.5v10H1V4.5z"/>
    </svg>
  )
}

export function BookIcon({ className = "w-4 h-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <path d="M8 2.5C6 2.5 3.5 3 3.5 3v10.5S6 13 8 13s4.5.5 4.5.5V3S10 2.5 8 2.5z"/>
      <line x1="8" y1="2.5" x2="8" y2="13"/>
    </svg>
  )
}

export function SettingsIcon({ className = "w-4 h-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <circle cx="8" cy="8" r="2.5"/>
      <path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3.2 3.2l1.1 1.1M11.7 11.7l1.1 1.1M3.2 12.8l1.1-1.1M11.7 4.3l1.1-1.1"/>
    </svg>
  )
}

export function ChevronRightIcon({ className = "w-3 h-3" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
      <polyline points="5,2 11,8 5,14"/>
    </svg>
  )
}
