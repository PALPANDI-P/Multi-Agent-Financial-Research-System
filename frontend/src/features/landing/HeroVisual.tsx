import { Badge } from '../../components'
import { HashIcon, SearchIcon } from '../../components/icons'

/**
 * The product visual of the landing page.
 *
 * It is built from real DOM and CSS - no image, no canvas - and it reproduces
 * the *shape* of the result the search API returns: a document, a page
 * reference, a section heading, a chunk type, a status, a chunk id and a
 * score.  The values are a specimen, not a claim: the caption says so, and
 * the card carries no figure that could be mistaken for a business result.
 */

const STAGES = [
  { id: 'upload', label: 'upload', state: 'done' },
  { id: 'validate', label: 'validate', state: 'done' },
  { id: 'extract', label: 'extract', state: 'done' },
  { id: 'chunk', label: 'chunk', state: 'done' },
  { id: 'embed', label: 'embed', state: 'done' },
  { id: 'index', label: 'index', state: 'active' },
  { id: 'search', label: 'search', state: 'idle' },
] as const

export function HeroVisual() {
  return (
    <div className="relative">
      <div className="relative">
        {/* A single soft plane behind the panel: the only depth cue of the
            hero, tinted by the accent so it also reads in dark mode. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -inset-5 -z-10 rounded-[2.5rem] bg-brand-50 sm:-inset-7"
        />

        <div className="overflow-hidden rounded-panel border border-line bg-surface shadow-panel">
        {/* The window bar: the search field of the workspace. */}
        <div className="flex items-center gap-3 border-b border-line bg-surface-muted/60 px-4 py-3">
          <span
            aria-hidden="true"
            className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-xs bg-brand-solid"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
            >
              <path d="M5 17.5v-5" />
              <path d="M12 17.5v-10" />
              <path d="M19 17.5v-13" />
            </svg>
          </span>
          <div className="flex min-w-0 flex-1 items-center gap-2 rounded-control border border-line bg-surface px-2.5 py-1.5">
            <SearchIcon size={14} className="shrink-0 text-ink-subtle" />
            <span className="truncate font-mono text-caption text-ink">
              segment revenue and operating income
            </span>
            <span className="ml-auto hidden shrink-0 rounded-xs bg-surface-muted px-1.5 py-0.5 font-mono text-micro text-ink-subtle sm:inline">
              ⌘K
            </span>
          </div>
        </div>

        <div className="grid gap-0 sm:grid-cols-[11rem_minmax(0,1fr)]">
          {/* The ingestion rail. */}
          <div className="min-w-0 border-b border-line bg-surface-muted/40 p-4 sm:border-r sm:border-b-0">
            <p className="text-micro font-semibold tracking-[0.12em] text-ink-subtle uppercase">
              Pipeline
            </p>
            <ol className="mt-3.5">
              {STAGES.map((stage, index) => (
                <li key={stage.id} className="relative flex items-center gap-2.5 py-[5px]">
                  {index < STAGES.length - 1 ? (
                    <span
                      aria-hidden="true"
                      className="absolute top-[21px] left-[3.5px] h-[13px] w-px bg-line-strong/50"
                    />
                  ) : null}
                  <span
                    aria-hidden="true"
                    className={
                      stage.state === 'done'
                        ? 'h-2 w-2 shrink-0 rounded-pill bg-brand-500'
                        : stage.state === 'active'
                          ? 'h-2 w-2 shrink-0 rounded-pill bg-brand-600 ring-4 ring-brand-100'
                          : 'h-2 w-2 shrink-0 rounded-pill bg-line-strong'
                    }
                  />
                  <span
                    className={
                      stage.state === 'idle'
                        ? 'font-mono text-micro text-ink-subtle'
                        : stage.state === 'active'
                          ? 'font-mono text-micro font-semibold text-brand-700'
                          : 'font-mono text-micro text-ink-muted'
                    }
                  >
                    {stage.label}
                  </span>
                </li>
              ))}
            </ol>
            <p className="mt-4 border-t border-line-faint pt-3 font-mono text-micro text-ink-subtle">
              384-dim · HNSW
            </p>
          </div>

          {/* The citation card: the shape of one hit. */}
          <div className="min-w-0 p-4 sm:p-5">
            <article className="overflow-hidden rounded-card border border-line bg-surface">
              <header className="flex items-start justify-between gap-3 border-b border-line-faint px-4 py-3.5">
                <div className="flex min-w-0 items-start gap-2.5">
                  <span
                    aria-hidden="true"
                    className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-xs border border-line bg-surface-muted font-mono text-micro text-ink-subtle tabular-nums"
                  >
                    01
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-display text-body font-semibold text-ink">
                      Example 10-K — fiscal year 2026
                    </p>
                    <p className="mt-0.5 truncate font-mono text-micro text-ink-subtle">
                      example industries · 10-K · FY2026
                    </p>
                  </div>
                </div>
                <span className="shrink-0 rounded-xs border border-line px-1.5 py-0.5 font-mono text-micro text-ink-subtle">
                  text
                </span>
              </header>

              <div className="flex items-center gap-2 border-b border-line-faint px-4 py-2.5">
                <span className="shrink-0 rounded-xs bg-brand-50 px-1.5 py-0.5 font-mono text-micro font-semibold text-brand-800">
                  p. 42
                </span>
                <span className="min-w-0 flex-1 truncate text-micro text-ink-muted">
                  Item 7. Management&rsquo;s discussion and analysis
                </span>
              </div>

              <div className="px-4 py-4">
                <p className="font-display text-small leading-relaxed text-ink-muted">
                  The verbatim passage of the matched chunk, anchored to the page it was found on
                  and to the heading of the section it belongs to.
                </p>
              </div>

              <footer className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-line-faint px-4 py-2.5">
                <Badge tone="completed" dot>
                  <span className="font-mono text-micro">completed</span>
                </Badge>
                <span className="ml-auto flex items-baseline gap-1.5">
                  <span className="text-micro tracking-[0.1em] text-ink-subtle uppercase">
                    score
                  </span>
                  <span className="font-mono text-micro font-semibold text-ink tabular-nums">
                    0.8412
                  </span>
                </span>
                <span className="inline-flex min-w-0 items-center gap-1 font-mono text-micro text-ink-subtle">
                  <HashIcon size={11} className="shrink-0" />
                  <span className="truncate">9f31a0c7d24e</span>
                </span>
              </footer>
            </article>
          </div>
        </div>
        </div>
      </div>

      <p className="mt-8 text-center font-mono text-micro text-ink-subtle">
        field layout of one search hit — every value above is returned by the search API
      </p>
    </div>
  )
}