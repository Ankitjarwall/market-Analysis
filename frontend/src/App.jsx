import { BrowserRouter, Routes, Route, Navigate, NavLink, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { setupAxiosAuth, useAuthStore } from './store/authStore'
import { useAuth } from './hooks/useAuth'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Options from './pages/Options'
import Predictions from './pages/Predictions'
import SelfHeal from './pages/SelfHeal'
import Admin from './pages/Admin'

// Setup axios auth interceptor once
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
  { path: '/options', label: '⚡ Options', minRole: 'analyst' },
  { path: '/predictions', label: '🔮 Predictions', minRole: 'analyst' },
  { path: '/self-heal', label: '🔧 Heal', minRole: 'admin' },
  { path: '/admin', label: '👥 Admin', minRole: 'admin' },
]

const ROLES_NUM = { super_admin: 4, admin: 3, analyst: 2, viewer: 1 }

function Layout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const wsConnected = true

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const visibleNav = NAV_ITEMS.filter(item =>
    (ROLES_NUM[user?.role] || 0) >= (ROLES_NUM[item.minRole] || 0)
  )

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-48 shrink-0 bg-[#1a1d26] border-r border-[#2a2d3a] flex flex-col">
        {/* Logo */}
        <div className="px-4 py-4 border-b border-[#2a2d3a]">
          <div className="text-green-400 font-bold text-lg">📊 MarketBot</div>
          <div className="text-xs text-gray-500 mt-0.5">{user?.name}</div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-1">
          {visibleNav.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors
                ${isActive
                  ? 'bg-green-600/20 text-green-300 border border-green-700/30'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-[#0f1117]'}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[#2a2d3a] space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <div className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-gray-600'}`} />
            {wsConnected ? 'Live' : 'Offline'}
          </div>
          <div className="text-xs text-gray-600">{user?.role}</div>
          <button onClick={handleLogout} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
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
          <ProtectedRoute>
            <Layout><Dashboard /></Layout>
          </ProtectedRoute>
        } />
        <Route path="/options" element={
          <ProtectedRoute requiredRole="analyst">
            <Layout><Options /></Layout>
          </ProtectedRoute>
        } />
        <Route path="/predictions" element={
          <ProtectedRoute requiredRole="analyst">
            <Layout><Predictions /></Layout>
          </ProtectedRoute>
        } />
        <Route path="/self-heal" element={
          <ProtectedRoute requiredRole="admin">
            <Layout><SelfHeal /></Layout>
          </ProtectedRoute>
        } />
        <Route path="/admin" element={
          <ProtectedRoute requiredRole="admin">
            <Layout><Admin /></Layout>
          </ProtectedRoute>
        } />

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
