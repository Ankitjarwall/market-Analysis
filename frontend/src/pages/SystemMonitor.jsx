import { useEffect, useRef, useState, useCallback } from 'react'
import axios from 'axios'
import { useMarketStore } from '../store/marketStore'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const TABS = [
  { id: 'all',       label: 'All Logs' },
  { id: 'api',       label: 'API Calls' },
  { id: 'scheduler', label: 'Scheduler' },
  { id: 'collector', label: 'Data Feed' },
  { id: 'db',        label: 'Database' },
  { id: 'websocket', label: 'WebSocket' },
  { id: 'error',     label: 'Errors',   showCount: true },
  { id: 'feeds',     label: 'Feed Test' },
]

// Only true errors count — not scheduler "missed" warnings
const isRealError = (l) =>
  ['ERROR', 'CRITICAL'].includes(l.level) ||
  (l.level === 'WARNING' && !l.message?.includes('Run time of job') && !l.message?.includes('missed by'))

const LEVEL_COLOR = {
  DEBUG:   'text-gray-500',
  INFO:    'text-gray-300',
  WARNING: 'text-yellow-400',
  WARN:    'text-yellow-400',
  ERROR:   'text-red-400',
  CRITICAL:'text-red-500',
}

const LEVEL_BG = {
  DEBUG:   '',
  INFO:    '',
  WARNING: 'bg-yellow-900/10',
  WARN:    'bg-yellow-900/10',
  ERROR:   'bg-red-900/20',
  CRITICAL:'bg-red-900/30',
}

const SOURCE_BADGE = {
  api:       'bg-blue-900/50 text-blue-300',
  scheduler: 'bg-purple-900/50 text-purple-300',
  collector: 'bg-cyan-900/50 text-cyan-300',
  db:        'bg-orange-900/50 text-orange-300',
  websocket: 'bg-green-900/50 text-green-300',
  ai:        'bg-pink-900/50 text-pink-300',
  system:    'bg-gray-700 text-gray-300',
}

function toIST(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  // IST = UTC + 5:30
  const ist = new Date(d.getTime() + 5.5 * 60 * 60 * 1000)
  return ist.toISOString().replace('T', ' ').slice(0, 23)
}

