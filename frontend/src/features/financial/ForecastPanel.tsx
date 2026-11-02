import { useState } from 'react'

import type { FormEvent } from 'react'

import { describeError } from '../../api/client'

import type { ForecastObservation, ForecastResult } from '../../api/types'

import {
  Alert,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  Select,
  SkeletonText,
  Textarea,
} from '../../components'

import { useForecast } from '../../hooks/useFinancial'

import type { SelectOption } from '../../components/Select'

export interface ForecastPanelProps {
  workspaceId: string
}

type ForecastResponse = ForecastResult & {
  scenarios?: Record<string, ForecastResult>
  conservative?: ForecastResult
  baseline?: ForecastResult
  optimistic?: ForecastResult
  adjustments?: unknown
  metric?: string
  source_count?: number
}

const METHOD_OPTIONS: SelectOption[] = [
  { value: 'naive', label: 'Naive' },
  { value: 'mean', label: 'Mean' },
  { value: 'linear', label: 'Linear' },
]

function num(value: unknown): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function ForecastChart({
  historical,
  normalForecast,
  scenarioForecasts,
}: {
  historical: Array<{ period: unknown; value: unknown }>
  normalForecast?: Array<{ period: unknown; value: unknown }>
  scenarioForecasts?: {
    conservative: Array<{ period: unknown; value: unknown }>
    baseline: Array<{ period: unknown; value: unknown }>
    optimistic: Array<{ period: unknown; value: unknown }>
  } | null
}) {
  const histValues = historical.map((h) => num(h.value))
  const baseSeries = scenarioForecasts?.baseline ?? normalForecast ?? []
  const fcValues = baseSeries.map((f) => num(f.value))
  const allValues = [...histValues, ...fcValues]
  if (allValues.length === 0) return null
  const min = Math.min(...allValues)
  const max = Math.max(...allValues)
  const range = max - min || 1
  const total = historical.length + baseSeries.length
  const xAt = (i: number) =>
    total <= 1 ? 150 : 20 + (i / (total - 1)) * 260
  const yAt = (v: number) => 100 - ((v - min) / range) * 80

  const histPoints = historical.map((h, i) => `${xAt(i)},${yAt(num(h.value))}`).join(' ')
  const normalPoints = (normalForecast ?? [])
    .map((f, i) => `${xAt(historical.length + i)},${yAt(num(f.value))}`)
    .join(' ')
  const consPoints = (scenarioForecasts?.conservative ?? [])
    .map((f, i) => `${xAt(historical.length + i)},${yAt(num(f.value))}`)
    .join(' ')
  const basePoints = (scenarioForecasts?.baseline ?? [])
    .map((f, i) => `${xAt(historical.length + i)},${yAt(num(f.value))}`)
    .join(' ')
  const optPoints = (scenarioForecasts?.optimistic ?? [])
    .map((f, i) => `${xAt(historical.length + i)},${yAt(num(f.value))}`)
    .join(' ')

  return (
    <div className="rounded-card border border-line bg-surface p-3">
      <svg viewBox="0 0 300 120" className="h-40 w-full" role="img" aria-label="Forecast chart">
        <line x1="20" y1="100" x2="280" y2="100" stroke="currentColor" className="text-line" strokeWidth="1" />
        {histPoints ? (
          <polyline points={histPoints} fill="none" stroke="#64748b" strokeWidth="2" />
        ) : null}
        {normalPoints ? (
          <polyline points={normalPoints} fill="none" stroke="#2563eb" strokeWidth="2" strokeDasharray="4 3" />
        ) : null}
        {consPoints ? (
          <polyline points={consPoints} fill="none" stroke="#dc2626" strokeWidth="2" strokeDasharray="4 3" />
        ) : null}
        {basePoints ? (
          <polyline points={basePoints} fill="none" stroke="#2563eb" strokeWidth="2" strokeDasharray="4 3" />
        ) : null}
        {optPoints ? (
          <polyline points={optPoints} fill="none" stroke="#16a34a" strokeWidth="2" strokeDasharray="4 3" />
        ) : null}
      </svg>
      <div className="mt-2 flex flex-wrap gap-3 text-caption text-ink-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-4 rounded-full bg-slate-500" /> Historical
        </span>
        {scenarioForecasts ? (
          <>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-4 rounded-full bg-red-600" /> Conservative
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-4 rounded-full bg-blue-600" /> Baseline
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-4 rounded-full bg-green-600" /> Optimistic
            </span>
          </>
        ) : (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-4 rounded-full bg-blue-600" /> Forecast
          </span>
        )}
      </div>
    </div>
  )
}

