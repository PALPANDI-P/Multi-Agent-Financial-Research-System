import { useParams } from 'react-router-dom'
import { Link } from 'react-router-dom'
import { ArrowLeftIcon } from '../components/icons'
import {
  FinancialMetricsPanel,
  RedFlagDashboard,
  ResearchInterface,
  ComparisonInterface,
  ReportGenerator,
  CitationEvidenceViewer,
  ProcessingStatusTracker,
} from '../features/financial'

export function FinancialAnalysisPage() {
  const params = useParams<{ id: string }>()
  const workspaceId = params.id ?? ''

  return (
    <div className="mx-auto flex w-full max-w-page flex-col gap-4 px-5 py-6 sm:px-8 sm:py-8">
      <Link
        to={`/app/workspaces/${workspaceId}`}
        className="inline-flex w-fit items-center gap-1.5 rounded-xs text-small font-medium text-ink-muted transition-colors duration-150 hover:text-ink"
      >
        <ArrowLeftIcon size={15} />
        Back to workspace
      </Link>

      <header>
        <h1 className="text-headline text-ink">Financial analysis</h1>
        <p className="mt-2 text-body text-ink-muted">Workspace {workspaceId}</p>
      </header>

      <ProcessingStatusTracker workspaceId={workspaceId} />
      <FinancialMetricsPanel workspaceId={workspaceId} />
      <RedFlagDashboard workspaceId={workspaceId} />
      <ResearchInterface workspaceId={workspaceId} />
      <ComparisonInterface workspaceId={workspaceId} />
      <ReportGenerator workspaceId={workspaceId} />
      <CitationEvidenceViewer workspaceId={workspaceId} />
    </div>
  )
}

