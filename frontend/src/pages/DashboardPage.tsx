import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { describeError } from '../api/client'
import { getHealth } from '../api/health'
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Chip,
  EmptyState,
  Input,
  MetricCard,
  PageHeader,
  Pagination,
  Select,
  SkeletonCard,
  Spinner,
} from '../components'
import {
  DocumentIcon,
  SearchIcon,
  TargetIcon,
  UserIcon,
  WorkspaceIcon,
} from '../components/icons'
import { WorkspaceDialog, WorkspaceList } from '../features/workspaces'
import { useAuth } from '../hooks/useAuth'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useScenarios } from '../hooks/useScenarios'
import { useWorkspaces } from '../hooks/useWorkspaces'
import { formatNumber } from '../lib/format'

export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [nameFilter, setNameFilter] = useState('')
  const [limit, setLimit] = useState(10)
  const [offset, setOffset] = useState(0)
  const [createOpen, setCreateOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [targetWorkspaceId, setTargetWorkspaceId] = useState('')

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
  const scenariosQuery = useScenarios()

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

  const scenarios = useMemo(() => scenariosQuery.data ?? [], [scenariosQuery.data])
  const assignedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.key === user?.scenario_key) ?? null,
    [scenarios, user?.scenario_key],
  )

  const documentsInListedWorkspaces = useMemo(
    () => workspaces.reduce((sum, workspace) => sum + (workspace.document_count ?? 0), 0),
    [workspaces],
  )

  // The suggested queries need a target workspace: the first one of the
  // listing is the default, and a selection that is no longer part of the
  // listing falls back to it.
  const targetWorkspaceIdIsListed = workspaces.some(
    (workspace) => workspace.id === targetWorkspaceId,
  )
  const effectiveTargetWorkspaceId = targetWorkspaceIdIsListed
    ? targetWorkspaceId
    : (workspaces[0]?.id ?? '')

  const runSuggestedQuery = (query: string) => {
    if (!effectiveTargetWorkspaceId) return
    navigate(`/app/workspaces/${effectiveTargetWorkspaceId}?q=${encodeURIComponent(query)}`)
  }

  return (
    <div className="mx-auto flex w-full max-w-page flex-col gap-10 px-5 py-10 sm:px-8 sm:py-14">
      <PageHeader
        eyebrow="Research workspace"
        title="Research workspaces"
        description="Organise research documents by company, sector or theme, then search the indexed passages of a workspace."
        actions={
          <Button onClick={() => setCreateOpen(true)}>Create workspace</Button>
        }
      />

      {/* The quiet status band: the role of the account on the left, the
          state of the API on the right. */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-y border-line py-3 text-caption text-ink-subtle">
        {user ? (
          <span className="inline-flex items-center gap-2">
            <UserIcon size={13} className="text-ink-subtle" />
            <span className="font-mono">{user.role}</span>
            {user.full_name ? <span className="text-ink-muted">{user.full_name}</span> : null}
          </span>
        ) : null}
        {user?.scenario_key ? (
          <Badge tone="neutral" title="scenario key">
            <span className="font-mono">{user.scenario_key}</span>
          </Badge>
        ) : null}

        <span className="inline-flex items-center gap-2 font-mono sm:ml-auto">
          {healthQuery.isSuccess ? (
            <>
              <span className="h-1.5 w-1.5 rounded-pill bg-success-600" aria-hidden="true" />
              <span>api</span>
              <span className="text-ink-muted">{healthQuery.data.status}</span>
              <span className="text-ink-muted">v{healthQuery.data.version}</span>
              <span className="text-ink-muted">{healthQuery.data.environment}</span>
            </>
          ) : healthQuery.isError ? (
            <span>api status unavailable</span>
          ) : (
            <Spinner label="Checking API status" hideLabel />
          )}
        </span>
      </div>

      {/* The metric row: one panel, three figures, hairline dividers. */}
      <Card className="overflow-hidden">
        <div className="grid divide-y divide-line-faint sm:grid-cols-3 sm:divide-y-0 sm:divide-x">
          <MetricCard
            label="Workspaces"
            value={workspacesQuery.isPending ? '—' : formatNumber(total)}
            hint="The total the workspaces API reports for the current filter."
            icon={<WorkspaceIcon size={14} />}
            valueSize="lg"
            className="rounded-none border-0 bg-transparent p-5 shadow-none sm:p-7"
          />
          <MetricCard
            label="Documents"
            value={workspacesQuery.isPending ? '—' : formatNumber(documentsInListedWorkspaces)}
            hint="The sum of the document counts of the workspaces listed below."
            icon={<DocumentIcon size={14} />}
            valueSize="lg"
            className="rounded-none border-0 bg-transparent p-5 shadow-none sm:p-7"
          />
          <MetricCard
            label="Scenario"
            value={assignedScenario ? assignedScenario.title : (user?.scenario_key ?? '—')}
            valueSize="sm"
            hint="The analyst scenario of your account."
            icon={<TargetIcon size={14} />}
            className="rounded-none border-0 bg-transparent p-5 shadow-none sm:p-7"
          />
        </div>
      </Card>

      {user?.scenario_key && !assignedScenario ? (
        <Alert
          tone="info"
          title="The scenario of your account is not served by the API"
          code={user.scenario_key}
        >
          Your account carries the scenario key above, but the API did not return a matching
          scenario, so no suggested query is shown.
        </Alert>
      ) : null}

      {assignedScenario ? (
        <Card>
          <CardHeader
            title="Suggested queries"
            description={`Questions the ${assignedScenario.title} scenario suggests. They open the search of the workspace you pick.`}
          />
          <CardBody>
            {workspaces.length === 0 ? (
              <p className="text-small text-ink-muted">
                There is no workspace yet. Create one, upload a document and the suggested queries
                become available.
              </p>
            ) : (
              <div className="grid gap-6 lg:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] lg:items-end">
                <Select
                  label="Target workspace"
                  id="suggested-query-workspace"
                  value={effectiveTargetWorkspaceId}
                  onChange={(event) => setTargetWorkspaceId(event.target.value)}
                  options={workspaces.map((workspace) => ({
                    value: workspace.id,
                    label: workspace.name,
                  }))}
                  hint="The query is searched in the workspace of your choice."
                />

                {assignedScenario.suggested_queries.length > 0 ? (
                  <ul className="flex flex-wrap gap-2.5">
                    {assignedScenario.suggested_queries.map((query) => (
                      <li key={query}>
                        <Chip
                          icon={<SearchIcon size={14} />}
                          disabled={!effectiveTargetWorkspaceId}
                          onClick={() => runSuggestedQuery(query)}
                        >
                          {query}
                        </Chip>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-small text-ink-muted">
                    The API returned no suggested query for this scenario.
                  </p>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      ) : null}

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
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {[0, 1, 2].map((index) => (
                <SkeletonCard key={index} />
              ))}
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
    </div>
  )
}