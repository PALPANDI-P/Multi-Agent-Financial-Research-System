import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { describeError } from '../api/client'
import type { DocumentRead } from '../api/types'
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  Pagination,
  Select,
} from '../components'
import { ArrowLeftIcon, FilterIcon, PencilIcon, TrashIcon } from '../components/icons'
import { DocumentList, UploadPanel } from '../features/documents'
import { SearchPanel } from '../features/search'
import { DeleteWorkspaceDialog, WorkspaceDialog } from '../features/workspaces'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useDocuments, useRetryDocument } from '../hooks/useDocuments'
import { useWorkspace } from '../hooks/useWorkspaces'
import { formatDateTime, formatNumber } from '../lib/format'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'queued', label: 'queued' },
  { value: 'validating', label: 'validating' },
  { value: 'extracting', label: 'extracting' },
  { value: 'chunking', label: 'chunking' },
  { value: 'embedding', label: 'embedding' },
  { value: 'indexing', label: 'indexing' },
  { value: 'completed', label: 'completed' },
  { value: 'failed', label: 'failed' },
]

export function WorkspaceDetailPage() {
  const params = useParams<{ id: string }>()
  const workspaceId = params.id ?? ''
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') ?? ''

  const [renameOpen, setRenameOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [companyFilter, setCompanyFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [limit, setLimit] = useState(10)
  const [offset, setOffset] = useState(0)
  const [actionError, setActionError] = useState<{ message: string; code: string } | null>(null)
  const [retryNotice, setRetryNotice] = useState<string | null>(null)
  const [retryingDocumentId, setRetryingDocumentId] = useState<string | null>(null)

  const debouncedCompany = useDebouncedValue(companyFilter, 300)
  const debouncedType = useDebouncedValue(typeFilter, 300)

  const workspaceQuery = useWorkspace(workspaceId)

  const documentParams = useMemo(
    () => ({
      limit,
      offset,
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(debouncedCompany.trim() ? { company_name: debouncedCompany.trim() } : {}),
      ...(debouncedType.trim() ? { document_type: debouncedType.trim() } : {}),
    }),
    [limit, offset, statusFilter, debouncedCompany, debouncedType],
  )

  const documentsQuery = useDocuments(workspaceId, documentParams)
  const retryDocument = useRetryDocument(workspaceId)

  const workspace = workspaceQuery.data
  const documents = documentsQuery.data?.items ?? []
  const documentsTotal = documentsQuery.data?.total ?? 0
  const workspaceError = workspaceQuery.error ? describeError(workspaceQuery.error) : null
  const documentsError = documentsQuery.error ? describeError(documentsQuery.error) : null

  const handleRetry = async (document: DocumentRead) => {
    setActionError(null)
    setRetryNotice(null)
    setRetryingDocumentId(document.id)
    try {
      const response = await retryDocument.mutateAsync(document.id)
      setRetryNotice(
        `Retry accepted for “${document.original_filename}” — status: ${response.processing_status}, attempt ${response.attempt_count}, job ${response.job_id}.`,
      )
    } catch (caught) {
      setActionError(describeError(caught))
    } finally {
      setRetryingDocumentId(null)
    }
  }

  if (workspaceQuery.isPending) {
    return (
      <div className="mx-auto flex w-full max-w-page flex-col gap-4 px-5 py-6 sm:px-8">
        <span className="skeleton h-3 w-32" />
        <span className="skeleton h-8 w-96 max-w-full" />
        <span className="skeleton h-4 w-full max-w-2xl" />
      </div>
    )
  }

  if (workspaceError) {
    return (
      <div className="mx-auto flex w-full max-w-page flex-col gap-4 px-5 py-6 sm:px-8">
        <Alert tone="danger" title="This workspace could not be loaded" code={workspaceError.code}>
          {workspaceError.message}
        </Alert>
        <div>
          <Link to="/app" className="text-small font-medium text-brand-700 hover:text-brand-600">
            Back to all workspaces
          </Link>
        </div>
      </div>
    )
  }

  if (!workspace) {
    return (
      <div className="mx-auto flex w-full max-w-page flex-col gap-4 px-5 py-6 sm:px-8">
        <Alert tone="warning" title="Workspace not found">
          The API did not return a workspace with this identifier.
        </Alert>
        <div>
          <Link to="/app" className="text-small font-medium text-brand-700 hover:text-brand-600">
            Back to all workspaces
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-page flex-col gap-4 px-5 py-6 sm:px-8 sm:py-8">
      <Link
        to="/app"
        className="inline-flex w-fit items-center gap-1.5 rounded-xs text-small font-medium text-ink-muted transition-colors duration-150 hover:text-ink"
      >
        <ArrowLeftIcon size={15} />
        All workspaces
      </Link>

      <header className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between lg:gap-10">
        <div className="min-w-0">
          <p className="flex items-center gap-2.5 text-micro font-semibold tracking-[0.14em] text-brand-700 uppercase">
            <span aria-hidden="true" className="h-px w-6 bg-brand-300" />
            Workspace
          </p>
          <h1 className="mt-3 text-headline text-balance text-ink">{workspace.name}</h1>
          {workspace.description ? (
            <p className="mt-3 max-w-prose text-body text-ink-muted">{workspace.description}</p>
          ) : (
            <p className="mt-3 text-body text-ink-subtle italic">No description</p>
          )}
          <div className="mt-6 border-t border-line pt-4">
            <dl className="flex flex-wrap items-center gap-x-7 gap-y-3 text-caption text-ink-muted">
            <div className="flex items-baseline gap-2">
              <dt className="text-ink-subtle">Documents</dt>
              <dd className="font-mono text-body font-semibold text-ink tabular-nums">
                {formatNumber(workspace.document_count)}
              </dd>
            </div>
            <div className="flex items-baseline gap-2">
              <dt className="text-ink-subtle">Created</dt>
              <dd className="font-mono text-ink">{formatDateTime(workspace.created_at)}</dd>
            </div>
            <div className="flex items-baseline gap-2">
              <dt className="text-ink-subtle">Updated</dt>
              <dd className="font-mono text-ink">{formatDateTime(workspace.updated_at)}</dd>
            </div>
            {workspace.owner_id ? (
              <div className="flex items-baseline gap-2">
                <dt className="text-ink-subtle">Owner</dt>
                <dd className="font-mono text-ink">{workspace.owner_id}</dd>
              </div>
            ) : null}
            </dl>
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <Button
            variant="secondary"
            leadingIcon={<PencilIcon size={15} />}
            onClick={() => setRenameOpen(true)}
          >
            Rename
          </Button>
          <Button
            variant="ghost"
            leadingIcon={<TrashIcon size={15} />}
            onClick={() => setDeleteOpen(true)}
            className="text-danger-700 hover:bg-danger-50 hover:text-danger-700"
          >
            Delete
          </Button>
        </div>
      </header>

      {actionError ? (
        <Alert tone="danger" title="The action failed" code={actionError.code}>
          {actionError.message}
        </Alert>
      ) : null}

      {retryNotice ? (
        <Alert tone="success" title="Retry accepted">
          {retryNotice}
        </Alert>
      ) : null}

      <Card>
        <CardHeader
          title="Search passages"
          description="Semantic search over the chunks indexed for this workspace."
        />
        <CardBody>
          <SearchPanel key={initialQuery} workspaceId={workspace.id} initialQuery={initialQuery} autoSearch />
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Documents"
          description={
            <span className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral">
                {formatNumber(documentsTotal)} in this view
              </Badge>
              <span>Every value below comes from the documents API.</span>
            </span>
          }
        />

        <div className="border-b border-line bg-surface-muted/40 px-5 py-4 sm:px-6">
          <p className="mb-3 flex items-center gap-1.5 text-micro font-semibold tracking-[0.12em] text-ink-subtle uppercase">
            <FilterIcon size={13} />
            Filters
          </p>
          <div className="grid gap-4 sm:grid-cols-3">
            <Select
              label="Processing status"
              id="document-filter-status"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value)
                setOffset(0)
              }}
              options={STATUS_OPTIONS}
            />
            <Input
              label="Company name"
              id="document-filter-company"
              type="search"
              value={companyFilter}
              onChange={(event) => {
                setCompanyFilter(event.target.value)
                setOffset(0)
              }}
              placeholder="Filter by company…"
            />
            <Input
              label="Document type"
              id="document-filter-type"
              type="search"
              value={typeFilter}
              onChange={(event) => {
                setTypeFilter(event.target.value)
                setOffset(0)
              }}
              placeholder="Filter by type…"
            />
          </div>
        </div>

        {documentsError ? (
          <CardBody>
            <Alert
              tone="danger"
              title="The documents could not be loaded"
              code={documentsError.code}
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void documentsQuery.refetch()}
                >
                  Try again
                </Button>
              }
            >
              {documentsError.message}
            </Alert>
          </CardBody>
        ) : null}

        <DocumentList
          documents={documents}
          workspaceId={workspace.id}
          onRetry={handleRetry}
          retryingDocumentId={retryingDocumentId}
          isLoading={documentsQuery.isPending}
        />

        {!documentsError ? (
          <Pagination
            total={documentsTotal}
            limit={limit}
            offset={offset}
            onOffsetChange={setOffset}
            onLimitChange={(nextLimit) => {
              setLimit(nextLimit)
              setOffset(0)
            }}
            itemLabel="documents"
          />
        ) : null}
      </Card>

      <Card>
        <CardHeader
          title="Financial analysis"
          description="Metrics, red flags, research, comparison, reports and citations."
          actions={
            <Link to={`/app/workspaces/${workspace.id}/analysis`}>
              <Button variant="primary" size="sm">Open analysis</Button>
            </Link>
          }
        />
        <CardBody>
          <p className="text-small text-ink-muted">
            Open the dedicated workspace for financial metrics, red-flag dashboards, research, comparison, report generation and citation review.
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Upload a document"
          description="Files are ingested by the API; the processing status shown afterwards is the one returned by the server."
        />
        <CardBody>
          <UploadPanel workspaceId={workspace.id} />
        </CardBody>
      </Card>

      <WorkspaceDialog
        open={renameOpen}
        mode="edit"
        workspace={workspace}
        onClose={() => setRenameOpen(false)}
      />

      <DeleteWorkspaceDialog
        open={deleteOpen}
        workspace={workspace}
        onClose={() => setDeleteOpen(false)}
        onDeleted={() => {
          setDeleteOpen(false)
          navigate('/app', { replace: true })
        }}
      />
    </div>
  )
}
