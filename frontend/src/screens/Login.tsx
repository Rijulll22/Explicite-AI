import { useState } from "react"
import { useNav } from "../App"
import { CodeIcon } from "../components/Icons"
import { apiLogin, ApiError } from "../lib/api"

export default function Login() {
  const { login } = useNav()
  const [email, setEmail] = useState("jane.doe@university.ac.uk")
  const [password, setPassword] = useState("password")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim() || !password) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiLogin(email.trim(), password)
      login(res.access_token, res.user)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "Invalid email or password." : `Error ${err.status}: ${err.message}`)
      } else {
        setError("Could not reach the server. Is the backend running?")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-full bg-gray-50 flex items-center justify-center">
      <div className="w-80">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 bg-blue-600 rounded mb-3">
            <CodeIcon className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-xl font-semibold text-gray-900">CodeReview AI</h1>
          <p className="text-sm text-gray-500 mt-1">AI-Powered Code Review Assistant</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-white border border-gray-200 rounded p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Email address</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
              />
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <label className="block text-xs font-medium text-gray-700">Password</label>
                <button type="button" className="text-xs text-blue-600 hover:underline">Forgot password?</button>
              </div>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
              />
            </div>
            {error && (
              <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </div>
          <p className="text-center text-xs text-gray-500 mt-4">
            {"Don't have an account? "}
            <button type="button" className="text-blue-600 hover:underline">Sign up</button>
          </p>
        </form>
        <p className="text-center text-xs text-gray-400 mt-4">University Software Engineering Project — v1.0</p>
      </div>
    </div>
  )
}
