import { useNav } from "../App"
import { CodeIcon } from "../components/Icons"

export default function Login() {
  const { navigate } = useNav()
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
        <div className="bg-white border border-gray-200 rounded p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Email address</label>
              <input
                type="email"
                defaultValue="jane.doe@university.ac.uk"
                className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <label className="block text-xs font-medium text-gray-700">Password</label>
                <button className="text-xs text-blue-600 hover:underline">Forgot password?</button>
              </div>
              <input
                type="password"
                defaultValue="password"
                className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <button
              onClick={() => navigate("dashboard")}
              className="w-full bg-blue-600 text-white py-2 rounded text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              Sign in
            </button>
          </div>
          <p className="text-center text-xs text-gray-500 mt-4">
            {"Don't have an account? "}
            <button className="text-blue-600 hover:underline">Sign up</button>
          </p>
        </div>
        <p className="text-center text-xs text-gray-400 mt-4">University Software Engineering Project — v1.0</p>
      </div>
    </div>
  )
}
