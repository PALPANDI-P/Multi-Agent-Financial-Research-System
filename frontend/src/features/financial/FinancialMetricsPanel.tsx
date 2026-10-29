import { useMemo, useState } from 'react'

import { describeError } from '../../api/client'

import type { FinancialCalculationRead, FinancialMetricRead } from '../../api/types'

import {

  Alert,

  Badge,

  Button,

  Card,

  CardBody,

  CardHeader,

  EmptyState,

  SkeletonRows,

  Select,

  Table,

  TableBody,

  TableCell,

  TableHead,

  TableHeadCell,

  TableRow,

} from '../../components'

import { useFinancialCalculations, useFinancialMetrics } from '../../hooks/useFinancial'

import { formatDateTime } from '../../lib/format'

export interface FinancialMetricsPanelProps {

  workspaceId: string

}

function formatValue(value: unknown): string {

  if (value === null || value === undefined) return ''

  if (typeof value === 'boolean') return value ? 'true' : 'false'

  if (typeof value === 'number') return value.toLocaleString()

  if (typeof value === 'string') return value

  try {

    return JSON.stringify(value)

  } catch {

    return String(value)

  }

}

export function FinancialMetricsPanel({ workspaceId }: FinancialMetricsPanelProps) {

  const [metricType, setMetricType] = useState('')

  const metricsQuery = useFinancialMetrics(workspaceId, metricType ? { metric_type: metricType } : {})

  const calculationsQuery = useFinancialCalculations(workspaceId, {})

  const metrics = metricsQuery.data?.items ?? []

  const calculations = calculationsQuery.data?.items ?? []

  const metricTypes = useMemo(() => {

    const set = new Set(metrics.map((item) => item.metric_type))

    return Array.from(set)

  }, [metrics])

  const metricsError = metricsQuery.error ? describeError(metricsQuery.error) : null

  const calculationsError = calculationsQuery.error ? describeError(calculationsQuery.error) : null

  return (

    <div className="flex flex-col gap-4">

      <Card>

        <CardHeader

          title="Financial metrics"

          description="Metrics extracted or stored for this workspace."

          actions={

            <Button

              variant="secondary"

              size="sm"

              onClick={() => {

                void metricsQuery.refetch()

                void calculationsQuery.refetch()

              }}

            >

              Refresh

            </Button>

          }

        />

        <CardBody>

          {metricsError ? (

            <Alert tone="danger" title="Metrics could not be loaded" code={metricsError.code}>

              {metricsError.message}

            </Alert>

          ) : null}

          {metricsQuery.isPending ? (

            <SkeletonRows rows={4} />

          ) : metrics.length === 0 ? (

            <EmptyState

              title="No financial metrics yet"

              description="Run red flag analysis or add metrics to populate this table."

            />

          ) : (

            <Table>

              <TableHead>

                <TableRow>

                  <TableHeadCell>Metric</TableHeadCell>

                  <TableHeadCell>Type</TableHeadCell>

                  <TableHeadCell>Value</TableHeadCell>

                  <TableHeadCell>Unit</TableHeadCell>

                  <TableHeadCell>Red flag</TableHeadCell>

                  <TableHeadCell>Updated</TableHeadCell>

                </TableRow>

              </TableHead>

              <TableBody>

                {metrics.map((metric: FinancialMetricRead) => (

                  <TableRow key={metric.id}>

                    <TableCell>{metric.metric_name}</TableCell>

                    <TableCell>

                      <Badge tone="neutral">{metric.metric_type}</Badge>

                    </TableCell>

                    <TableCell className="font-mono tabular-nums">{formatValue(metric.metric_value)}</TableCell>

                    <TableCell>{metric.unit ?? metric.currency ?? ''}</TableCell>

                    <TableCell>

                      {metric.red_flag_level ? (

                        <Badge tone={metric.red_flag_level === 'high' || metric.red_flag_level === 'critical' ? 'danger' : 'warning'}>

                          {metric.red_flag_level}

                        </Badge>

                      ) : (

                        ''

                      )}

                    </TableCell>

                    <TableCell className="text-caption text-ink-subtle">

                      {formatDateTime(metric.updated_at ?? metric.created_at ?? '')}

                    </TableCell>

                  </TableRow>

                ))}

              </TableBody>

            </Table>

          )}

          {metricTypes.length > 0 ? (

            <div className="mt-4 max-w-xs">

              <Select

                label="Filter by type"

                id="metric-type-filter"

                value={metricType}

                onChange={(event) => setMetricType(event.target.value)}

                options={[{ value: '', label: 'All types' }, ...metricTypes.map((type) => ({ value: type, label: type }))]}

              />

            </div>

          ) : null}

        </CardBody>

      </Card>

      <Card>

        <CardHeader title="Financial calculations" description="Ratios and derived values." />

        <CardBody>

          {calculationsError ? (

            <Alert tone="danger" title="Calculations could not be loaded" code={calculationsError.code}>

              {calculationsError.message}

            </Alert>

          ) : null}

          {calculationsQuery.isPending ? (

            <SkeletonRows rows={4} />

          ) : calculations.length === 0 ? (

            <EmptyState title="No calculations yet" description="Calculations appear after analysis runs." />

          ) : (

            <Table>

              <TableHead>

                <TableRow>

                  <TableHeadCell>Calculation</TableHeadCell>

                  <TableHeadCell>Type</TableHeadCell>

                  <TableHeadCell>Result</TableHeadCell>

                  <TableHeadCell>Confidence</TableHeadCell>

                  <TableHeadCell>Calculated</TableHeadCell>

                </TableRow>

              </TableHead>

              <TableBody>

                {calculations.map((calculation: FinancialCalculationRead) => (

                  <TableRow key={calculation.id}>

                    <TableCell>{calculation.calculation_name}</TableCell>

                    <TableCell>

                      <Badge tone="neutral">{calculation.calculation_type}</Badge>

                    </TableCell>

                    <TableCell className="font-mono tabular-nums">{formatValue(calculation.result_value)}</TableCell>

                    <TableCell>{formatValue(calculation.confidence_score)}</TableCell>

                    <TableCell className="text-caption text-ink-subtle">

                      {formatDateTime(calculation.calculated_at ?? calculation.created_at ?? '')}

                    </TableCell>

                  </TableRow>

                ))}

              </TableBody>

            </Table>

          )}

        </CardBody>

      </Card>

    </div>

  )

}