function StatusDot({ ok }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${ok ? 'bg-green-400' : 'bg-red-500'}`} />
  )
}

// ── Feed Test Panel ────────────────────────────────────────────────────────────
function FeedTestPanel() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(null)

  const runTest = useCallback(async () => {
    setLoading(true)
    try {
      const [feedRes, statusRes] = await Promise.all([
        axios.get(`${API}/api/system/test-feeds`),
        axios.get(`${API}/api/system/status`),
      ])
      setResults(feedRes.data.results)
      setStatus(statusRes.data.services)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { runTest() }, [runTest])

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-300">Live Data Feed Test</h2>
        <button
          onClick={runTest}
          disabled={loading}
          className="px-3 py-1 text-xs rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white"
        >
          {loading ? 'Testing…' : '⟳ Re-test'}
        </button>
      </div>

      {/* Service status */}
      {status && (
        <div>
          <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Services</div>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
            {Object.entries(status).map(([svc, info]) => (
              <div key={svc} className="bg-[#1a1d26] border border-[#2a2d3a] rounded-lg px-3 py-2">
                <div className="flex items-center gap-1 text-xs font-medium text-gray-300 capitalize">
                  <StatusDot ok={info.ok} />
                  {svc.replace('_', ' ')}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {info.latency_ms != null && `${info.latency_ms}ms`}
                  {info.jobs != null && ` · ${info.jobs} jobs`}
                  {info.connections != null && ` · ${info.connections} conn`}
                  {info.keys != null && ` · ${info.keys} keys`}
                  {info.error && <span className="text-red-400"> {info.error}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* External feeds */}
      {results && (
        <div>
          <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">External Feeds</div>
          <div className="space-y-2">
            {Object.entries(results).map(([feed, info]) => (
              <div key={feed} className={`border rounded-lg px-3 py-2 ${info.ok ? 'border-green-800/50 bg-green-900/5' : 'border-red-800/50 bg-red-900/10'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-medium">
                    <StatusDot ok={info.ok} />
                    <span className="text-gray-200">{feed.replace('_', ' ').toUpperCase()}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    {info.latency_ms != null && <span>{info.latency_ms}ms</span>}
                    {info.http_status != null && <span>HTTP {info.http_status}</span>}
                    {info.shape && <span>{info.shape}</span>}
                  </div>
                </div>
                {info.ok && (
                  <div className="mt-1.5 grid grid-cols-3 lg:grid-cols-5 gap-x-4 gap-y-0.5">
                    {info.prices && Object.entries(info.prices).map(([k, v]) => (
                      <div key={k} className="flex justify-between text-xs">
                        <span className="text-gray-500">{k}</span>
                        <span className="text-green-400 font-mono">{v?.toLocaleString()}</span>
                      </div>
                    ))}
                    {info.pcr != null && <div className="text-xs"><span className="text-gray-500">PCR </span><span className="text-cyan-400 font-mono">{info.pcr}</span></div>}
                    {info.pe != null && <div className="text-xs"><span className="text-gray-500">PE </span><span className="text-cyan-400 font-mono">{info.pe}</span></div>}
                    {info.rows != null && <div className="text-xs text-gray-400">{info.rows} rows</div>}
                    {info.nifty != null && (
                      <>
                        <div className="text-xs"><span className="text-gray-500">NIFTY </span><span className="text-white font-mono">{info.nifty?.toLocaleString()}</span></div>
                        <div className="text-xs"><span className="text-gray-500">S&P </span><span className="text-white font-mono">{info.sp500?.toLocaleString()}</span></div>
                        <div className="text-xs"><span className="text-gray-500">GOLD </span><span className="text-yellow-400 font-mono">{info.gold?.toLocaleString()}</span></div>
                      </>
                    )}
                  </div>
                )}
                {info.error && <div className="mt-1 text-xs text-red-400">{info.error}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Log row ────────────────────────────────────────────────────────────────────
function LogRow({ entry }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = entry.details && Object.keys(entry.details).length > 0

  return (
    <div
      className={`text-xs border-b border-[#1e2130] px-2 py-1 font-mono hover:bg-[#1a1d26]/50 cursor-pointer ${LEVEL_BG[entry.level] || ''}`}
      onClick={() => hasDetails && setExpanded(e => !e)}
    >
      <div className="flex items-start gap-2 min-w-0">
        {/* Timestamp */}
        <span className="text-gray-600 shrink-0 w-[152px]">{toIST(entry.ts)}</span>

        {/* Level */}
        <span className={`shrink-0 w-[52px] font-semibold ${LEVEL_COLOR[entry.level] || 'text-gray-400'}`}>
          {entry.level}
        </span>

        {/* Source badge */}
        <span className={`shrink-0 px-1.5 rounded text-[10px] font-medium ${SOURCE_BADGE[entry.source] || 'bg-gray-700 text-gray-400'}`}>
          {entry.source}
        </span>

        {/* Message */}
        <span className="text-gray-300 break-all min-w-0">{entry.message}</span>

        {hasDetails && (
          <span className="text-gray-600 shrink-0 ml-auto">{expanded ? '▲' : '▼'}</span>
        )}
      </div>

      {expanded && hasDetails && (
        <pre className="mt-1 ml-[220px] text-gray-500 text-[11px] whitespace-pre-wrap bg-[#0f1117] rounded p-1.5">
          {JSON.stringify(entry.details, null, 2)}
        </pre>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function SystemMonitor() {
  const [tab, setTab] = useState('all')
  const [autoScroll, setAutoScroll] = useState(true)
  const [search, setSearch] = useState('')
  const systemLogs = useMarketStore(s => s.systemLogs)
  const clearSystemLogs = useMarketStore(s => s.clearSystemLogs)
  const bottomRef = useRef(null)
  const listRef = useRef(null)

  // Fetch initial log history on mount
  useEffect(() => {
    axios.get(`${API}/api/system/logs?limit=300`)
      .then(r => {
        const store = useMarketStore.getState()
        r.data.logs.forEach(entry => store.addSystemLog(entry))
      })
      .catch(() => {})
  }, [])

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [systemLogs.length, autoScroll])

  const filtered = systemLogs.filter(entry => {
    if (tab === 'error') return isRealError(entry)
    if (tab !== 'all') return entry.source === tab
    return true
  }).filter(entry => {
    if (!search) return true
    return entry.message?.toLowerCase().includes(search.toLowerCase())
  })

  // Display oldest-first (logs are stored newest-first in store)
  const display = [...filtered].reverse()

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-[#1a1d26] border-b border-[#2a2d3a] px-4 py-3 flex items-center gap-3 flex-wrap">
        <h1 className="text-sm font-bold text-gray-200">System Monitor</h1>
        <span className="text-xs text-gray-500">{systemLogs.length} log entries</span>

        {/* Search */}
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Filter logs…"
          className="ml-auto text-xs bg-[#0f1117] border border-[#2a2d3a] rounded px-2 py-1 text-gray-300 placeholder-gray-600 w-48"
        />

        {/* Auto-scroll toggle */}
        <button
          onClick={() => setAutoScroll(a => !a)}
          className={`text-xs px-2 py-1 rounded border ${autoScroll ? 'border-green-700 text-green-400' : 'border-gray-700 text-gray-500'}`}
        >
          {autoScroll ? '⬇ Auto' : '⬇ Manual'}
        </button>

        <button
          onClick={clearSystemLogs}
          className="text-xs px-2 py-1 rounded border border-gray-700 text-gray-500 hover:text-red-400 hover:border-red-700"
        >
          Clear
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 bg-[#13151e] border-b border-[#2a2d3a] px-2 overflow-x-auto">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 transition-colors
              ${tab === t.id
                ? 'border-blue-500 text-blue-300'
                : 'border-transparent text-gray-500 hover:text-gray-300'}`}
          >
            {t.label}
            {t.showCount && (
              <span className={`ml-1 text-xs ${systemLogs.filter(isRealError).length > 0 ? 'text-red-400' : 'text-gray-600'}`}>
                {systemLogs.filter(isRealError).length || ''}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {tab === 'feeds' ? (
        <div className="flex-1 overflow-auto">
          <FeedTestPanel />
        </div>
      ) : (
        <div ref={listRef} className="flex-1 overflow-auto text-xs">
          {display.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-gray-600">
              No log entries {search ? `matching "${search}"` : 'yet'}
            </div>
          ) : (
            <>
              {display.map(entry => <LogRow key={entry.id} entry={entry} />)}
              <div ref={bottomRef} />
            </>
          )}
        </div>
      )}
    </div>
  )
}