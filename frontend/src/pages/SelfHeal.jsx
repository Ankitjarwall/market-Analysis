import { useEffect, useState } from 'react'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''

const SEV_CONFIG = {
  4: { label: 'CRITICAL', bg: 'bg-red-900/30', border: 'border-red-800/60', badge: 'bg-red-700 text-red-100' },
  3: { label: 'HIGH',     bg: 'bg-orange-900/20', border: 'border-orange-800/50', badge: 'bg-orange-700 text-orange-100' },
  2: { label: 'MEDIUM',   bg: 'bg-yellow-900/10', border: 'border-yellow-800/40', badge: 'bg-yellow-700/70 text-yellow-200' },
  1: { label: 'LOW',      bg: '',                  border: 'border-[#2a2d3a]',     badge: 'bg-gray-700 text-gray-300' },
}

const STATUS_CONFIG = {
  OK:      { dot: 'bg-green-500', text: 'text-green-400', label: 'OK' },
  WARNING: { dot: 'bg-yellow-500', text: 'text-yellow-400', label: 'WARN' },
  ERROR:   { dot: 'bg-red-500', text: 'text-red-400', label: 'ERROR' },
  CRASHED: { dot: 'bg-red-700 animate-pulse', text: 'text-red-500', label: 'DOWN' },
}

const RESTARTABLE = ['scheduler', 'data_feed', 'telegram']

function StatusCard({ svc }) {
  const cfg = STATUS_CONFIG[svc.status] || STATUS_CONFIG.WARNING
  const isRestartable = RESTARTABLE.includes(svc.service?.toLowerCase())

  return (
    <div className={`bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-3 ${svc.status !== 'OK' ? 'border-yellow-800/40' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${cfg.dot}`} />
          <div>
            <div className="text-sm font-medium text-gray-200 capitalize">{svc.service?.replace('_', ' ')}</div>
            {svc.response_time_ms != null && (
              <div className="text-xs text-gray-500">{svc.response_time_ms}ms</div>
            )}
          </div>
        </div>
        <span className={`text-xs font-semibold ${cfg.text}`}>{cfg.label}</span>
      </div>
      {svc.details?.error && (
        <div className="mt-2 text-xs text-red-400 bg-red-900/20 rounded px-2 py-1">{svc.details.error}</div>
      )}
      {isRestartable && (
        <RestartButton service={svc.service?.toLowerCase()} />
      )}
    </div>
  )
}

function RestartButton({ service }) {
  const [state, setState] = useState('idle') // idle | loading | done | error

  const restart = async () => {
    setState('loading')
    try {
      await axios.post(`${API}/api/heal/restart/${service}`)
      setState('done')
      setTimeout(() => setState('idle'), 3000)
    } catch {
      setState('error')
      setTimeout(() => setState('idle'), 3000)
    }
  }

  return (
    <button
      onClick={restart}
      disabled={state === 'loading'}
      className={`mt-2 w-full text-xs py-1.5 rounded border transition-colors
        ${state === 'done' ? 'border-green-800/60 text-green-400 bg-green-900/20' :
          state === 'error' ? 'border-red-800/60 text-red-400' :
          'border-[#2a2d3a] text-gray-500 hover:text-yellow-400 hover:border-yellow-800/50'}`}
    >
      {state === 'loading' ? '⟳ Restarting...' : state === 'done' ? '✓ Restart queued' : state === 'error' ? '✗ Failed' : '⟳ Restart'}
    </button>
  )
}

