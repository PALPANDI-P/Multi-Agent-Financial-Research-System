import { Link } from 'react-router-dom'
import { Footer, PublicHeader } from '../components'
import {
  CapabilitiesSection,
  HeroSection,
  PipelineSection,
  ScopeSection,
  ScenariosSection,
} from '../features/landing'
import { useAuth } from '../hooks/useAuth'

const STACK = [
  'Frontend: React 19, TypeScript, Vite and Tailwind CSS v4',
  'Backend: FastAPI, SQLAlchemy and Alembic',
  'Storage: PostgreSQL 16 with the pgvector 0.8 extension',
  'Embeddings: a local ONNX model (BAAI/bge-small-en-v1.5, 384 dimensions)',
]

const REPO_LINKS = [
  {
    path: 'README.md',
    description: 'The overview, the setup and the known limitations of the milestone.',
  },
  {
    path: 'docs/architecture.md',
    description: 'How the frontend, the API, the services and the database fit together.',
  },
  {
    path: 'docs/ingestion-pipeline.md',
    description: 'The eight stages of the ingestion pipeline and the chunking strategy.',
  },
  {
    path: 'docs/api-reference.md',
    description: 'Every endpoint, every parameter and a curl example per group.',
  },
  {
    path: 'docs/database-schema.md',
    description: 'The four tables, their indexes and their relations.',
  },
]

const SECTION_LINKS = [
  { href: '#pipeline', label: 'How it works' },
  { href: '#scenarios', label: 'Scenarios' },
  { href: '#scope', label: 'Scope' },
]

/**
 * The public front page of the product.
 *
 * The page describes what the system really does today: the ingestion
 * pipeline, the pgvector index and the source-cited search.  It makes no
 * claim about the agents that do not exist yet.
 */
export function LandingPage() {
  const { isAuthenticated } = useAuth()
  const workspaceHref = isAuthenticated ? '/app' : '/login'

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <a className="skip-link" href="#main">
        Skip to the main content
      </a>

      <PublicHeader
        links={SECTION_LINKS}
        secondaryAction={
          <Link
            to="/login"
            className="inline-flex h-9 items-center rounded-control border border-line-strong bg-surface px-3.5 text-small font-semibold text-ink transition-colors duration-150 hover:bg-surface-muted"
          >
            Sign in
          </Link>
        }
        action={
          isAuthenticated ? (
            <Link
              to="/app"
              className="inline-flex h-9 items-center rounded-control bg-brand-solid px-3.5 text-small font-semibold text-on-accent transition-colors duration-150 hover:bg-brand-solid-hover"
            >
              Workspace
            </Link>
          ) : null
        }
      />

      <main id="main" className="flex-1">
        <HeroSection workspaceHref={workspaceHref} isAuthenticated={isAuthenticated} />
        <PipelineSection />
        <CapabilitiesSection />
        <ScenariosSection />
        <ScopeSection />
      </main>

      <Footer
        links={REPO_LINKS}
        stack={STACK}
        action={
          <Link
            to="/login"
            className="inline-flex h-10 items-center rounded-control bg-brand-solid px-4 text-small font-semibold text-on-accent transition-colors duration-150 hover:bg-brand-solid-hover"
          >
            Sign in
          </Link>
        }
      />
    </div>
  )
}