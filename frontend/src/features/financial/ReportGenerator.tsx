import { useState } from 'react'

import type { FormEvent } from 'react'

import { describeError } from '../../api/client'

import { Alert, Button, Card, CardBody, CardHeader, Input, SkeletonText, Textarea } from '../../components'

import { useGenerateReport } from '../../hooks/useFinancial'

import type { FinancialAgentResult } from '../../api/types'

export interface ReportGeneratorProps {

  workspaceId: string

}

function pickReportText(result: FinancialAgentResult | undefined): string {

  if (!result) return ''

  const candidates = ['report', 'content', 'markdown', 'text', 'summary', 'answer']

  for (const key of candidates) {

    const value = result[key]

    if (typeof value === 'string' && value.trim()) return value

  }

  // fallback: stringify

  try {

    return JSON.stringify(result, null, 2)

  } catch {

    return ''

  }

}

function pickDownloadUrl(result: FinancialAgentResult | undefined): string | null {

  if (!result) return null

  const candidates = ['download_url', 'file_url', 'url']

  for (const key of candidates) {

    const value = result[key]

    if (typeof value === 'string' && value.trim()) return value

  }

  return null

}

export function ReportGenerator({ workspaceId }: ReportGeneratorProps) {

  const [title, setTitle] = useState('')

  const [question, setQuestion] = useState('')

  const report = useGenerateReport(workspaceId)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {

    event.preventDefault()

    try {

      await report.mutateAsync({

        ...(title.trim() ? { title: title.trim() } : {}),

        ...(question.trim() ? { question: question.trim() } : {}),

        include_metrics: true,

        include_red_flags: true,

      })

    } catch {

      // rendered below

    }

  }

  const reportText = pickReportText(report.data)

  const downloadUrl = pickDownloadUrl(report.data)

  const error = report.error ? describeError(report.error) : null

  const handleDownload = () => {

    if (downloadUrl) {

      window.open(downloadUrl, '_blank', 'noopener,noreferrer')

      return

    }

    const blob = new Blob([reportText], { type: 'text/markdown;charset=utf-8' })

    const url = URL.createObjectURL(blob)

    const anchor = document.createElement('a')

    anchor.href = url

    anchor.download = `${title.trim() || 'financial-report'}.md`

    document.body.appendChild(anchor)

    anchor.click()

    document.body.removeChild(anchor)

    URL.revokeObjectURL(url)

  }

  return (

    <Card>

      <CardHeader title="Report generation" description="Generate a downloadable research report." />

      <CardBody className="flex flex-col gap-3">

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">

          <Input label="Title (optional)" id="report-title" value={title} onChange={(event) => setTitle(event.target.value)} />

          <Textarea

            label="Question / scope (optional)"

            id="report-question"

            value={question}

            onChange={(event) => setQuestion(event.target.value)}

            rows={3}

          />

          <div>

            <Button type="submit" loading={report.isPending} loadingLabel="Generating...">

              Generate report

            </Button>

          </div>

        </form>

        {error ? (

          <Alert tone="danger" title="Report generation failed" code={error.code}>

            {error.message}

          </Alert>

        ) : null}

        {report.isPending ? <SkeletonText lines={8} /> : null}

        {report.data && !report.isPending ? (

          <div className="flex flex-col gap-3">

            <Textarea label="Generated report" id="report-output" readOnly value={reportText} rows={12} />

            <div>

              <Button onClick={handleDownload}>Download report</Button>

            </div>

          </div>

        ) : null}

      </CardBody>

    </Card>

  )

}

