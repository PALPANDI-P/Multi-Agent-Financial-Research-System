import type { ApiErrorBody, ApiErrorEnvelope } from './types'

/**
 * Base URL for every API call.
 *
 * `VITE_API_BASE_URL` overrides it. The documented default is the absolute
 * backend URL; setting it to `/api/v1` makes the browser talk to the Vite dev
 * proxy instead (see `vite.config.ts`), which avoids CORS in development.
 */
const RAW_BASE_URL = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
).trim()

export const API_BASE_URL: string =
  RAW_BASE_URL.length > 0 ? RAW_BASE_URL.replace(/\/+$/, '') : 'http://localhost:8000/api/v1'

export type QueryValue = string | number | boolean | null | undefined

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Record<string, QueryValue>
  signal?: AbortSignal
  headers?: Record<string, string>
}

export interface UploadOptions {
  onProgress?: (percent: number, loaded: number, total: number) => void
  signal?: AbortSignal
}

/** Typed error carrying the backend's `{ error: { code, message, ... } }` envelope. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: unknown
  readonly requestId: string | undefined

  constructor(params: {
    code: string
    message: string
    status: number
    details?: unknown
    requestId?: string
  }) {
    super(params.message)
    this.name = 'ApiError'
    this.code = params.code
    this.status = params.status
    this.details = params.details
    this.requestId = params.requestId
  }
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const base = API_BASE_URL
  const normalisedPath = path.startsWith('/') ? path : `/${path}`
  // The base may be relative (`/api/v1` -> Vite dev proxy); in that case it is
  // resolved against the origin of the page.  An absolute base ignores it.
  const url = new URL(`${base}${normalisedPath}`, window.location.origin)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') continue
      url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    (error as { name?: string }).name === 'AbortError'
  )
}

function parseErrorBody(status: number, rawBody: string): {
  code: string
  message: string
  details?: unknown
  requestId?: string
} {
  let parsed: unknown
  try {
    parsed = rawBody ? JSON.parse(rawBody) : undefined
  } catch {
    parsed = undefined
  }

  const envelope = parsed as ApiErrorEnvelope | undefined
  const body: ApiErrorBody | undefined = envelope?.error

  if (body && typeof body.message === 'string' && body.message.length > 0) {
    return {
      code: typeof body.code === 'string' && body.code ? body.code : `http_${status}`,
      message: body.message,
      details: body.details,
      requestId: typeof body.request_id === 'string' ? body.request_id : undefined,
    }
  }

  return {
    code: `http_${status}`,
    message:
      rawBody.trim().length > 0
        ? `Request failed with status ${status}.`
        : `Request failed with status ${status}.`,
  }
}

async function readErrorResponse(response: Response): Promise<ApiError> {
  let raw: string
  try {
    raw = await response.text()
  } catch {
    raw = ''
  }
  const parsed = parseErrorBody(response.status, raw)
  return new ApiError({
    code: parsed.code,
    message: parsed.message,
    status: response.status,
    details: parsed.details,
    requestId: parsed.requestId,
  })
}

/**
 * Single typed request helper used by every API module.
 *
 * - Builds the URL from `API_BASE_URL` + path + query string.
 * - Serialises JSON bodies, sets `Accept: application/json`.
 * - Supports cancellation through an `AbortSignal`.
 * - Throws {@link ApiError} for any non-2xx response, parsed from the backend
 *   error envelope.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, signal, headers } = options
  const url = buildUrl(path, query)

  const requestHeaders: Record<string, string> = { Accept: 'application/json', ...headers }
  let payload: BodyInit | undefined

  if (body !== undefined) {
    if (body instanceof FormData) {
      // The browser must set the multipart boundary itself.
      payload = body
    } else {
      requestHeaders['Content-Type'] = 'application/json'
      payload = JSON.stringify(body)
    }
  }

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers: requestHeaders,
      body: payload,
      signal,
    })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ApiError({
      code: 'network_error',
      message:
        error instanceof Error
          ? `Could not reach the API: ${error.message}`
          : 'Could not reach the API.',
      status: 0,
    })
  }

  if (!response.ok) {
    throw await readErrorResponse(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  if (!text) {
    return undefined as T
  }

  try {
    return JSON.parse(text) as T
  } catch {
    throw new ApiError({
      code: 'invalid_response',
      message: 'The API returned a response that could not be parsed as JSON.',
      status: response.status,
    })
  }
}

/**
 * Multipart upload with real progress reporting.
 *
 * `fetch` cannot report upload progress, so this uses `XMLHttpRequest`.
 * The `Content-Type` header is intentionally NOT set: the browser has to
 * generate the multipart boundary itself.
 */
export function uploadFile<T>(
  path: string,
  formData: FormData,
  options: UploadOptions = {},
): Promise<T> {
  const { onProgress, signal } = options
  const url = buildUrl(path)

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url, true)
    xhr.responseType = 'text'
    xhr.setRequestHeader('Accept', 'application/json')

    const abort = () => {
      xhr.abort()
    }

    if (signal) {
      if (signal.aborted) {
        reject(new DOMException('Upload aborted', 'AbortError'))
        return
      }
      signal.addEventListener('abort', abort, { once: true })
    }

    const cleanup = () => {
      signal?.removeEventListener('abort', abort)
    }

    if (onProgress && xhr.upload) {
      xhr.upload.onprogress = (event: ProgressEvent) => {
        if (!event.lengthComputable) return
        const percent = event.total > 0 ? Math.round((event.loaded / event.total) * 100) : 0
        onProgress(Math.min(percent, 100), event.loaded, event.total)
      }
    }

    xhr.onload = () => {
      cleanup()
      const status = xhr.status
      const raw = typeof xhr.response === 'string' ? xhr.response : xhr.responseText ?? ''

      if (status >= 200 && status < 300) {
        if (!raw) {
          resolve(undefined as T)
          return
        }
        try {
          resolve(JSON.parse(raw) as T)
        } catch {
          reject(
            new ApiError({
              code: 'invalid_response',
              message: 'The API returned a response that could not be parsed as JSON.',
              status,
            }),
          )
        }
        return
      }

      const parsed = parseErrorBody(status, raw)
      reject(
        new ApiError({
          code: parsed.code,
          message: parsed.message,
          status,
          details: parsed.details,
          requestId: parsed.requestId,
        }),
      )
    }

    xhr.onerror = () => {
      cleanup()
      reject(
        new ApiError({
          code: 'network_error',
          message: 'Could not reach the API: the upload request failed.',
          status: 0,
        }),
      )
    }

    xhr.onabort = () => {
      cleanup()
      reject(new DOMException('Upload aborted', 'AbortError'))
    }

    xhr.send(formData)
  })
}

/** Normalises any thrown value into a user-facing message plus error code. */
export function describeError(error: unknown): { message: string; code: string } {
  if (error instanceof ApiError) {
    return { message: error.message, code: error.code }
  }
  if (error instanceof Error) {
    return { message: error.message, code: 'unexpected_error' }
  }
  return { message: 'An unexpected error occurred.', code: 'unexpected_error' }
}
