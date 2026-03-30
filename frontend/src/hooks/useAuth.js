import { useEffect } from 'react'
import { useAuthStore } from '../store/authStore'

export function useAuth() {
  const { user, token, isLoading, error, login, logout, refreshToken, clearError } = useAuthStore()

  // Refresh token every 7 hours (token expires in 8h)
  useEffect(() => {
    if (!token) return
    const interval = setInterval(refreshToken, 7 * 60 * 60 * 1000)
    return () => clearInterval(interval)
  }, [token])

  return { user, token, isLoading, error, login, logout, clearError, isAuthenticated: !!token }
}

export function useRequireAuth() {
  const { token, user } = useAuthStore()
  return { token, user, isAuthenticated: !!token }
}
