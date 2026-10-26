import { createContext } from 'react'
import type { AuthUser, RegisterPayload } from '../api/types'

export interface AuthContextValue {
  /** The profile of the signed-in user, `null` when there is no session. */
  user: AuthUser | null
  isAuthenticated: boolean
  /** True while the session is being checked (`GET /auth/me`). */
  isLoading: boolean
  login: (email: string, password: string) => Promise<AuthUser>
  register: (payload: RegisterPayload) => Promise<AuthUser>
  logout: () => Promise<void>
  refresh: () => Promise<AuthUser | null>
}

/**
 * The context of the session.
 *
 * The provider lives in `AuthProvider.tsx`; this module only holds the
 * contract so that the hook and the provider can share it without a circular
 * import.
 */
export const AuthContext = createContext<AuthContextValue | null>(null)