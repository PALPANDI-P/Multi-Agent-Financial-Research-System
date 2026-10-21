import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
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
  Spinner,
} from '../components'
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
      <div className="mx-auto flex w-full max-w-7xl items-center justify-center px-4 py-20 sm:px-6">
        <Spinner label="Loading workspace" />
      </div>
    )
  }

  if (workspaceError) {
    return (
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-10 sm:px-6">
        <Alert tone="danger" title="This workspace could not be loaded" code={workspaceError.code}>
          {workspaceError.message}
        </Alert>
        <div>
          <Link
            to="/"
            className="text-sm font-medium text-brand-700 underline hover:text-brand-600"
          >
            Back to all workspaces
          </Link>
        </div>
      </div>
    )
  }

  if (!workspace) {
    return (
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-10 sm:px-6">
        <Alert tone="warning" title="Workspace not found">
          The API did not return a workspace with this identifier.
        </Alert>
        <div>
          <Link
            to="/"
            className="text-sm font-medium text-brand-700 underline hover:text-brand-600"
          >
            Back to all workspaces
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <div>
        <Link to="/" className="text-sm font-medium text-brand-700 hover:text-brand-600">
          ← All workspaces
        </Link>
      </div>

      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-ink">{workspace.name}</h1>
          {workspace.description ? (
            <p className="mt-1.5 max-w-3xl text-sm text-ink-muted">{workspace.description}</p>
          ) : (
            <p className="mt-1.5 text-sm italic text-ink-subtle">No description</p>
          )}
          <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ink-muted">
            <div className="flex items-center gap-1.5">
              <dt>Documents:</dt>
              <dd className="font-semibold text-ink">{formatNumber(workspace.document_count)}</dd>
            </div>
            <div className="flex items-center gap-1.5">
              <dt>Created:</dt>
              <dd className="text-ink">{formatDateTime(workspace.created_at)}</dd>
            </div>
            <div className="flex items-center gap-1.5">
              <dt>Updated:</dt>
              <dd className="text-ink">{formatDateTime(workspace.updated_at)}</dd>
            </div>
            {workspace.owner_id ? (
              <div className="flex items-center gap-1.5">
                <dt>Owner:</dt>
                <dd className="font-mono text-ink">{workspace.owner_id}</dd>
              </div>
            ) : null}
          </dl>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setRenameOpen(true)}>
            Rename workspace
          </Button>
          <Button variant="danger" onClick={() => setDeleteOpen(true)}>
            Delete workspace
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
          <SearchPanel workspaceId={workspace.id} />
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

        <CardBody>
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
        </CardBody>

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
          navigate('/', { replace: true })
        }}
      />
    </div>
  )
}
