import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { SessionLoading } from '../components'
import { useAuth } from '../hooks/useAuth'

export interface RequireGuestProps {
  children: ReactNode
}

/**
 * Guards the public sign-in pages: a visitor that already has a session is
 * sent straight into the workspace.
 */
export function RequireGuest({ children }: RequireGuestProps) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <SessionLoading />
  }

  if (isAuthenticated) {
    return <Navigate to="/app" replace />
  }

  return <>{children}</>
}