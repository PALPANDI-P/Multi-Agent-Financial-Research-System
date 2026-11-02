import { useState } from 'react'

import type { FormEvent } from 'react'

import { describeError } from '../../api/client'

import { Alert, Button, Card, CardBody, CardHeader, Select } from '../../components'

import { useExport } from '../../hooks/useFinancial'

import type { SelectOption } from '../../components/Select'

export interface ExportPanelProps {
  workspaceId: string
}

const FORMAT_OPTIONS: SelectOption[] = [
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
  { value: 'xlsx', label: 'Excel (XLSX)' },
  { value: 'pdf', label: 'PDF' },
]

const DATA_TYPE_OPTIONS: SelectOption[] = [
  { value: 'metrics', label: 'Metrics' },
  { value: 'calculations', label: 'Calculations' },
  { value: 'red_flags', label: 'Red flags' },
  { value: 'forecast', label: 'Forecast' },
]

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export function ExportPanel({ workspaceId }: ExportPanelProps) {
  const [format, setFormat] = useState('csv')
  const [dataType, setDataType] = useState('metrics')

  const exportMutation = useExport(workspaceId)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      const blob = await exportMutation.mutateAsync({
        format: format as 'csv' | 'json' | 'xlsx' | 'pdf',
        data_type: dataType as 'metrics' | 'calculations' | 'red_flags' | 'forecast',
      })
      const ext = format === 'xlsx' ? 'xlsx' : format
      downloadBlob(blob, `${dataType}_export.${ext}`)
    } catch {
      // rendered below
    }
  }

  const error = exportMutation.error ? describeError(exportMutation.error) : null

  return (
    <Card>
      <CardHeader title="Export" description="Download workspace data in a chosen format." />
      <CardBody className="flex flex-col gap-3">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Select
              label="Format"
              id="export-format"
              options={FORMAT_OPTIONS}
              value={format}
              onChange={(event) => setFormat(event.target.value)}
            />
            <Select
              label="Data type"
              id="export-data-type"
              options={DATA_TYPE_OPTIONS}
              value={dataType}
              onChange={(event) => setDataType(event.target.value)}
            />
          </div>
          <div>
            <Button type="submit" loading={exportMutation.isPending} loadingLabel="Exporting...">
              Download
            </Button>
          </div>
        </form>

        {error ? (
          <Alert tone="danger" title="Export failed" code={error.code}>
            {error.message}
          </Alert>
        ) : null}
      </CardBody>
    </Card>
  )
}