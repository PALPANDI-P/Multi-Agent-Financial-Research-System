import { SectionIntro } from '../../components'
import { CheckIcon, ClockIcon } from '../../components/icons'

const AVAILABLE_TODAY = [
  'Upload a PDF into a workspace and validate the file.',
  'Extract the text layer, the tables, the headings and the page numbers.',
  'Chunk the document by page and by section, keeping the tables intact.',
  'Embed every chunk with a local model and index it in pgvector.',
  'Search the chunks of a workspace and read the citation of every hit.',
  'Follow the processing state of every document and retry the failed ones.',
  'Extraction agent — pulls structured metrics out of a document.',
  'Red Flag agent — finds accounting and disclosure anomalies.',
  'Comparison agent — compares companies, periods and documents.',
  'Research agent — reasons over the retrieved evidence.',
  'Report agent — writes a PDF research report.',
]

const NOT_YET_AVAILABLE: string[] = []

export function ScopeSection() {
  return (
    <section id="scope" className="border-b border-line bg-surface-sunken scroll-mt-20">
      <div className="mx-auto w-full max-w-page px-5 py-12 sm:px-8 sm:py-16">
        <SectionIntro
          eyebrow="Current scope"
          title="What exists, and what does not"
          lead={
            <>
              The retrieval and evidence foundation and all six agents are wired and tested.
              It is worth being precise about the boundary: the agents run with known
              limitations (see below).
            </>
          }
        />

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <article className="flex h-full flex-col gap-5 rounded-card border border-line bg-surface p-6 shadow-card sm:p-8">
            <div className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className="inline-flex h-8 w-8 items-center justify-center rounded-control bg-success-50 text-success-700"
              >
                <CheckIcon size={16} />
              </span>
              <h3 className="text-subtitle text-ink">Available today</h3>
            </div>
            <ul className="flex flex-col">
              {AVAILABLE_TODAY.map((entry) => (
                <li
                  key={entry}
                  className="flex gap-3 border-t border-line-faint py-3.5 text-small leading-relaxed text-ink-muted first:border-t-0 first:pt-0 last:pb-0"
                >
                  <span
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-pill bg-success-600"
                    aria-hidden="true"
                  />
                  <span className="measure">{entry}</span>
                </li>
              ))}
            </ul>
          </article>

          <article className="flex h-full flex-col gap-5 rounded-card border border-line bg-surface p-6 shadow-card sm:p-8">
            <div className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className="inline-flex h-8 w-8 items-center justify-center rounded-control bg-surface-muted text-ink-subtle"
              >
                <ClockIcon size={16} />
              </span>
              <h3 className="text-subtitle text-ink">Known limitations</h3>
            </div>
            <ul className="flex flex-col">
              {NOT_YET_AVAILABLE.map((entry) => (
                <li
                  key={entry}
                  className="flex gap-3 border-t border-line-faint py-3.5 text-small leading-relaxed text-ink-subtle first:border-t-0 first:pt-0 last:pb-0"
                >
                  <span
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-pill bg-line-strong"
                    aria-hidden="true"
                  />
                  <span className="measure">{entry}</span>
                </li>
              ))}
            </ul>
            <p className="mt-auto border-t border-line pt-5 text-small leading-relaxed text-ink-subtle">
              All six agents are wired and tested. Remaining limits (no auth, in-process queue,
              heuristic metadata, PDF only) are documented in the README.
            </p>
          </article>
        </div>
      </div>
    </section>
  )
}