export function ForecastPanel({ workspaceId }: ForecastPanelProps) {
  const [horizon, setHorizon] = useState('3')
  const [method, setMethod] = useState('linear')
  const [observationsText, setObservationsText] = useState('')
  const [scenario, setScenario] = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)

  const forecast = useForecast(workspaceId)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setParseError(null)

    let observations: ForecastObservation[] | undefined
    if (observationsText.trim()) {
      try {
        const parsed = JSON.parse(observationsText)
        if (!Array.isArray(parsed)) throw new Error('Observations must be a JSON array')
        observations = parsed.map((item, index) => {
          if (!item || typeof item !== 'object') {
            throw new Error(`Observation ${index + 1} is not an object`)
          }
          const period = String((item as { period?: unknown }).period ?? '').trim()
          const value = Number((item as { value?: unknown }).value)
          if (!period) throw new Error(`Observation ${index + 1} is missing period`)
          if (!Number.isFinite(value)) throw new Error(`Observation ${index + 1} has invalid value`)
          return { period, value }
        })
      } catch (error) {
        setParseError(error instanceof Error ? error.message : 'Invalid observations JSON')
        return
      }
    }

    try {
      await forecast.mutateAsync({
        observations,
        horizon: Number(horizon) || 1,
        method,
        scenario,
        ...(scenario ? { adjustments: { method } } : {}),
      })
    } catch {
      // rendered below
    }
  }

  const result = forecast.data as ForecastResponse | undefined
  const isScenario = Boolean(result?.conservative && result?.baseline && result?.optimistic)

  const historical = (isScenario ? result?.baseline?.historical : result?.historical) ?? []
  const assumptions = (isScenario ? result?.baseline?.assumptions : result?.assumptions) ?? []
  const limitations = (isScenario ? result?.baseline?.limitations : result?.limitations) ?? []
  const evaluation = isScenario ? result?.baseline?.evaluation : result?.evaluation

  const error = forecast.error
    ? describeError(forecast.error)
    : parseError
      ? { message: parseError, code: 'invalid_input' }
      : null

  return (
    <Card>
      <CardHeader title="Forecasting" description="Run time-series forecasts from historical observations." />
      <CardBody className="flex flex-col gap-3">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Input
              label="Horizon"
              id="forecast-horizon"
              type="number"
              min={1}
              value={horizon}
              onChange={(event) => setHorizon(event.target.value)}
            />
            <Select
              label="Method"
              id="forecast-method"
              options={METHOD_OPTIONS}
              value={method}
              onChange={(event) => setMethod(event.target.value)}
            />
            <label className="flex items-end gap-2 pb-2 text-small text-ink">
              <input
                type="checkbox"
                checked={scenario}
                onChange={(event) => setScenario(event.target.checked)}
                className="h-4 w-4 rounded border-line-strong"
              />
              Scenario analysis
            </label>
          </div>
          <Textarea
            label="Observations (JSON array of {period, value})"
            id="forecast-observations"
            value={observationsText}
            onChange={(event) => setObservationsText(event.target.value)}
            rows={5}
            placeholder='[{"period":"2020","value":100},{"period":"2021","value":120}]'
          />
          <div>
            <Button type="submit" loading={forecast.isPending} loadingLabel="Forecasting...">
              Run forecast
            </Button>
          </div>
        </form>

        {error ? (
          <Alert tone="danger" title="Forecast failed" code={error.code}>
            {error.message}
          </Alert>
        ) : null}

        {forecast.isPending ? <SkeletonText lines={8} /> : null}

        {result && !forecast.isPending ? (
          <div className="flex flex-col gap-4">
            <ForecastChart
              historical={historical}
              normalForecast={isScenario ? undefined : (result.forecast ?? [])}
              scenarioForecasts={
                isScenario
                  ? {
                      conservative: result.conservative?.forecast ?? [],
                      baseline: result.baseline?.forecast ?? [],
                      optimistic: result.optimistic?.forecast ?? [],
                    }
                  : null
              }
            />

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="flex flex-col gap-2">
                <h3 className="text-small font-semibold text-ink">Historical</h3>
                <div className="overflow-x-auto rounded-card border border-line">
                  <table className="w-full border-collapse text-small">
                    <thead>
                      <tr className="bg-surface-muted/60">
                        <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Period</th>
                        <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {historical.map((row, index) => (
                        <tr key={index} className="bg-surface">
                          <td className="px-3 py-2 text-ink">{String(row.period)}</td>
                          <td className="px-3 py-2 text-ink">{num(row.value).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <h3 className="text-small font-semibold text-ink">Forecast</h3>
                <div className="overflow-x-auto rounded-card border border-line">
                  {isScenario ? (
                    <table className="w-full border-collapse text-small">
                      <thead>
                        <tr className="bg-surface-muted/60">
                          <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Period</th>
                          <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Conservative</th>
                          <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Baseline</th>
                          <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Optimistic</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {(result.baseline?.forecast ?? []).map((row, index) => (
                          <tr key={index} className="bg-surface">
                            <td className="px-3 py-2 text-ink">{String(row.period)}</td>
                            <td className="px-3 py-2 text-ink">{num(result.conservative?.forecast?.[index]?.value).toLocaleString()}</td>
                            <td className="px-3 py-2 text-ink">{num(row.value).toLocaleString()}</td>
                            <td className="px-3 py-2 text-ink">{num(result.optimistic?.forecast?.[index]?.value).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <table className="w-full border-collapse text-small">
                      <thead>
                        <tr className="bg-surface-muted/60">
                          <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Period</th>
                          <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Forecast</th>
                          <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Lower</th>
                          <th className="border-b border-line px-3 py-2 text-left text-micro font-semibold uppercase text-ink-subtle">Upper</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {(result.forecast ?? []).map((row, index) => (
                          <tr key={index} className="bg-surface">
                            <td className="px-3 py-2 text-ink">{String(row.period)}</td>
                            <td className="px-3 py-2 text-ink">{num(row.value).toLocaleString()}</td>
                            <td className="px-3 py-2 text-ink">{row.lower != null ? num(row.lower).toLocaleString() : '—'}</td>
                            <td className="px-3 py-2 text-ink">{row.upper != null ? num(row.upper).toLocaleString() : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>

            {assumptions.length > 0 ? (
              <div className="flex flex-col gap-1.5">
                <h3 className="text-small font-semibold text-ink">Assumptions</h3>
                <ul className="list-disc pl-5 text-small text-ink-muted">
                  {assumptions.map((item, index) => (
                    <li key={index}>{String(item)}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {limitations.length > 0 ? (
              <div className="flex flex-col gap-1.5">
                <h3 className="text-small font-semibold text-ink">Limitations</h3>
                <ul className="list-disc pl-5 text-small text-ink-muted">
                  {limitations.map((item, index) => (
                    <li key={index}>{String(item)}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {evaluation ? (
              <div className="flex flex-col gap-1.5">
                <h3 className="text-small font-semibold text-ink">Evaluation</h3>
                <pre className="overflow-x-auto rounded-card border border-line bg-surface-muted/40 p-3 text-caption text-ink">
                  {JSON.stringify(evaluation, null, 2)}
                </pre>
              </div>
            ) : null}
          </div>
        ) : null}
      </CardBody>
    </Card>
  )
}