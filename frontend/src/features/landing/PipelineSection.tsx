import { SectionIntro } from '../../components'

interface PipelineStep {
  id: string
  title: string
  summary: string
  detail: string
}

/**
 * The real ingestion pipeline of the backend, in the order it runs.  Every
 * entry describes what the code in `backend/app/ingestion/` really does.
 */
const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: 'upload',
    title: 'Upload',
    summary: 'A PDF is uploaded into a workspace.',
    detail:
      'The bytes are written to the storage and the SHA-256 of the file is recorded. Uploading the same bytes twice returns the existing document instead of a second copy.',
  },
  {
    id: 'validate',
    title: 'Validate',
    summary: 'The stored bytes are read back and re-validated.',
    detail:
      'The content of the file decides whether it is a PDF at all; the announced MIME type only corroborates it. The file must not be encrypted and must stay inside the page and size limits. The recorded content hash is compared with the stored bytes.',
  },
  {
    id: 'extracting',
    title: 'Extract',
    summary: 'Text, tables, headings and page numbers are read from the PDF.',
    detail:
      'The text layer is read with PyMuPDF, the headings are detected typographically and merged with the bookmarks of the document, the tables are read with pdfplumber, and every page keeps its number.',
  },
  {
    id: 'chunking',
    title: 'Chunk',
    summary: 'The document is split into page- and section-aware chunks.',
    detail:
      'A chunk never spans two pages and never mixes two sections. Every table becomes exactly one chunk that carries its header row, all of its rows, the caption and the units — the cell values stay verbatim.',
  },
  {
    id: 'embedding',
    title: 'Embed',
    summary: 'Every chunk is turned into a vector.',
    detail:
      'A local ONNX model (BAAI/bge-small-en-v1.5, 384 dimensions) runs inside the API process. The vectors are validated — count, dimension, finiteness, non degeneracy — and a transient provider failure is retried.',
  },
  {
    id: 'indexing',
    title: 'Index in pgvector',
    summary: 'The vectors are written into PostgreSQL with pgvector.',
    detail:
      'The chunks are written with an idempotent upsert into a vector(384) column that carries an HNSW index. The workspace of a document is part of the query, not a post filter.',
  },
  {
    id: 'search',
    title: 'Search with citations',
    summary: 'A question is matched against the chunks of one workspace.',
    detail:
      'Every hit carries the document, the company, the document type, the fiscal period, the page range, the section heading and the chunk type — the evidence a later agent will reason over.',
  },
]

function stepNumber(index: number): string {
  return String(index + 1).padStart(2, '0')
}

export function PipelineSection() {
  return (
    <section id="pipeline" className="border-b border-line bg-canvas scroll-mt-20">
      <div className="mx-auto w-full max-w-page px-5 py-20 sm:px-8 sm:py-28">
        <SectionIntro
          eyebrow="How it works"
          title="The ingestion pipeline"
          lead={
            <>
              This is the path a document takes through the backend, in the order it takes it. The
              state of the document is reported after every stage, so the workspace always shows
              where the processing stands.
            </>
          }
        />

        {/* The strip: the seven stages at a glance. */}
        <ol className="mt-16 grid grid-cols-2 gap-x-6 gap-y-8 overflow-hidden sm:grid-cols-4 lg:grid-cols-7">
          {PIPELINE_STEPS.map((step, index) => (
            <li key={step.id} className="relative">
              {index < PIPELINE_STEPS.length - 1 ? (
                <span
                  aria-hidden="true"
                  className="absolute top-[3px] right-[-1.5rem] left-2 h-px bg-line-strong/70"
                />
              ) : null}
              <span
                aria-hidden="true"
                className="relative block h-1.5 w-1.5 rounded-pill bg-brand-500"
              />
              <p className="mt-4 font-mono text-micro text-ink-subtle tabular-nums">
                {stepNumber(index)}
              </p>
              <p className="mt-1 text-small font-semibold text-ink">{step.title}</p>
            </li>
          ))}
        </ol>

        {/* The detail of every stage, as a reading list rather than a wall of
            boxes: the stage keeps its number and title on the left, the
            explanation is set to a reading measure on the right. */}
        <ol className="mt-16 border-t border-line">
          {PIPELINE_STEPS.map((step, index) => (
            <li
              key={step.id}
              className="grid gap-x-12 gap-y-3 border-b border-line py-7 transition-colors duration-200 hover:bg-surface-muted/40 lg:grid-cols-[17rem_minmax(0,1fr)] lg:py-9"
            >
              <div className="flex items-baseline gap-3.5">
                <span className="font-mono text-micro text-brand-700 tabular-nums">
                  {stepNumber(index)}
                </span>
                <h3 className="text-subtitle text-ink">{step.title}</h3>
              </div>
              <div className="max-w-prose">
                <p className="text-small font-medium text-ink">{step.summary}</p>
                <p className="mt-2.5 text-small leading-relaxed text-ink-muted">{step.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}