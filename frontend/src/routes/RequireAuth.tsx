import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { SessionLoading } from '../components'
import { useAuth } from '../hooks/useAuth'

export interface RequireAuthProps {
  children: ReactNode
}

/**
 * Guards a route that needs a session.
 *
 * While the session is being checked the branded loading state is shown.
 * Without a session the visitor is sent to the sign-in page, and the path
 * they wanted is remembered in the router state so that the sign-in can
 * return them to it.
 */
export function RequireAuth({ children }: RequireAuthProps) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <SessionLoading />
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    )
  }

  return <>{children}</>
}