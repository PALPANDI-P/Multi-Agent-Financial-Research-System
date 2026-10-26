import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Brand } from './Brand'
import { cn } from '../lib/cn'

export interface FooterLink {
  /** Repository relative path, e.g. `docs/architecture.md`. */
  path: string
  description: string
}

export interface FooterProps {
  /** The repository relative paths that document the product. */
  links: FooterLink[]
  /** The stack of the product, one line per layer. */
  stack: string[]
  /** Primary call to action of the footer. */
  action?: ReactNode
  className?: string
}

/**
 * The footer of the public pages: the stack the product is built on and the
 * repository relative paths of its documentation.
 */
export function Footer({ links, stack, action, className }: FooterProps) {
  return (
    <footer className={cn('border-t border-line bg-surface', className)}>
      <div className="mx-auto flex w-full max-w-page flex-col gap-10 px-5 py-12 sm:px-8 sm:py-14">
        <div className="flex flex-col gap-10 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-md">
            <Brand />
            <p className="mt-4 text-small text-ink-muted">
              A research workspace for uploading financial documents and retrieving
              source-grounded passages with page-level citations. Every value on this site is read
              from the configured API.
            </p>
            {action ? <div className="mt-5">{action}</div> : null}
          </div>

          <div className="grid gap-10 sm:grid-cols-2">
            <div>
              <h2 className="text-micro font-semibold tracking-[0.12em] text-ink-subtle uppercase">
                Stack
              </h2>
              <ul className="mt-3.5 flex flex-col gap-2 text-small text-ink-muted">
                {stack.map((entry) => (
                  <li key={entry}>{entry}</li>
                ))}
              </ul>
            </div>

            <div>
              <h2 className="text-micro font-semibold tracking-[0.12em] text-ink-subtle uppercase">
                Repository paths
              </h2>
              <ul className="mt-3.5 flex flex-col gap-3 text-small text-ink-muted">
                {links.map((link) => (
                  <li key={link.path}>
                    <code className="rounded-xs bg-surface-muted px-1.5 py-0.5 font-mono text-caption text-ink">
                      {link.path}
                    </code>
                    <span className="mt-1 block text-caption text-ink-subtle">
                      {link.description}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-line pt-6 text-caption text-ink-subtle sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-2xl">
            Milestone 1: the retrieval and evidence foundation. The Extraction, Red Flag,
            Comparison, Research and Report agents are planned for later milestones.
          </p>
          <p className="flex items-center gap-4">
            <Link
              to="/"
              className="rounded-xs font-medium text-ink-muted transition-colors hover:text-ink"
            >
              Home
            </Link>
            <Link
              to="/login"
              className="rounded-xs font-medium text-ink-muted transition-colors hover:text-ink"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </footer>
  )
}