import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { describeError } from '../api/client'
import { getHealth } from '../api/health'
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  Input,
  Pagination,
  Spinner,
} from '../components'
import { WorkspaceDialog, WorkspaceList } from '../features/workspaces'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useWorkspaces } from '../hooks/useWorkspaces'

export function DashboardPage() {
  const [nameFilter, setNameFilter] = useState('')
  const [limit, setLimit] = useState(10)
  const [offset, setOffset] = useState(0)
  const [createOpen, setCreateOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const debouncedName = useDebouncedValue(nameFilter, 300)

  const params = useMemo(
    () => ({
      limit,
      offset,
      ...(debouncedName.trim() ? { name: debouncedName.trim() } : {}),
    }),
    [limit, offset, debouncedName],
  )

  const workspacesQuery = useWorkspaces(params)

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => getHealth(signal),
    retry: false,
    staleTime: 60_000,
  })

  const workspaces = useMemo(
    () => workspacesQuery.data?.items ?? [],
    [workspacesQuery.data],
  )
  const total = workspacesQuery.data?.total ?? 0

  // The API filters by name server-side; this second pass keeps the filter
  // accurate if the backend ignores the `name` query parameter.
  const visibleWorkspaces = useMemo(() => {
    const term = debouncedName.trim().toLowerCase()
    if (!term) return workspaces
    return workspaces.filter((workspace) => workspace.name.toLowerCase().includes(term))
  }, [workspaces, debouncedName])

  const queryError = workspacesQuery.error ? describeError(workspacesQuery.error) : null

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Research workspaces</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Organise research documents by company, sector or theme, then search the indexed
            passages.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>Create workspace</Button>
      </header>

      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-subtle">
        {healthQuery.isSuccess ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-success-600" aria-hidden="true" />
            API <span className="font-mono text-ink-muted">{healthQuery.data.status}</span> ·{' '}
            <span className="font-mono text-ink-muted">{healthQuery.data.app}</span>{' '}
            <span className="font-mono text-ink-muted">v{healthQuery.data.version}</span> ·{' '}
            <span className="font-mono text-ink-muted">{healthQuery.data.environment}</span>
          </span>
        ) : healthQuery.isError ? (
          <span>API status unavailable</span>
        ) : (
          <Spinner label="Checking API status" hideLabel />
        )}
      </div>

      {notice ? (
        <Alert tone="success" title="Workspace created">
          {notice}
        </Alert>
      ) : null}

      {queryError ? (
        <Alert
          tone="danger"
          title="The workspace list could not be loaded"
          code={queryError.code}
          action={
            <Button variant="secondary" size="sm" onClick={() => void workspacesQuery.refetch()}>
              Try again
            </Button>
          }
        >
          {queryError.message}
        </Alert>
      ) : null}

      <Card>
        <CardHeader
          title="All workspaces"
          description="Names, descriptions, document counts and timestamps are read from the API."
          actions={
            <div className="w-full sm:w-72">
              <Input
                label="Search workspaces by name"
                id="workspace-name-filter"
                type="search"
                value={nameFilter}
                onChange={(event) => {
                  setNameFilter(event.target.value)
                  setOffset(0)
                }}
                placeholder="Filter by name…"
              />
            </div>
          }
        />
        <CardBody>
          {workspacesQuery.isPending ? (
            <div className="flex items-center justify-center py-10">
              <Spinner label="Loading workspaces" />
            </div>
          ) : workspacesQuery.isError ? (
            <EmptyState
              title="The workspace list is unavailable"
              description="The API returned an error, so no workspaces could be loaded. Use “Try again” to retry the request."
              action={
                <Button variant="secondary" onClick={() => void workspacesQuery.refetch()}>
                  Try again
                </Button>
              }
            />
          ) : (
            <WorkspaceList
              workspaces={visibleWorkspaces}
              emptyAction={
                <Button onClick={() => setCreateOpen(true)}>Create workspace</Button>
              }
            />
          )}
        </CardBody>
        {!workspacesQuery.isError ? (
          <Pagination
            total={total}
            limit={limit}
            offset={offset}
            onOffsetChange={setOffset}
            onLimitChange={(nextLimit) => {
              setLimit(nextLimit)
              setOffset(0)
            }}
            itemLabel="workspaces"
          />
        ) : null}
      </Card>

      <WorkspaceDialog
        open={createOpen}
        mode="create"
        onClose={() => setCreateOpen(false)}
        onSaved={(created) => {
          setNotice(`“${created.name}” is ready for documents.`)
        }}
      />


      <p className="text-xs text-ink-subtle">
        Open a workspace to upload documents and to query the indexed passages.{' '}
        <Link to="/" className="underline hover:text-ink">
          Back to all workspaces
        </Link>
        .
      </p>
    </div>
  )
}