import { BrandMark } from './Brand'

export interface SessionLoadingProps {
  message?: string
}

/**
 * The branded loading state of the protected routes: the session is being
 * checked, so the application does not know yet whether the visitor may see
 * the workspace.
 */
export function SessionLoading({ message = 'Checking your session' }: SessionLoadingProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-screen flex-col items-center justify-center gap-5 bg-canvas px-4 text-center"
    >
      <BrandMark size={44} className="anim-fade" />
      <p className="text-subtitle text-ink">Multi-Agent Financial Research System</p>
      <p className="flex items-center gap-2 text-small text-ink-muted">
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 animate-pulse rounded-pill bg-brand-500"
        />
        {message}
      </p>
    </div>
  )
}