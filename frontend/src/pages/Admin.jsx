import { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'

const API = import.meta.env.VITE_API_URL || ''

const ROLES = ['viewer', 'analyst', 'admin', 'super_admin']
const ROLE_CONFIG = {
  super_admin: { bg: 'bg-red-900/50 text-red-300 border-red-800/50', label: 'Super Admin' },
  admin:       { bg: 'bg-yellow-900/50 text-yellow-300 border-yellow-800/50', label: 'Admin' },
  analyst:     { bg: 'bg-blue-900/50 text-blue-300 border-blue-800/50', label: 'Analyst' },
  viewer:      { bg: 'bg-gray-700 text-gray-300 border-gray-600/50', label: 'Viewer' },
}

function RoleBadge({ role }) {
  const cfg = ROLE_CONFIG[role] || ROLE_CONFIG.viewer
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${cfg.bg}`}>
      {cfg.label}
    </span>
  )
}

function UserRow({ u, currentUser, onUpdate, onDelete }) {
  const [editingRole, setEditingRole] = useState(false)
  const [newRole, setNewRole] = useState(u.role)
  const [saving, setSaving] = useState(false)

  const isSelf = u.id === currentUser?.id
  const canEdit = !isSelf && !(currentUser?.role === 'admin' && ['admin', 'super_admin'].includes(u.role))
  const canDelete = currentUser?.role === 'super_admin' && !isSelf

  const saveRole = async () => {
    if (newRole === u.role) { setEditingRole(false); return }
    setSaving(true)
    try {
      await axios.put(`${API}/api/admin/users/${u.id}`, { role: newRole })
      onUpdate()
      setEditingRole(false)
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to update role')
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async () => {
    try {
      await axios.put(`${API}/api/admin/users/${u.id}`, { is_active: !u.is_active })
      onUpdate()
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed')
    }
  }

  const deleteUser = async () => {
    if (!window.confirm(`Delete user ${u.email}? This cannot be undone.`)) return
    try {
      await axios.delete(`${API}/api/admin/users/${u.id}`)
      onUpdate()
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to delete')
    }
  }

  return (
    <div className={`bg-[#1a1d26] border border-[#2a2d3a] rounded-xl p-4 ${!u.is_active ? 'opacity-50' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-gray-200">{u.name}</span>
            {isSelf && <span className="text-xs text-gray-600">(you)</span>}
            <RoleBadge role={u.role} />
            {!u.is_active && (
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-gray-800 text-gray-500 border border-gray-700">Inactive</span>
            )}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">{u.email}</div>
          <div className="text-xs text-gray-600 mt-0.5">
            Capital: ₹{(u.capital || 0).toLocaleString('en-IN')} · Mode: {u.trade_mode || 'auto'}
          </div>
        </div>

        {canEdit && (
          <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
            {/* Role edit */}
            {editingRole ? (
              <div className="flex items-center gap-1">
                <select
                  className="bg-[#0f1117] border border-[#2a2d3a] rounded px-2 py-1 text-xs text-gray-300"
                  value={newRole}
                  onChange={e => setNewRole(e.target.value)}
                >
                  {ROLES.filter(r => {
                    if (currentUser?.role === 'admin') return ['viewer', 'analyst'].includes(r)
                    return r !== 'super_admin' || currentUser?.role === 'super_admin'
                  }).map(r => <option key={r} value={r}>{r}</option>)}
                </select>
                <button onClick={saveRole} disabled={saving} className="px-2 py-1 text-xs bg-green-900/50 text-green-300 border border-green-800/50 rounded hover:bg-green-900/80">
                  {saving ? '...' : '✓'}
                </button>
                <button onClick={() => setEditingRole(false)} className="px-2 py-1 text-xs border border-[#2a2d3a] text-gray-500 rounded hover:text-gray-300">
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => setEditingRole(true)}
                className="px-2 py-1 text-xs border border-[#2a2d3a] text-gray-500 rounded hover:text-gray-300 hover:border-gray-500"
              >
                Edit Role
              </button>
            )}

            <button
              onClick={toggleActive}
              className={`px-2 py-1 text-xs rounded border transition-colors
                ${u.is_active
                  ? 'border-red-800/50 text-red-400 hover:bg-red-900/20'
                  : 'border-green-800/50 text-green-400 hover:bg-green-900/20'}`}
            >
              {u.is_active ? 'Deactivate' : 'Activate'}
            </button>

            {canDelete && (
              <button
                onClick={deleteUser}
                className="px-2 py-1 text-xs border border-red-800/50 text-red-500 rounded hover:bg-red-900/30"
              >
                Delete
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const ACTION_COLOR = {
  USER_CREATED: 'text-green-400',
  USER_UPDATED: 'text-blue-400',
  USER_DELETED: 'text-red-400',
}

export default function Admin() {
  const { user } = useAuth()
  const [users, setUsers] = useState([])
  const [auditLog, setAuditLog] = useState([])
  const [signalRules, setSignalRules] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('users')
  const [showAdd, setShowAdd] = useState(false)
  const [adding, setAdding] = useState(false)
  const [newUser, setNewUser] = useState({ email: '', name: '', password: '', role: 'analyst', capital: 200000 })

  useEffect(() => { loadAll() }, [])

  const loadAll = async () => {
    try {
      const results = await Promise.allSettled([
        axios.get(`${API}/api/admin/users`),
        axios.get(`${API}/api/admin/audit-log?limit=50`),
        axios.get(`${API}/api/admin/signal-rules`),
      ])
      if (results[0].status === 'fulfilled') setUsers(results[0].value.data.users || [])
      if (results[1].status === 'fulfilled') setAuditLog(results[1].value.data.logs || [])
      if (results[2].status === 'fulfilled') setSignalRules(results[2].value.data.rules || [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const addUser = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      await axios.post(`${API}/api/admin/users`, newUser)
      setShowAdd(false)
      setNewUser({ email: '', name: '', password: '', role: 'analyst', capital: 200000 })
      loadAll()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to add user')
    } finally {
      setAdding(false)
    }
  }

  const TABS = [
    { id: 'users', label: `Users (${users.length})` },
    { id: 'audit', label: 'Audit Log' },
    { id: 'rules', label: 'Signal Rules' },
  ]

  return (
    <div className="p-4 lg:p-6 space-y-4 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-gray-200">Admin Panel</h1>
        {tab === 'users' && (
          <button
            onClick={() => setShowAdd(!showAdd)}
            className="px-3 py-1.5 text-xs rounded-lg bg-blue-600/20 border border-blue-700/50 text-blue-300 hover:bg-blue-600/40 transition-colors"
          >
            + Add User
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-[#2a2d3a]">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors
              ${tab === t.id
                ? 'border-blue-500 text-blue-300'
                : 'border-transparent text-gray-500 hover:text-gray-300'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32 text-gray-600 text-sm">Loading...</div>
      ) : tab === 'users' ? (
        <div className="space-y-3">
          {/* Add user form */}
          {showAdd && (
            <form onSubmit={addUser} className="bg-[#1a1d26] border border-blue-800/40 rounded-xl p-4 space-y-3">
              <div className="text-sm font-semibold text-gray-300">New User</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Email</label>
                  <input type="email" required
                    className="w-full bg-[#0f1117] border border-[#2a2d3a] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-600"
                    value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Name</label>
                  <input type="text" required
                    className="w-full bg-[#0f1117] border border-[#2a2d3a] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-600"
                    value={newUser.name} onChange={e => setNewUser({ ...newUser, name: e.target.value })} />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Password</label>
                  <input type="password" required minLength={8}
                    className="w-full bg-[#0f1117] border border-[#2a2d3a] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-600"
                    value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Role</label>
                  <select
                    className="w-full bg-[#0f1117] border border-[#2a2d3a] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-600"
                    value={newUser.role} onChange={e => setNewUser({ ...newUser, role: e.target.value })}>
                    <option value="viewer">viewer</option>
                    <option value="analyst">analyst</option>
                    {user?.role === 'super_admin' && <option value="admin">admin</option>}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Capital (₹)</label>
                  <input type="number" min={10000}
                    className="w-full bg-[#0f1117] border border-[#2a2d3a] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-600"
                    value={newUser.capital} onChange={e => setNewUser({ ...newUser, capital: Number(e.target.value) })} />
                </div>
              </div>
              <div className="flex gap-2">
                <button type="submit" disabled={adding}
                  className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors disabled:opacity-50">
                  {adding ? 'Adding...' : 'Add User'}
                </button>
                <button type="button" onClick={() => setShowAdd(false)}
                  className="px-4 py-2 text-sm border border-[#2a2d3a] text-gray-400 rounded-lg hover:text-gray-200">
                  Cancel
                </button>
              </div>
            </form>
          )}

          {users.map(u => (
            <UserRow key={u.id} u={u} currentUser={user} onUpdate={loadAll} onDelete={loadAll} />
          ))}
        </div>

      ) : tab === 'audit' ? (
        <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl overflow-hidden">
          {auditLog.length === 0 ? (
            <div className="p-6 text-center text-gray-600 text-sm">No audit log entries</div>
          ) : (
            <div className="divide-y divide-[#2a2d3a]/50">
              {auditLog.map((log, i) => (
                <div key={i} className="px-4 py-3 flex items-start justify-between gap-4 hover:bg-[#0f1117]/50">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold ${ACTION_COLOR[log.action] || 'text-gray-400'}`}>
                        {log.action?.replace('_', ' ')}
                      </span>
                      {log.details && Object.keys(log.details).length > 0 && (
                        <span className="text-xs text-gray-500">
                          {Object.entries(log.details).map(([k, v]) => `${k}: ${v}`).join(' · ')}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-600 mt-0.5">
                      {new Date(log.created_at || log.timestamp).toLocaleString('en-IN')}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      ) : tab === 'rules' ? (
        <div className="bg-[#1a1d26] border border-[#2a2d3a] rounded-xl overflow-hidden">
          {signalRules.length === 0 ? (
            <div className="p-6 text-center text-gray-600 text-sm">No signal rules configured</div>
          ) : (
            <div className="divide-y divide-[#2a2d3a]/50">
              {signalRules.map(rule => (
                <div key={rule.id} className="px-4 py-3 flex items-center justify-between hover:bg-[#0f1117]/50">
                  <div>
                    <div className="text-sm font-mono text-gray-300">{rule.rule_name}</div>
                    {rule.change_reason && (
                      <div className="text-xs text-gray-600 mt-0.5">{rule.change_reason}</div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-mono text-blue-400">
                      {JSON.stringify(rule.rule_value?.value ?? rule.rule_value)}
                    </div>
                    {rule.updated_at && (
                      <div className="text-xs text-gray-600">
                        {new Date(rule.updated_at).toLocaleDateString('en-IN')}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
