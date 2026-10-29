import { useState } from 'react'

import { describeError } from '../../api/client'

import type { RedFlagFindingRead } from '../../api/types'

import {

  Alert,

  Badge,

  Button,

  Card,

  CardBody,

  CardHeader,

  EmptyState,

  Select,

  SkeletonRows,

  Table,

  TableBody,

  TableCell,

  TableHead,

  TableHeadCell,

  TableRow,

} from '../../components'

import {

  useAnalyzeRedFlags,

  useRedFlagFindings,

  useUpdateRedFlagFinding,

  useDeleteRedFlagFinding,

} from '../../hooks/useFinancial'

import { formatDateTime } from '../../lib/format'

export interface RedFlagDashboardProps {

  workspaceId: string

  documentId?: string

}

function severityTone(severity: string): 'danger' | 'warning' | 'info' | 'neutral' {

  const normalized = severity.toLowerCase()

  if (normalized === 'critical' || normalized === 'high') return 'danger'

  if (normalized === 'medium') return 'warning'

  return 'info'

}

export function RedFlagDashboard({ workspaceId, documentId }: RedFlagDashboardProps) {

  const [severity, setSeverity] = useState('')

  const [status, setStatus] = useState('')

  const findingsQuery = useRedFlagFindings(workspaceId, {

    ...(severity ? { severity } : {}),

    ...(status ? { status } : {}),

    ...(documentId ? { document_id: documentId } : {}),

  })

  const analyze = useAnalyzeRedFlags(workspaceId)

  const updateFinding = useUpdateRedFlagFinding(workspaceId)

  const deleteFinding = useDeleteRedFlagFinding(workspaceId)

  const findings = findingsQuery.data?.items ?? []

  const error = findingsQuery.error ? describeError(findingsQuery.error) : null

  const handleAnalyze = async () => {

    try {

      await analyze.mutateAsync({ documentId })

    } catch {

      // rendered below

    }

  }

  const handleResolve = async (finding: RedFlagFindingRead) => {

    try {

      await updateFinding.mutateAsync({

        id: finding.id,

        payload: { status: 'resolved', resolution_notes: finding.resolution_notes ?? 'Resolved in UI' },

      })

    } catch {

      // rendered below

    }

  }

  const handleDelete = async (finding: RedFlagFindingRead) => {

    try {

      await deleteFinding.mutateAsync(finding.id)

    } catch {

      // rendered below

    }

  }

  return (

    <Card>

      <CardHeader

        title="Red flag analysis"

        description="Risk findings detected across the workspace documents."

        actions={

          <Button onClick={handleAnalyze} loading={analyze.isPending} loadingLabel="Analyzing">

            {documentId ? 'Analyze document' : 'Analyze workspace'}

          </Button>

        }

      />

      <CardBody className="flex flex-col gap-3">

        {(analyze.error || updateFinding.error || deleteFinding.error) && (

          <Alert tone="danger" title="Red flag action failed" code={describeError(analyze.error ?? updateFinding.error ?? deleteFinding.error).code}>

            {describeError(analyze.error ?? updateFinding.error ?? deleteFinding.error).message}

          </Alert>

        )}

        <div className="grid gap-3 sm:grid-cols-2">

          <Select

            label="Severity"

            id="red-flag-severity"

            value={severity}

            onChange={(event) => setSeverity(event.target.value)}

            options={[

              { value: '', label: 'All severities' },

              { value: 'critical', label: 'critical' },

              { value: 'high', label: 'high' },

              { value: 'medium', label: 'medium' },

              { value: 'low', label: 'low' },

            ]}

          />

          <Select

            label="Status"

            id="red-flag-status"

            value={status}

            onChange={(event) => setStatus(event.target.value)}

            options={[

              { value: '', label: 'All statuses' },

              { value: 'open', label: 'open' },

              { value: 'resolved', label: 'resolved' },

            ]}

          />

        </div>

        {error ? (

          <Alert tone="danger" title="Red flags could not be loaded" code={error.code}>

            {error.message}

          </Alert>

        ) : null}

        {findingsQuery.isPending ? (

          <SkeletonRows rows={4} />

        ) : findings.length === 0 ? (

          <EmptyState

            title="No red flags found"

            description="Run an analysis to detect potential issues."

          />

        ) : (

          <Table>

            <TableHead>

              <TableRow>

                <TableHeadCell>Flag</TableHeadCell>

                <TableHeadCell>Severity</TableHeadCell>

                <TableHeadCell>Status</TableHeadCell>

                <TableHeadCell>Detected</TableHeadCell>

                <TableHeadCell>Actions</TableHeadCell>

              </TableRow>

            </TableHead>

            <TableBody>

              {findings.map((finding: RedFlagFindingRead) => (

                <TableRow key={finding.id}>

                  <TableCell>

                    <div className="flex flex-col gap-1">

                      <span className="font-medium text-ink">{finding.title ?? finding.flag_type}</span>

                      {finding.description ? (

                        <span className="text-caption text-ink-muted">{finding.description}</span>

                      ) : null}

                      {finding.source_excerpt ? (

                        <span className="text-caption text-ink-subtle italic">{finding.source_excerpt}</span>

                      ) : null}

                    </div>

                  </TableCell>

                  <TableCell>

                    <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>

                  </TableCell>

                  <TableCell>

                    <Badge tone={finding.status === 'resolved' ? 'success' : 'warning'}>{finding.status}</Badge>

                  </TableCell>

                  <TableCell className="text-caption text-ink-subtle">

                    {formatDateTime(finding.detected_at ?? finding.created_at ?? '')}

                  </TableCell>

                  <TableCell>

                    <div className="flex flex-wrap gap-2">

                      {finding.status !== 'resolved' ? (

                        <Button size="sm" variant="secondary" onClick={() => void handleResolve(finding)}>

                          Resolve

                        </Button>

                      ) : null}

                      <Button

                        size="sm"

                        variant="ghost"

                        className="text-danger-700"

                        onClick={() => void handleDelete(finding)}

                      >

                        Delete

                      </Button>

                    </div>

                  </TableCell>

                </TableRow>

              ))}

            </TableBody>

          </Table>

        )}

        {analyze.data ? (

          <Alert tone="success" title="Analysis complete">

            {String((analyze.data as Record<string, unknown>).summary ? JSON.stringify((analyze.data as Record<string, unknown>).summary) : 'Red flag analysis finished.')}

          </Alert>

        ) : null}

      </CardBody>

    </Card>

  )

}

