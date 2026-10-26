import { request } from './client'
import type {
  AuthScenario,
  AuthScenariosResponse,
  AuthUser,
  LoginResponse,
  RegisterPayload,
  RegisterResponse,
} from './types'

/**
 * Signs a user in.  The backend answers with the session cookie
 * (`frs_session`, HttpOnly, SameSite=Lax) and with the profile of the user.
 */
export function login(email: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
  })
}

/**
 * Creates an account.  The backend answers with `403 registration_disabled`,
 * `409` (the email is already registered) or `422` (the input is invalid).
 */
export function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return request<RegisterResponse>('/auth/register', {
    method: 'POST',
    body: {
      email: payload.email,
      full_name: payload.full_name,
      password: payload.password,
    },
  })
}

/** Ends the session.  The backend answers with `204`. */
export function logout(): Promise<void> {
  return request<void>('/auth/logout', { method: 'POST' })
}

/**
 * Reads the profile of the current session.  A `401` means "no session"; the
 * caller decides what to do with it.
 */
export function fetchMe(signal?: AbortSignal): Promise<AuthUser> {
  return request<AuthUser>('/auth/me', { signal })
}

/**
 * Reads the analyst scenarios of the product.  The endpoint is public: the
 * landing page and the sign-in page show the scenarios to a visitor that is
 * not signed in.
 */
export async function fetchScenarios(signal?: AbortSignal): Promise<AuthScenario[]> {
  const payload = await request<AuthScenariosResponse | AuthScenario[]>('/auth/scenarios', {
    signal,
  })
  return Array.isArray(payload) ? payload : payload.scenarios
}