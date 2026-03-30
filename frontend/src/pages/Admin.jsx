import { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function Admin() {
  const { user } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newUser, setNewUser] = useState({ email: '', name: '', password: '', role: 'analyst', capital: 200000 })
  const [adding, setAdding] = useState(false)

  useEffect(() => { loadUsers() }, [])

  const loadUsers = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/users`)
      setUsers(res.data.users || [])
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
      loadUsers()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to add user')
    } finally {
      setAdding(false)
    }
  }

  const toggleActive = async (userId, isActive) => {
    try {
      await axios.put(`${API}/api/admin/users/${userId}`, { is_active: !isActive })
      loadUsers()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update user')
    }
  }

  const ROLE_COLORS = {
    super_admin: 'badge-red',
    admin: 'badge-yellow',
    analyst: 'badge-blue',
    viewer: 'badge-gray',
  }

  if (loading) return <div className="p-4 text-gray-500">Loading...</div>

  return (
    <div className="p-4 space-y-4 max-w-2xl mx-auto">
      {/* Users list */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-400">Users ({users.length})</h3>
          <button onClick={() => setShowAdd(!showAdd)} className="btn-primary text-sm">
            + Add User
          </button>
        </div>

        {/* Add user form */}
        {showAdd && (
          <form onSubmit={addUser} className="bg-[#0f1117] rounded-lg p-4 mb-4 space-y-3">
            <h4 className="text-sm font-semibold">New User</h4>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Email</label>
                <input type="email" className="input text-sm" required
                  value={newUser.email} onChange={e => setNewUser({...newUser, email: e.target.value})} />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Name</label>
                <input type="text" className="input text-sm" required
                  value={newUser.name} onChange={e => setNewUser({...newUser, name: e.target.value})} />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Password</label>
                <input type="password" className="input text-sm" required minLength={8}
                  value={newUser.password} onChange={e => setNewUser({...newUser, password: e.target.value})} />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Role</label>
                <select className="input text-sm" value={newUser.role}
                  onChange={e => setNewUser({...newUser, role: e.target.value})}>
                  <option value="analyst">analyst</option>
                  <option value="viewer">viewer</option>
                  {user?.role === 'super_admin' && <option value="admin">admin</option>}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Capital (₹)</label>
                <input type="number" className="input text-sm"
                  value={newUser.capital} onChange={e => setNewUser({...newUser, capital: Number(e.target.value)})} />
              </div>
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={adding} className="btn-primary text-sm">
                {adding ? 'Adding...' : 'Add User'}
              </button>
              <button type="button" onClick={() => setShowAdd(false)} className="btn-ghost text-sm">
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Users table */}
        <div className="space-y-2">
          {users.map(u => (
            <div key={u.id} className={`flex items-center justify-between py-2 px-3 rounded-lg
              ${!u.is_active ? 'opacity-50' : ''} bg-[#0f1117]`}>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{u.name}</span>
                  <span className={`badge ${ROLE_COLORS[u.role] || 'badge-gray'}`}>{u.role}</span>
                </div>
                <div className="text-xs text-gray-500">{u.email}</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 font-mono">
                  ₹{(u.capital || 0).toLocaleString('en-IN')}
                </span>
                {u.id !== user?.id && (
                  <button
                    onClick={() => toggleActive(u.id, u.is_active)}
                    className={`text-xs px-2 py-1 rounded border transition-colors
                      ${u.is_active
                        ? 'border-red-800/60 text-red-400 hover:bg-red-900/20'
                        : 'border-green-800/60 text-green-400 hover:bg-green-900/20'}`}
                  >
                    {u.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
