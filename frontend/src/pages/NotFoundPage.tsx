import { Link } from 'react-router-dom'
import { Brand, PublicHeader } from '../components'
import { ArrowLeftIcon, ArrowRightIcon } from '../components/icons'

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <a className="skip-link" href="#main">
        Skip to the main content
      </a>

      <PublicHeader />

      <main id="main" className="relative flex flex-1 items-center overflow-hidden px-5 py-20 sm:px-8">
        <div aria-hidden="true" className="paper-grid pointer-events-none absolute inset-0" />

        <div className="relative mx-auto w-full max-w-page">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <div className="max-w-2xl">
              <p className="flex items-center gap-2.5 text-micro font-semibold tracking-[0.16em] text-brand-700 uppercase">
                <span aria-hidden="true" className="h-px w-6 bg-brand-300" />
                <span className="font-mono tracking-[0.2em]">404</span>
              </p>
              <h1 className="mt-6 max-w-[18ch] font-display text-display text-balance text-ink">
                This page does not exist.
              </h1>
              <p className="mt-6 max-w-[54ch] text-body leading-relaxed text-ink-muted">
                The page you requested is not part of this application. The product overview
                describes what the system does today; the workspace holds your documents and the
                passages that were indexed from them.
              </p>
              <div className="mt-9 flex flex-wrap gap-3">
                <Link
                  to="/"
                  className="inline-flex h-11 items-center gap-2 rounded-control bg-brand-solid px-5 text-body font-semibold text-on-accent shadow-[0_1px_2px_rgb(0_0_0/0.10)] transition-[background-color,transform] duration-150 ease-out-soft hover:bg-brand-solid-hover active:translate-y-px"
                >
                  <ArrowLeftIcon size={16} />
                  Product overview
                </Link>
                <Link
                  to="/app"
                  className="inline-flex h-11 items-center gap-2 rounded-control border border-line-strong bg-surface px-5 text-body font-semibold text-ink transition-[background-color,transform] duration-150 ease-out-soft hover:bg-surface-muted active:translate-y-px"
                >
                  Open the workspace
                  <ArrowRightIcon size={16} />
                </Link>
              </div>
            </div>

            <p className="hidden max-w-[16rem] text-caption leading-relaxed text-ink-subtle lg:block">
              The routes of the application are <span className="font-mono">/</span>,{' '}
              <span className="font-mono">/login</span>, <span className="font-mono">/register</span>,{' '}
              <span className="font-mono">/app</span> and{' '}
              <span className="font-mono">/app/workspaces/:id</span>.
            </p>
          </div>
        </div>
      </main>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto w-full max-w-page px-5 py-5 sm:px-8">
          <Brand compact />
        </div>
      </footer>
    </div>
  )
}