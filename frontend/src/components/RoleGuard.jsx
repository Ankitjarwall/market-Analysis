import { useAuth } from '../hooks/useAuth'

const ROLE_HIERARCHY = { super_admin: 4, admin: 3, analyst: 2, viewer: 1 }

export function RoleGuard({ requiredRole, fallback = null, children }) {
  const { user } = useAuth()
  if (!user) return fallback
  const userLevel = ROLE_HIERARCHY[user.role] || 0
  const requiredLevel = ROLE_HIERARCHY[requiredRole] || 0
  return userLevel >= requiredLevel ? children : fallback
}

export function RequireAnalyst({ children, fallback = null }) {
  return <RoleGuard requiredRole="analyst" fallback={fallback}>{children}</RoleGuard>
}

export function RequireAdmin({ children, fallback = null }) {
  return <RoleGuard requiredRole="admin" fallback={fallback}>{children}</RoleGuard>
}
