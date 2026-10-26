import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { onUnauthorized } from '../api/client'
import {
  fetchMe,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
} from '../api/auth'
import type { AuthUser, RegisterPayload } from '../api/types'
import { AuthContext } from './AuthContext'
import type { AuthContextValue } from './AuthContext'

export interface AuthProviderProps {
  children: ReactNode
}

/**
 * Holds the session of the application.
 *
 * The session token itself lives in the HttpOnly cookie of the backend; the
 * provider only keeps the *profile* of the user in memory.  Nothing
 * sensitive is written to `localStorage` or `sessionStorage`.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  /**
   * Reads the profile of the current session.  A `401` is the expected answer
   * for a visitor without a session, and a network error means the same thing
   * for the interface: there is no usable session.
   */
  const loadProfile = useCallback(async (): Promise<AuthUser | null> => {
    try {
      return await fetchMe()
    } catch {
      return null
    }
  }, [])

  const refresh = useCallback(async (): Promise<AuthUser | null> => {
    const profile = await loadProfile()
    setUser(profile)
    setIsLoading(false)
    return profile
  }, [loadProfile])

  useEffect(() => {
    let active = true
    void loadProfile().then((profile) => {
      if (!active) return
      setUser(profile)
      setIsLoading(false)
    })
    return () => {
      active = false
    }
  }, [loadProfile])

  // A `401` of any other API call means that the session expired: the state
  // is cleared so that the protected routes send the visitor to the sign-in
  // page instead of showing an empty screen.
  useEffect(
    () =>
      onUnauthorized(() => {
        setUser(null)
      }),
    [],
  )

  const login = useCallback(async (email: string, password: string): Promise<AuthUser> => {
    const response = await loginRequest(email, password)
    setUser(response.user)
    return response.user
  }, [])

  const register = useCallback(async (payload: RegisterPayload): Promise<AuthUser> => {
    const created = await registerRequest(payload)
    return created
  }, [])

  const logout = useCallback(async (): Promise<void> => {
    try {
      await logoutRequest()
    } finally {
      setUser(null)
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      register,
      logout,
      refresh,
    }),
    [user, isLoading, login, register, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}