import { useEffect } from 'react'
import axios from 'axios'
import { useAuthStore } from '../store/authStore'

const API = import.meta.env.VITE_API_URL || ''

export function useAuth() {
  const { user, token, isLoading, error, login, logout, refreshToken, clearError } = useAuthStore()

  // On mount: verify the stored token is still valid — silently logs out if expired
  useEffect(() => {
    if (!token) return
    axios.get(`${API}/auth/me`).catch(() => {
      // 401 response triggers the Axios interceptor which calls logout()
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])  // intentionally run once on mount only

  // Refresh token every 23 hours (token expires in 24h)
  useEffect(() => {
    if (!token) return
    const interval = setInterval(refreshToken, 23 * 60 * 60 * 1000)
    return () => clearInterval(interval)
  }, [token, refreshToken])

  return { user, token, isLoading, error, login, logout, clearError, isAuthenticated: !!token }
}

export function useRequireAuth() {
  const { token, user } = useAuthStore()
  return { token, user, isAuthenticated: !!token }
}
