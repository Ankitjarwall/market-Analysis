import { BrowserRouter, Routes, Route, Navigate, NavLink, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { setupAxiosAuth } from './store/authStore'
import { useMarketStore } from './store/marketStore'
import { useAuth } from './hooks/useAuth'
import { useWebSocket } from './hooks/useWebSocket'
import { syncIST, getNow } from './utils/timeSync'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Options from './pages/Options'
import News from './pages/News'
import SelfHeal from './pages/SelfHeal'
import Admin from './pages/Admin'
import SystemMonitor from './pages/SystemMonitor'

setupAxiosAuth()

function ProtectedRoute({ children, requiredRole }) {
  const { isAuthenticated, user } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />

  const ROLES = { super_admin: 4, admin: 3, analyst: 2, viewer: 1 }
  if (requiredRole && (ROLES[user?.role] || 0) < (ROLES[requiredRole] || 0)) {
    return <Navigate to="/dashboard" replace />
  }
  return children
}

const NAV_ITEMS = [
  { path: '/dashboard', label: '📊 Dashboard', minRole: 'viewer' },
  { path: '/news',      label: '📰 News',       minRole: 'viewer' },
  { path: '/options',   label: '⚡ Options',   minRole: 'analyst' },
  { path: '/self-heal', label: '🔧 Heal',       minRole: 'admin' },
  { path: '/admin',     label: '👥 Admin',      minRole: 'admin' },
  { path: '/monitor',   label: '🖥 Monitor',    minRole: 'admin' },
]

const ROLES_NUM = { super_admin: 4, admin: 3, analyst: 2, viewer: 1 }

// ── IST Clock + Refresh Countdown ─────────────────────────────────────────────
function ISTClock() {
  const [istTime, setIstTime] = useState('')
  const [nextTick, setNextTick] = useState(0)
  const [nextCollect, setNextCollect] = useState(0)

  useEffect(() => {
    syncIST()
    const syncId = setInterval(syncIST, 10 * 60 * 1000)
    return () => clearInterval(syncId)
  }, [])

  useEffect(() => {
    function tick() {
      const now = getNow()
      const ist = new Date(now.getTime() + (now.getTimezoneOffset() * 60000) + 5.5 * 60 * 60 * 1000)
      const hh = String(ist.getHours()).padStart(2, '0')
      const mm = String(ist.getMinutes()).padStart(2, '0')
      const ss = String(ist.getSeconds()).padStart(2, '0')
      setIstTime(`${hh}:${mm}:${ss}`)
      const secs = ist.getSeconds()
      setNextTick(10 - (secs % 10))
      setNextCollect(20 - (secs % 20))
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="px-3 py-2 space-y-1">
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-gray-600">IST</span>
        <span className="text-xs font-mono text-green-400 tracking-wide">{istTime}</span>
      </div>
      <div className="grid grid-cols-2 gap-1 text-[10px]">
        <div className="flex flex-col">
          <span className="text-gray-600">Price tick</span>
          <span className={`font-mono tabular-nums ${nextTick <= 5 ? 'text-yellow-400' : 'text-gray-400'}`}>
            {nextTick}s
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-gray-600">Full collect</span>
          <span className={`font-mono tabular-nums ${nextCollect <= 5 ? 'text-yellow-400' : 'text-gray-400'}`}>
            {nextCollect}s
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Sidebar Layout ─────────────────────────────────────────────────────────────
function Layout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { connected } = useWebSocket()
  const wsError = useMarketStore(s => s.wsError)
  const systemLogs = useMarketStore(s => s.systemLogs)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const errorCount = systemLogs.filter(l =>
    ['ERROR', 'CRITICAL'].includes(l.level) ||
    (l.level === 'WARNING' && !l.message?.includes('Run time of job') && !l.message?.includes('missed by'))
  ).length

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const visibleNav = NAV_ITEMS.filter(item =>
    (ROLES_NUM[user?.role] || 0) >= (ROLES_NUM[item.minRole] || 0)
  )

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed md:relative z-40 w-48 h-full shrink-0
        bg-[#1a1d26] border-r border-[#2a2d3a] flex flex-col
        transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>
        {/* Logo */}
        <div className="px-4 py-4 border-b border-[#2a2d3a] flex items-center justify-between">
          <div>
            <div className="text-green-400 font-bold text-lg">📊 MarketBot</div>
            <div className="text-xs text-gray-500 mt-0.5">{user?.name}</div>
          </div>
          <button
            className="md:hidden text-gray-500 hover:text-white p-1"
            onClick={() => setSidebarOpen(false)}
          >
            ✕
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-1 overflow-y-auto">
          {visibleNav.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors
                ${isActive
                  ? 'bg-green-600/20 text-green-300 border border-green-700/30'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-[#0f1117]'}`
              }
            >
              {item.label}
              {item.path === '/monitor' && errorCount > 0 && (
                <span className="ml-auto text-[10px] bg-red-600 text-white rounded-full px-1.5 min-w-[18px] text-center font-bold">
                  {errorCount > 9 ? '9+' : errorCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* IST Clock + Timers */}
        <div className="border-t border-[#2a2d3a]">
          <ISTClock />
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[#2a2d3a] space-y-1">
          <div className="flex items-center gap-1.5 text-xs">
            {connected ? (
              <>
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
                </span>
                <span className="text-green-400">Live</span>
              </>
            ) : (
              <>
                <span className="h-1.5 w-1.5 rounded-full bg-gray-600" />
                <span className="text-gray-500">Offline</span>
              </>
            )}
          </div>
          <div className="text-xs text-gray-600">{user?.role}</div>
          <button onClick={handleLogout} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Session expired / WS error banner */}
        {wsError && wsError.includes('expired') && (
          <div className="bg-yellow-900/80 border-b border-yellow-700 px-4 py-2 flex items-center justify-between text-sm shrink-0">
            <span className="text-yellow-300">Session expired — please sign in again</span>
            <button
              onClick={() => { logout(); navigate('/login') }}
              className="text-xs bg-yellow-700 hover:bg-yellow-600 text-white px-3 py-1 rounded transition-colors"
            >
              Sign In
            </button>
          </div>
        )}
        {/* Mobile top bar */}
        <div className="md:hidden flex items-center justify-between px-4 py-3 bg-[#1a1d26] border-b border-[#2a2d3a] shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-gray-400 hover:text-white p-1"
            aria-label="Open menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="text-green-400 font-bold text-base">📊 MarketBot</div>
          <div className="flex items-center gap-1.5 text-xs">
            {connected ? (
              <>
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
                </span>
                <span className="text-green-400">Live</span>
              </>
            ) : (
              <span className="text-gray-500">Offline</span>
            )}
          </div>
        </div>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        <Route path="/dashboard" element={
          <ProtectedRoute><Layout><Dashboard /></Layout></ProtectedRoute>
        } />
        <Route path="/news" element={
          <ProtectedRoute><Layout><News /></Layout></ProtectedRoute>
        } />
        <Route path="/options" element={
          <ProtectedRoute requiredRole="analyst"><Layout><Options /></Layout></ProtectedRoute>
        } />
        <Route path="/self-heal" element={
          <ProtectedRoute requiredRole="admin"><Layout><SelfHeal /></Layout></ProtectedRoute>
        } />
        <Route path="/admin" element={
          <ProtectedRoute requiredRole="admin"><Layout><Admin /></Layout></ProtectedRoute>
        } />
        <Route path="/monitor" element={
          <ProtectedRoute requiredRole="admin"><Layout><SystemMonitor /></Layout></ProtectedRoute>
        } />

        {/* Keep /predictions as redirect to /options for any saved links */}
        <Route path="/predictions" element={<Navigate to="/options" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
