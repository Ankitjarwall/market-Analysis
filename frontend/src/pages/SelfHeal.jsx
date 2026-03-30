import { useEffect, useState } from 'react'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const STATUS_COLOR = {
  OK: 'bg-green-500',
  WARNING: 'bg-yellow-500',
  ERROR: 'bg-red-500',
  CRASHED: 'bg-red-700',
}

export default function SelfHeal() {
  const [status, setStatus] = useState(null)
  const [errors, setErrors] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  const load = async () => {
    try {
      const [s, e] = await Promise.all([
        axios.get(`${API}/api/heal/status`),
        axios.get(`${API}/api/heal/errors?limit=20`),
      ])
      setStatus(s.data)
      setErrors(e.data.errors || [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const approveFix = async (errorId) => {
    try {
      await axios.post(`${API}/api/heal/approve/${errorId}`)
      load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to approve')
    }
  }

  const rejectFix = async (errorId) => {
    try {
      await axios.post(`${API}/api/heal/reject/${errorId}`)
      load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to reject')
    }
  }

  if (loading) return <div className="p-4 text-gray-500">Loading...</div>

  return (
    <div className="p-4 space-y-4 max-w-2xl mx-auto">
      {/* Service health grid */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">System Health</h3>
        {status?.services?.length > 0 ? (
          <div className="grid grid-cols-2 gap-2">
            {status.services.map(svc => (
              <div key={svc.service} className="flex items-center justify-between bg-[#0f1117] rounded-lg px-3 py-2">
                <div>
                  <div className="text-sm font-medium">{svc.service}</div>
                  {svc.response_time_ms && (
                    <div className="text-xs text-gray-500">{svc.response_time_ms}ms</div>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  <div className={`w-2.5 h-2.5 rounded-full ${STATUS_COLOR[svc.status] || 'bg-gray-500'}`} />
                  <span className="text-xs text-gray-400">{svc.status}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-600 text-sm">No health data yet</div>
        )}
        {status?.pending_fixes > 0 && (
          <div className="mt-3 text-sm text-yellow-400">
            ⚠️ {status.pending_fixes} pending fix(es) require attention
          </div>
        )}
      </div>

      {/* Error log */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">Recent Errors</h3>
        {errors.length === 0 ? (
          <div className="text-gray-600 text-sm text-center py-4">No errors recorded</div>
        ) : (
          <div className="space-y-3">
            {errors.map(err => (
              <div key={err.id} className={`rounded-lg border p-3
                ${err.severity >= 4 ? 'border-red-800/60 bg-red-900/20' :
                  err.severity === 3 ? 'border-yellow-800/60 bg-yellow-900/10' :
                  'border-[#2a2d3a]'}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`badge ${err.severity >= 4 ? 'badge-red' : err.severity === 3 ? 'badge-yellow' : 'badge-gray'}`}>
                        SEV {err.severity}
                      </span>
                      <span className="text-sm font-medium">{err.service}</span>
                      <span className="text-xs text-gray-500">{err.error_type}</span>
                    </div>
                    {err.fix_explanation && (
                      <div className="text-xs text-gray-400 mt-1">
                        AI: {err.fix_explanation.slice(0, 120)}...
                      </div>
                    )}
                    <div className="text-xs text-gray-600 mt-1">
                      {new Date(err.timestamp).toLocaleString('en-IN')}
                    </div>
                  </div>
                  {err.fix_code && !err.fix_approved_by && err.severity < 4 && (
                    <div className="flex gap-1 shrink-0">
                      <button
                        onClick={() => approveFix(err.id)}
                        className="text-xs bg-green-900/40 hover:bg-green-900/70 text-green-300 border border-green-800/50 px-2 py-1 rounded transition-colors"
                      >
                        ✓ Allow
                      </button>
                      <button
                        onClick={() => rejectFix(err.id)}
                        className="text-xs bg-red-900/40 hover:bg-red-900/70 text-red-300 border border-red-800/50 px-2 py-1 rounded transition-colors"
                      >
                        ✗ Reject
                      </button>
                    </div>
                  )}
                  {err.fix_worked !== null && (
                    <span className={`text-xs shrink-0 ${err.fix_worked ? 'text-green-400' : 'text-red-400'}`}>
                      {err.fix_worked ? '✓ Fixed' : '✗ Failed'}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