function ErrorCard({ err, onAction }) {
  const sev = SEV_CONFIG[err.severity] || SEV_CONFIG[1]
  const [expanded, setExpanded] = useState(false)
  const [acting, setActing] = useState(null)

  const act = async (action) => {
    setActing(action)
    try {
      await axios.post(`${API}/api/heal/${action}/${err.id}`)
      onAction()
    } catch (e) {
      alert(e.response?.data?.detail || `Failed to ${action}`)
    } finally {
      setActing(null)
    }
  }

  return (
    <div className={`rounded-xl border p-4 ${sev.bg} ${sev.border}`}>
      <div className="flex items-start gap-3">
        {/* Severity badge */}
        <span className={`shrink-0 mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold ${sev.badge}`}>
          SEV{err.severity}
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-gray-200 capitalize">{err.service?.replace('_', ' ')}</span>
            <span className="text-xs text-gray-500 font-mono">{err.error_type}</span>
            {err.fix_worked !== null && (
              <span className={`text-xs font-semibold ml-auto ${err.fix_worked ? 'text-green-400' : 'text-red-400'}`}>
                {err.fix_worked ? '✓ Fixed' : '✗ Fix failed'}
              </span>
            )}
          </div>

          {err.error_message && (
            <div className="mt-1 text-xs text-gray-400 font-mono bg-[#0f1117] rounded px-2 py-1 truncate">
              {err.error_message}
            </div>
          )}

          {err.fix_explanation && (
            <div className="mt-2">
              <div
                className="flex items-center gap-1.5 cursor-pointer text-xs text-gray-500 hover:text-gray-300"
                onClick={() => setExpanded(e => !e)}
              >
                <span>AI Analysis</span>
                <span>{expanded ? '▲' : '▼'}</span>
              </div>
              {expanded && (
                <div className="mt-1 text-xs text-gray-400 bg-[#0f1117] rounded p-2 leading-relaxed">
                  {err.fix_explanation}
                </div>
              )}
            </div>
          )}

          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="text-xs text-gray-600">
              {new Date(err.timestamp).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
            </span>

            {err.fix_code && !err.fix_approved_by && err.severity < 4 && (
              <div className="flex gap-1.5 shrink-0">
                <button
                  onClick={() => act('approve')}
                  disabled={!!acting}
                  className="px-3 py-1 text-xs rounded-lg bg-green-900/50 hover:bg-green-900/80 text-green-300 border border-green-800/50 transition-colors disabled:opacity-50"
                >
                  {acting === 'approve' ? '...' : '✓ Apply Fix'}
                </button>
                <button
                  onClick={() => act('reject')}
                  disabled={!!acting}
                  className="px-3 py-1 text-xs rounded-lg bg-red-900/30 hover:bg-red-900/60 text-red-400 border border-red-800/40 transition-colors disabled:opacity-50"
                >
                  {acting === 'reject' ? '...' : '✗ Reject'}
                </button>
              </div>
            )}

            {err.fix_approved_by && !err.fix_worked && (
              <span className="text-xs text-yellow-500">Fix deploying...</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function SelfHeal() {
  const [status, setStatus] = useState(null)
  const [errors, setErrors] = useState([])
  const [loading, setLoading] = useState(true)
  const [rolling, setRolling] = useState(false)
  const [rollbackResult, setRollbackResult] = useState(null)
  const [sevFilter, setSevFilter] = useState(0)

  useEffect(() => {
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [])

  const load = async () => {
    try {
      const [s, e] = await Promise.all([
        axios.get(`${API}/api/heal/status`),
        axios.get(`${API}/api/heal/errors?limit=50`),
      ])
      setStatus(s.data)
      setErrors(e.data.errors || [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const rollback = async () => {
    if (!window.confirm('Rollback to last known good commit? This cannot be undone easily.')) return
    setRolling(true)
    try {
      const res = await axios.post(`${API}/api/heal/rollback`)
      setRollbackResult({ success: true, message: res.data.message || 'Rollback initiated' })
    } catch (e) {
      setRollbackResult({ success: false, message: e.response?.data?.detail || 'Rollback failed' })
    } finally {
      setRolling(false)
      setTimeout(() => setRollbackResult(null), 8000)
    }
  }

  const services = status?.services || []
  const pendingFixes = status?.pending_fixes || 0
  const criticalCount = services.filter(s => s.status === 'CRASHED' || s.status === 'ERROR').length
  const filteredErrors = sevFilter > 0 ? errors.filter(e => e.severity === sevFilter) : errors

  return (
    <div className="p-4 lg:p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header + actions */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-200">Self-Heal Monitor</h1>
          <p className="text-xs text-gray-500 mt-0.5">System health, error detection, and automated fixes</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="px-3 py-1.5 text-xs rounded-lg border border-[#2a2d3a] text-gray-400 hover:text-gray-200 transition-colors"
          >
            ⟳ Refresh
          </button>
          <button
            onClick={rollback}
            disabled={rolling}
            className="px-3 py-1.5 text-xs rounded-lg bg-red-900/40 border border-red-800/50 text-red-400 hover:bg-red-900/70 transition-colors disabled:opacity-50"
          >
            {rolling ? 'Rolling back...' : '⏪ Rollback'}
          </button>
        </div>
      </div>

      {/* Rollback result */}
      {rollbackResult && (
        <div className={`rounded-lg px-4 py-2 text-sm ${rollbackResult.success ? 'bg-green-900/30 border border-green-800/50 text-green-300' : 'bg-red-900/30 border border-red-800/50 text-red-300'}`}>
          {rollbackResult.message}
        </div>
      )}

      {/* Alert banner */}
      {pendingFixes > 0 && (
        <div className="bg-yellow-900/20 border border-yellow-800/40 rounded-xl px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-yellow-400 text-lg">⚠</span>
            <div>
              <div className="text-sm font-semibold text-yellow-300">{pendingFixes} pending fix{pendingFixes > 1 ? 'es' : ''} need review</div>
              {criticalCount > 0 && (
                <div className="text-xs text-red-400">{criticalCount} service{criticalCount > 1 ? 's' : ''} critical — manual intervention required</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Service Health Grid */}
      <div>
        <div className="flex items-baseline gap-2 mb-3">
          <h2 className="text-sm font-semibold text-gray-300">Service Health</h2>
          <span className="text-xs text-gray-600">auto-refreshes every 30s</span>
        </div>
        {loading ? (
          <div className="flex items-center justify-center h-24 text-gray-600 text-sm">Loading...</div>
        ) : services.length === 0 ? (
          <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-6 text-center text-gray-600 text-sm">
            No health data yet — watchdog runs every 5 minutes
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {services.map(svc => <StatusCard key={svc.service} svc={svc} />)}
          </div>
        )}
      </div>

      {/* Error Log */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-baseline gap-2">
            <h2 className="text-sm font-semibold text-gray-300">Error Log</h2>
            <span className="text-xs text-gray-600">{errors.length} entries</span>
          </div>
          <div className="flex gap-1">
            {[0, 4, 3, 2, 1].map(s => (
              <button
                key={s}
                onClick={() => setSevFilter(s)}
                className={`px-2 py-0.5 text-xs rounded border transition-colors
                  ${sevFilter === s
                    ? 'border-blue-600 text-blue-300 bg-blue-900/30'
                    : 'border-[#2a2d3a] text-gray-500 hover:text-gray-300'}`}
              >
                {s === 0 ? 'All' : `SEV${s}`}
              </button>
            ))}
          </div>
        </div>

        {filteredErrors.length === 0 ? (
          <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-6 text-center text-gray-600 text-sm">
            {sevFilter > 0 ? `No SEV${sevFilter} errors` : 'No errors recorded'}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredErrors.map(err => (
              <ErrorCard key={err.id} err={err} onAction={load} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
