import type { ReactNode } from 'react'
import { FeatureCard, SectionIntro } from '../../components'
import {
  DatabaseIcon,
  FileTextIcon,
  GridIcon,
  HashIcon,
  QuoteIcon,
  RefreshIcon,
} from '../../components/icons'

interface Capability {
  title: string
  description: string
  icon: ReactNode
}

const CAPABILITIES: Capability[] = [
  {
    title: 'Page-level citations',
    description:
      'Every search hit names the document, the company, the document type, the fiscal period, the page range, the section heading and the chunk type.',
    icon: <QuoteIcon size={18} />,
  },
  {
    title: 'Table-aware chunks',
    description:
      'A table is never shredded. It becomes exactly one chunk that carries its header row, every row, the caption and the units — with the values verbatim.',
    icon: <GridIcon size={18} />,
  },
  {
    title: 'Section headings',
    description:
      'A chunk never mixes two sections and keeps the heading of the section it came from. The headings are detected from the typography of the page and merged with the bookmarks of the PDF.',
    icon: <FileTextIcon size={18} />,
  },
  {
    title: 'Per-document metadata',
    description:
      'Company name, title, document type, fiscal period, source URL and page count are stored per document. A value that cannot be established is left empty rather than guessed.',
    icon: <HashIcon size={18} />,
  },
  {
    title: 'Processing status and retry',
    description:
      'Eight explicit states — queued, validating, extracting, chunking, embedding, indexing, completed and failed — are reported for every document, and a failed document can be retried.',
    icon: <RefreshIcon size={18} />,
  },
  {
    title: 'Workspace-scoped search',
    description:
      'The workspace filter is part of the SQL query, so a search never leaves the workspace of its path. Documents are organised by company, sector or theme.',
    icon: <DatabaseIcon size={18} />,
  },
]

export function CapabilitiesSection() {
  return (
    <section id="capabilities" className="border-b border-line bg-surface scroll-mt-20">
      <div className="mx-auto w-full max-w-page px-5 py-20 sm:px-8 sm:py-28">
        <SectionIntro
          eyebrow="What you get"
          title="Evidence, not answers"
          lead={
            <>
              The product of this milestone is the evidence layer: the passages, their citations and
              the metadata around them. It is what an analyst can check and what a later agent will
              reason over.
            </>
          }
        />

        <div className="mt-16 grid gap-x-10 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map((capability, index) => (
            <FeatureCard
              key={capability.title}
              title={capability.title}
              description={capability.description}
              icon={capability.icon}
              index={String(index + 1).padStart(2, '0')}
            />
          ))}
        </div>
      </div>
    </section>
  )
}