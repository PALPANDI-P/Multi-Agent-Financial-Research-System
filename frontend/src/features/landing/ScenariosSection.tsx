import { describeError } from '../../api/client'
import { Alert, Badge, Button, SectionIntro, Skeleton } from '../../components'
import { ArrowUpRightIcon, TargetIcon } from '../../components/icons'
import { useScenarios } from '../../hooks/useScenarios'

export function ScenariosSection() {
  const scenariosQuery = useScenarios()
  const scenarios = scenariosQuery.data ?? []
  const error = scenariosQuery.error ? describeError(scenariosQuery.error) : null

  return (
    <section id="scenarios" className="border-b border-line bg-canvas scroll-mt-20">
      <div className="mx-auto w-full max-w-wide px-5 py-20 sm:px-8 sm:py-28">
        <SectionIntro
          eyebrow="Who it is for"
          title="Three analyst personas"
          lead={
            <>
              The product ships with three research scenarios. They describe the focus areas and the
              questions each persona is likely to ask; the copy is served by the API, so it always
              matches the running backend.
            </>
          }
        />

        {scenariosQuery.isPending ? (
          <div className="mt-16 grid gap-5 lg:grid-cols-3">
            {[0, 1, 2].map((index) => (
              <div
                key={index}
                className="flex flex-col gap-4 rounded-card border border-line bg-surface p-7"
              >
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-5/6" />
                <Skeleton className="h-6 w-24 rounded-pill" />
              </div>
            ))}
          </div>
        ) : null}

        {error ? (
          <div className="mt-12">
            <Alert
              tone="warning"
              title="The analyst scenarios could not be loaded"
              code={error.code}
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void scenariosQuery.refetch()}
                >
                  Try again
                </Button>
              }
            >
              {error.message} The rest of the page is unaffected.
            </Alert>
          </div>
        ) : null}

        {!scenariosQuery.isPending && !error && scenarios.length === 0 ? (
          <div className="mt-12 rounded-card border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
            <p className="text-subtitle text-ink">No scenarios are configured</p>
            <p className="mt-2 text-small text-ink-muted">
              The API answered with an empty list of analyst scenarios.
            </p>
          </div>
        ) : null}

        {scenarios.length > 0 ? (
          <ul className="mt-16 grid gap-6 lg:grid-cols-3">
            {scenarios.map((scenario) => (
              <li key={scenario.key} className="h-full">
                <article className="flex h-full flex-col gap-4 rounded-card border border-line bg-surface p-6 shadow-card card-interactive sm:p-7">
                  <header className="flex items-start justify-between gap-3">
                    <h3 className="text-subtitle text-ink">{scenario.title}</h3>
                    <Badge tone="brand" title="scenario key">
                      <span className="font-mono text-micro">{scenario.key}</span>
                    </Badge>
                  </header>

                  <p className="text-small font-medium text-ink">{scenario.tagline}</p>

                  <p className="text-small leading-relaxed text-ink-muted">{scenario.description}</p>

                  {scenario.focus_areas.length > 0 ? (
                    <div>
                      <p className="text-micro font-semibold tracking-[0.12em] text-ink-subtle uppercase">
                        Focus areas
                      </p>
                      <ul className="mt-2.5 flex flex-wrap gap-1.5">
                        {scenario.focus_areas.map((area) => (
                          <li
                            key={area}
                            className="rounded-pill border border-line bg-surface-muted/70 px-2.5 py-0.5 text-caption text-ink-muted"
                          >
                            {area}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {scenario.suggested_queries.length > 0 ? (
                    <div className="mt-auto border-t border-line-faint pt-5">
                      <p className="flex items-center gap-1.5 text-micro font-semibold tracking-[0.12em] text-ink-subtle uppercase">
                        <TargetIcon size={13} />
                        Suggested queries
                      </p>
                      <ul className="mt-3 flex flex-col gap-2">
                        {scenario.suggested_queries.map((query) => (
                          <li
                            key={query}
                            className="flex items-start gap-2 text-small text-ink-muted"
                          >
                            <ArrowUpRightIcon
                              size={14}
                              className="mt-0.5 shrink-0 text-brand-500"
                            />
                            <span className="measure">{query}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </article>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  )
}