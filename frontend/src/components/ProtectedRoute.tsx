import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { authenticated } = useAuth()

  if (authenticated === null) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <span className="font-mono text-muted text-sm">Loading…</span>
      </div>
    )
  }

  if (!authenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
