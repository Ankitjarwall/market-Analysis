import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isLoading: false,
      error: null,

      login: async (email, password) => {
        set({ isLoading: true, error: null })
        try {
          const res = await axios.post(`${API}/auth/login`, { email, password })
          const { access_token } = res.data

          // Fetch user info
          const me = await axios.get(`${API}/auth/me`, {
            headers: { Authorization: `Bearer ${access_token}` }
          })
          set({ token: access_token, user: me.data, isLoading: false })
          return { success: true }
        } catch (err) {
          const msg = err.response?.data?.detail || 'Login failed'
          set({ error: msg, isLoading: false })
          return { success: false, error: msg }
        }
      },

      logout: async () => {
        const { token } = get()
        try {
          if (token) {
            await axios.post(`${API}/auth/logout`, {}, {
              headers: { Authorization: `Bearer ${token}` }
            })
          }
        } catch (_) {}
        set({ user: null, token: null })
      },

      refreshToken: async () => {
        const { token } = get()
        if (!token) return
        try {
          const res = await axios.post(`${API}/auth/refresh`, {}, {
            headers: { Authorization: `Bearer ${token}` }
          })
          set({ token: res.data.access_token })
        } catch (_) {
          set({ user: null, token: null })
        }
      },

      updateUser: (patch) => set((state) => ({ user: { ...state.user, ...patch } })),

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-store',
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
)

// Axios interceptor to attach token
export function setupAxiosAuth() {
  axios.interceptors.request.use((config) => {
    const token = useAuthStore.getState().token
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  })

  axios.interceptors.response.use(
    (r) => r,
    (err) => {
      const status = err.response?.status
      // 401 = token invalid/expired, 403 on /auth/* = token rejected
      if (status === 401 || (status === 403 && err.config?.url?.includes('/auth/'))) {
        useAuthStore.getState().logout()
      }
      return Promise.reject(err)
    }
  )
}
