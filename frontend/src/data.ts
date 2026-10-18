export interface Issue {
  id: number
  severity: "Critical" | "High" | "Medium" | "Low"
  type: "Vulnerability" | "Bug" | "Code Smell" | "Security Hotspot"
  title: string
  rule: string
  file: string
  line: number
  risk: "High" | "Medium" | "Low"
  status: "Open" | "In Review" | "Resolved"
}

export const issues: Issue[] = [
  { id: 1, severity: "Critical", type: "Vulnerability", title: "SQL Injection", rule: "java:S3649", file: "StudentDAO.java", line: 42, risk: "High", status: "Open" },
  { id: 2, severity: "Critical", type: "Vulnerability", title: "Hard-coded Password", rule: "java:S2068", file: "DatabaseConfig.java", line: 15, risk: "High", status: "Open" },
  { id: 3, severity: "High", type: "Bug", title: "Null Pointer Dereference", rule: "java:S2259", file: "StudentService.java", line: 87, risk: "High", status: "Open" },
  { id: 4, severity: "High", type: "Bug", title: "Resource Leak", rule: "java:S2093", file: "ReportGenerator.java", line: 134, risk: "Medium", status: "In Review" },
  { id: 5, severity: "Medium", type: "Code Smell", title: "High Cognitive Complexity", rule: "java:S3776", file: "EnrollmentManager.java", line: 201, risk: "Low", status: "Open" },
  { id: 6, severity: "Medium", type: "Code Smell", title: "Duplicate Code", rule: "java:S1192", file: "GradeCalculator.java", line: 56, risk: "Low", status: "Open" },
  { id: 7, severity: "Low", type: "Code Smell", title: "Unused Variable", rule: "java:S1481", file: "CourseController.java", line: 23, risk: "Low", status: "Open" },
  { id: 8, severity: "High", type: "Security Hotspot", title: "Weak Cryptography Algorithm", rule: "java:S4426", file: "AuthService.java", line: 67, risk: "High", status: "Open" },
]

export interface Project {
  id: number
  name: string
  status: "Passed" | "Failed"
  bugs: number
  vulnerabilities: number
  codeSmells: number
  coverage: string
  lastAnalysis: string
  branch: string
}

export const projects: Project[] = [
  { id: 1, name: "Student Management System", status: "Failed", bugs: 12, vulnerabilities: 3, codeSmells: 24, coverage: "64%", lastAnalysis: "2 hours ago", branch: "main" },
  { id: 2, name: "Library Catalogue System", status: "Passed", bugs: 4, vulnerabilities: 0, codeSmells: 8, coverage: "78%", lastAnalysis: "1 day ago", branch: "main" },
  { id: 3, name: "Online Exam Portal", status: "Passed", bugs: 7, vulnerabilities: 1, codeSmells: 15, coverage: "71%", lastAnalysis: "3 days ago", branch: "develop" },
  { id: 4, name: "Attendance Tracker", status: "Failed", bugs: 2, vulnerabilities: 2, codeSmells: 6, coverage: "55%", lastAnalysis: "5 days ago", branch: "main" },
]
