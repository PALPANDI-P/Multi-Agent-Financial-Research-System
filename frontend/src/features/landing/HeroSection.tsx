import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRightIcon } from '../../components/icons'
import { HeroVisual } from './HeroVisual'

export interface HeroSectionProps {
  /** Where the primary call to action points to when a session exists. */
  workspaceHref: string
  /** True when the visitor already has a session. */
  isAuthenticated?: boolean
}

const FACTS = [
  'pgvector 0.8 · HNSW',
  '384-dim local embeddings',
  'page-level citations',
  '8 explicit pipeline states',
]

/**
 * The opening band of the landing page.
 *
 * The reading order is deliberate: an eyebrow that names the category, the
 * display headline that makes the promise, one restrained lead that explains
 * it, two calls to action and finally the technical facts.  Everything is
 * carried by size, weight and space - the band has a single hairline and no
 * boxes.
 */
export function HeroSection({ workspaceHref, isAuthenticated = false }: HeroSectionProps) {
  return (
    <section className="relative overflow-hidden border-b border-line bg-surface">
      {/* The ruled paper of the band: a texture, not a decoration. */}
      <div aria-hidden="true" className="paper-grid pointer-events-none absolute inset-0 -z-0 opacity-45" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-[26rem] bg-gradient-to-b from-brand-50/70 to-transparent"
      />

      <div className="relative mx-auto grid w-full max-w-page gap-16 px-5 py-16 sm:px-8 sm:py-20 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:items-center lg:gap-16 lg:py-28">
        <div className="anim-rise min-w-0">
          <p className="flex items-center gap-2.5 text-micro font-semibold tracking-[0.16em] text-brand-700 uppercase">
            <span aria-hidden="true" className="h-px w-6 bg-brand-300" />
            Retrieval and evidence foundation
          </p>

          <h1 className="mt-7 max-w-[15ch] font-display text-hero text-balance text-ink">
            Every passage, anchored to a page.
          </h1>

          <p className="mt-7 max-w-[46ch] text-subtitle leading-relaxed font-normal text-ink-muted">
            Upload a filing, let the pipeline extract, chunk and embed it, then retrieve the exact
            passage — with its document, page range and section heading.
          </p>

          <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Link
              to={isAuthenticated ? workspaceHref : '/login'}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-control bg-brand-solid px-5 text-body font-semibold text-on-accent shadow-[0_1px_2px_rgb(0_0_0/0.10)] transition-[background-color,transform] duration-150 ease-out-soft hover:bg-brand-solid-hover active:translate-y-px"
            >
              {isAuthenticated ? 'Open the workspace' : 'Sign in to the workspace'}
              <ArrowRightIcon size={16} />
            </Link>
            <a
              href="#pipeline"
              className="inline-flex h-11 items-center justify-center rounded-control border border-line-strong bg-surface/70 px-5 text-body font-semibold text-ink backdrop-blur-sm transition-[background-color,transform] duration-150 ease-out-soft hover:bg-surface-muted active:translate-y-px"
            >
              See how it works
            </a>
          </div>

          {/* The facts read as a single line of technical provenance, not as
              four competing badges. */}
          <ul className="mt-12 grid grid-cols-1 gap-x-6 gap-y-2 border-t border-line-faint pt-5 sm:grid-cols-2">
            {FACTS.map((fact) => (
              <li key={fact} className="font-mono text-caption text-ink-subtle">
                {fact}
              </li>
            ))}
          </ul>
        </div>

        <div
          className="anim-rise min-w-0"
          style={{ '--rise-delay': '120ms' } as CSSProperties}
        >
          <HeroVisual />
        </div>
      </div>
    </section>
  )
}