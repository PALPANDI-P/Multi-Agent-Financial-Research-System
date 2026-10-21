import { Link, Outlet } from 'react-router-dom'

/**
 * Application shell. It lives inside the router tree so that `Link` and
 * `Outlet` always have access to the router context.
 */
export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link
            to="/"
            className="rounded text-base font-semibold tracking-tight text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
          >
            Research Workspace
          </Link>
          <p className="hidden text-xs text-ink-subtle sm:block">`n            Multi-Agent Financial Research System`n          </p>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-line bg-surface">
        <div className="mx-auto w-full max-w-7xl px-4 py-4 text-xs text-ink-subtle sm:px-6">
          All workspace, document and search data is loaded from the configured API.
        </div>
      </footer>
    </div>
  )
}