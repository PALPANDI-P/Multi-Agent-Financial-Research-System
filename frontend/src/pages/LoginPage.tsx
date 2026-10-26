import { useMemo, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError, describeError } from '../api/client'
import type { AuthScenario } from '../api/types'
import { Alert, Badge, Brand, Button, Card, CardBody, Input, PublicHeader } from '../components'
import { CheckIcon, ChevronDownIcon, LockIcon, TargetIcon } from '../components/icons'
import { useAuth } from '../hooks/useAuth'
import { useScenarios } from '../hooks/useScenarios'
import { cn } from '../lib/cn'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface LoginLocationState {
  from?: string
}

interface FieldErrors {
  email?: string
  password?: string
}

interface RegisterFieldErrors {
  email?: string
  fullName?: string
  password?: string
}

interface Failure {
  title: string
  message: string
  code: string
}

/** Turns a failed sign-in into a message the visitor can act on. */
function describeLoginFailure(error: unknown): Failure {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return {
        title: 'The sign-in was rejected',
        message: error.message || 'Invalid email or password',
        code: error.code,
      }
    }
    return { title: 'The sign-in failed', message: error.message, code: error.code }
  }
  const described = describeError(error)
  return { title: 'The sign-in failed', message: described.message, code: described.code }
}

/** Turns a failed registration into a message the visitor can act on. */
function describeRegisterFailure(error: unknown): Failure {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return {
        title: 'Registration is disabled',
        message:
          'This deployment does not accept new accounts. Ask an administrator for credentials.',
        code: error.code,
      }
    }
    if (error.status === 409) {
      return {
        title: 'That email address is already registered',
        message: 'Sign in with that address instead, or register with a different one.',
        code: error.code,
      }
    }
    if (error.status === 422) {
      return {
        title: 'The account could not be created',
        message: error.message,
        code: error.code,
      }
    }
    return { title: 'The account could not be created', message: error.message, code: error.code }
  }
  const described = describeError(error)
  return { title: 'The account could not be created', message: described.message, code: described.code }
}

/**
 * The sign-in page.
 *
 * The page is built around the analyst scenarios of the product: a scenario
 * selects the persona, pre-fills the email address and shows the questions
 * the persona is likely to ask.  The scenario copy itself is served by the
 * API, it is never hard coded here.
 *
 * Layout: the heading owns the top of the page, so the reading order stays
 * the same on a phone and on a wide screen.  Below it the page splits into
 * the scenarios (left) and the form (right); on a phone the form comes
 * first, because it is the thing the visitor came for.
 */
export function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { login, register, refresh } = useAuth()
  const scenariosQuery = useScenarios()
  const scenarios = useMemo(() => scenariosQuery.data ?? [], [scenariosQuery.data])

  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [failure, setFailure] = useState<Failure | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [isRegisterOpen, setIsRegisterOpen] = useState(location.pathname === '/register')
  const [registerName, setRegisterName] = useState('')
  const [registerEmail, setRegisterEmail] = useState('')
  const [registerPassword, setRegisterPassword] = useState('')
  const [registerErrors, setRegisterErrors] = useState<RegisterFieldErrors>({})
  const [registerFailure, setRegisterFailure] = useState<Failure | null>(null)
  const [registerNotice, setRegisterNotice] = useState<string | null>(null)
  const [isRegistering, setIsRegistering] = useState(false)

  const emailRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const registerNameRef = useRef<HTMLInputElement>(null)
  const registerEmailRef = useRef<HTMLInputElement>(null)
  const registerPasswordRef = useRef<HTMLInputElement>(null)

  const destination = (location.state as LoginLocationState | null)?.from ?? '/app'

  const selectedScenario = useMemo<AuthScenario | null>(
    () => scenarios.find((scenario) => scenario.key === selectedKey) ?? null,
    [scenarios, selectedKey],
  )

  const scenariosError = scenariosQuery.error ? describeError(scenariosQuery.error) : null

  const handleSelectScenario = (scenario: AuthScenario) => {
    setSelectedKey(scenario.key)
    setFailure(null)
    setFieldErrors((current) => ({ ...current, email: undefined }))
    if (scenario.demo_email) {
      setEmail(scenario.demo_email)
    }
  }

  const handleFillDemoCredentials = (scenario: AuthScenario) => {
    if (!scenario.demo_email || !scenario.demo_password) return
    setSelectedKey(scenario.key)
    setEmail(scenario.demo_email)
    setPassword(scenario.demo_password)
    setFieldErrors({})
    setFailure(null)
  }

  const handleScenarioKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (scenarios.length === 0) return
    let nextIndex: number | null = null
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      nextIndex = (index + 1) % scenarios.length
    } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
      nextIndex = (index - 1 + scenarios.length) % scenarios.length
    }
    if (nextIndex === null) return
    event.preventDefault()
    const next = scenarios[nextIndex]
    handleSelectScenario(next)
    const group = event.currentTarget.closest('[role="radiogroup"]')
    group?.querySelectorAll<HTMLElement>('[role="radio"]')[nextIndex]?.focus()
  }

  const validateSignIn = (): FieldErrors => {
    const errors: FieldErrors = {}
    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      errors.email = 'Enter the email address of your account.'
    } else if (!EMAIL_PATTERN.test(trimmedEmail)) {
      errors.email = 'Enter a valid email address.'
    }
    if (!password) {
      errors.password = 'Enter your password.'
    }
    return errors
  }

  const handleSignIn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFailure(null)

    const errors = validateSignIn()
    setFieldErrors(errors)
    if (errors.email) {
      emailRef.current?.focus()
      return
    }
    if (errors.password) {
      passwordRef.current?.focus()
      return
    }

    setIsSubmitting(true)
    try {
      await login(email.trim(), password)
      navigate(destination, { replace: true })
    } catch (error) {
      setFailure(describeLoginFailure(error))
      passwordRef.current?.focus()
    } finally {
      setIsSubmitting(false)
    }
  }

  const validateRegistration = (): RegisterFieldErrors => {
    const errors: RegisterFieldErrors = {}
    const trimmedEmail = registerEmail.trim()
    if (!registerName.trim()) {
      errors.fullName = 'Enter your full name.'
    } else if (!trimmedEmail) {
      errors.email = 'Enter an email address.'
    } else if (!EMAIL_PATTERN.test(trimmedEmail)) {
      errors.email = 'Enter a valid email address.'
    }
    if (!registerPassword) {
      errors.password = 'Enter a password.'
    }
    return errors
  }

  const handleRegister = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setRegisterFailure(null)
    setRegisterNotice(null)

    const errors = validateRegistration()
    setRegisterErrors(errors)
    if (errors.fullName) {
      registerNameRef.current?.focus()
      return
    }
    if (errors.email) {
      registerEmailRef.current?.focus()
      return
    }
    if (errors.password) {
      registerPasswordRef.current?.focus()
      return
    }

    setIsRegistering(true)
    try {
      await register({
        email: registerEmail.trim(),
        full_name: registerName.trim(),
        password: registerPassword,
      })
      const session = await refresh()
      if (session) {
        navigate(destination, { replace: true })
        return
      }
      setRegisterNotice(
        'The account was created. Sign in below with the email address and the password you just chose.',
      )
      setEmail(registerEmail.trim())
      setPassword('')
      setRegisterPassword('')
      passwordRef.current?.focus()
    } catch (caught) {
      setRegisterFailure(describeRegisterFailure(caught))
    } finally {
      setIsRegistering(false)
    }
  }

  const demoScenario =
    selectedScenario && selectedScenario.demo_email && selectedScenario.demo_password
      ? selectedScenario
      : null

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <a className="skip-link" href="#main">
        Skip to the main content
      </a>

      <PublicHeader
        action={
          <Link
            to="/"
            className="inline-flex h-9 items-center rounded-control px-2.5 text-small font-medium text-ink-muted transition-colors duration-150 hover:bg-surface-muted hover:text-ink"
          >
            Product overview
          </Link>
        }
      />

      <main id="main" className="flex flex-1 items-center justify-center px-5 py-12 sm:px-8 sm:py-16">
        <div className="w-full max-w-page">
          {/* The heading owns the top of the page: it comes before the two
              columns on every viewport. */}
          <header className="max-w-2xl">
            <p className="flex items-center gap-2.5 text-micro font-semibold tracking-[0.16em] text-brand-700 uppercase">
              <span aria-hidden="true" className="h-px w-6 bg-brand-300" />
              Research workspace
            </p>
            <h1 className="mt-6 max-w-[17ch] font-display text-display text-balance text-ink">
              Sign in to your research workspace
            </h1>
            <p className="mt-6 max-w-[58ch] text-body leading-relaxed text-ink-muted">
              Upload financial documents, let the ingestion pipeline extract, chunk and embed them,
              then retrieve source-grounded passages with page-level citations. Choose the analyst
              scenario you work in — it sets the focus areas and the questions the workspace
              suggests.
            </p>
          </header>

          <div className="mt-14 grid gap-10 lg:grid-cols-[minmax(0,1fr)_25rem] lg:items-start lg:gap-16">
            {/* The scenarios and the framing of the task. */}
            <section className="order-2 flex flex-col gap-8 lg:order-1">
              <div>
                <h2 id="scenario-heading" className="text-subtitle text-ink">
                  Choose a scenario
                </h2>
                <p className="mt-1.5 max-w-[56ch] text-small text-ink-muted">
                  The scenarios and their demo credentials are served by the API.
                </p>

                {scenariosQuery.isPending ? (
                  <div
                    className="mt-6 grid gap-4 sm:grid-cols-2"
                    role="status"
                    aria-live="polite"
                  >
                    <span className="sr-only">Loading the analyst scenarios…</span>
                    {[0, 1, 2, 3].map((index) => (
                      <div
                        key={index}
                        className="flex flex-col gap-3 rounded-card border border-line bg-surface p-5"
                      >
                        <span className="skeleton h-4 w-2/3" />
                        <span className="skeleton h-3 w-full" />
                        <span className="skeleton h-3 w-1/2" />
                      </div>
                    ))}
                  </div>
                ) : null}

                {scenariosError ? (
                  <div className="mt-6">
                    <Alert
                      tone="warning"
                      title="The scenarios could not be loaded"
                      code={scenariosError.code}
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
                      {scenariosError.message} You can still sign in with your own credentials.
                    </Alert>
                  </div>
                ) : null}

                {scenarios.length > 0 ? (
                  <div
                    role="radiogroup"
                    aria-labelledby="scenario-heading"
                    className="mt-6 flex flex-col gap-4"
                  >
                    {scenarios.map((scenario, index) => {
                      const isSelected = scenario.key === selectedKey
                      return (
                        <li
                          key={scenario.key}
                          className={cn(
                            'group relative overflow-hidden rounded-card border transition-[border-color,background-color,box-shadow,transform] duration-200 ease-out-soft',
                            'focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/55 focus-within:ring-offset-2 focus-within:ring-offset-surface',
                            isSelected
                              ? 'border-brand-400 bg-brand-50 shadow-card'
                              : 'border-line bg-surface hover:-translate-y-0.5 hover:border-line-strong hover:shadow-card',
                          )}
                        >
                          {/* The selected rule: the strongest signal of the
                              group, and the only saturated element. */}
                          <span
                            aria-hidden="true"
                            className={cn(
                              'absolute inset-y-4 left-0 w-[3px] rounded-r-pill transition-opacity duration-200',
                              isSelected ? 'bg-brand-600 opacity-100' : 'opacity-0',
                            )}
                          />

                          <button
                            type="button"
                            role="radio"
                            aria-checked={isSelected}
                            tabIndex={isSelected || (selectedKey === null && index === 0) ? 0 : -1}
                            onClick={() => handleSelectScenario(scenario)}
                            onKeyDown={(event) => handleScenarioKeyDown(event, index)}
                            className="flex w-full flex-col gap-3 p-5 text-left focus-visible:outline-none"
                          >
                            <span className="flex items-start gap-3">
                              <span
                                aria-hidden="true"
                                className={cn(
                                  'mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-pill border transition-colors duration-200',
                                  isSelected
                                    ? 'border-brand-600 bg-brand-600 text-on-accent'
                                    : 'border-line-strong bg-surface text-transparent group-hover:border-brand-300',
                                )}
                              >
                                <CheckIcon size={12} />
                              </span>

                              <span className="min-w-0 flex-1">
                                <span className="flex flex-wrap items-center gap-2">
                                  <span className="text-subtitle text-ink">{scenario.title}</span>
                                  <Badge tone={isSelected ? 'brand' : 'neutral'} title="scenario key">
                                    <span className="font-mono text-micro">{scenario.key}</span>
                                  </Badge>
                                </span>
                                <span className="mt-1.5 block max-w-[46ch] text-small font-medium text-ink-muted">
                                  {scenario.tagline}
                                </span>
                              </span>
                            </span>

                            {scenario.focus_areas.length > 0 ? (
                              <span className="flex flex-wrap gap-1.5 pl-8">
                                {scenario.focus_areas.map((area) => (
                                  <span
                                    key={area}
                                    className="rounded-pill border border-line bg-surface/80 px-2 py-0.5 text-caption text-ink-muted"
                                  >
                                    {area}
                                  </span>
                                ))}
                              </span>
                            ) : null}
                          </button>

                          {/* The demo account is a quiet footnote of the card.
                              It lives outside the radio button, so the card
                              holds no nested control. */}
                          {scenario.demo_email ? (
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line-faint bg-surface/60 px-5 py-2.5">
                              <span className="text-micro font-semibold tracking-[0.1em] text-ink-subtle uppercase">
                                demo
                              </span>
                              <span className="truncate font-mono text-caption text-ink-muted">
                                {scenario.demo_email}
                              </span>
                              {scenario.demo_password ? (
                                <button
                                  type="button"
                                  onClick={() => handleFillDemoCredentials(scenario)}
                                  className="ml-auto rounded-xs text-caption font-medium text-brand-700 transition-colors duration-150 hover:text-brand-600"
                                >
                                  <span className="link-underline">Use demo</span>
                                </button>
                              ) : null}
                            </div>
                          ) : null}
                        </li>
                      )
                    })}
                  </div>
                ) : null}
              </div>
            </section>

            {/* The form column. */}
            <section className="order-1 flex flex-col gap-4 lg:order-2 lg:sticky lg:top-24">
              <Card className="shadow-raised">
                <CardBody className="flex flex-col gap-6">
                  <div>
                    <h2 className="text-subtitle text-ink">Sign in</h2>
                    <p className="mt-2 flex items-start gap-2 text-small text-ink-muted">
                      <LockIcon size={14} className="mt-0.5 shrink-0 text-ink-subtle" />
                      Your session is stored in a secure cookie of the API — nothing is kept in the
                      browser storage.
                    </p>
                  </div>

                  {selectedScenario ? (
                    <p className="flex items-center gap-2.5 rounded-control border border-brand-200 bg-brand-50/70 px-3 py-2 text-caption text-ink-muted">
                      <TargetIcon size={14} className="shrink-0 text-brand-700" />
                      Signing in as{' '}
                      <span className="font-semibold text-ink">{selectedScenario.title}</span>
                    </p>
                  ) : null}

                  <form onSubmit={handleSignIn} noValidate className="flex flex-col gap-4">
                    <Input
                      label="Email address"
                      id="signin-email"
                      type="email"
                      autoComplete="username"
                      inputRef={emailRef}
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      error={fieldErrors.email ?? null}
                      required
                    />
                    <Input
                      label="Password"
                      id="signin-password"
                      type="password"
                      autoComplete="current-password"
                      inputRef={passwordRef}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      error={fieldErrors.password ?? null}
                      required
                    />

                    {failure ? (
                      <Alert tone="danger" title={failure.title} code={failure.code}>
                        {failure.message}
                      </Alert>
                    ) : null}

                    <Button
                      type="submit"
                      loading={isSubmitting}
                      loadingLabel="Signing in…"
                      className="mt-1 w-full"
                      size="lg"
                    >
                      Sign in
                    </Button>
                  </form>

                  {/* The demo credentials are a hint, not a call to action:
                      a quiet line under the form. */}
                  {demoScenario ? (
                    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line-faint pt-4 text-caption text-ink-subtle">
                      <span>Demo account</span>
                      <span className="font-mono text-ink-muted">{demoScenario.demo_email}</span>
                      <button
                        type="button"
                        onClick={() => handleFillDemoCredentials(demoScenario)}
                        className="ml-auto rounded-xs font-medium text-brand-700 transition-colors duration-150 hover:text-brand-600"
                      >
                        <span className="link-underline">Fill the credentials</span>
                      </button>
                    </p>
                  ) : null}

                  {selectedScenario && selectedScenario.suggested_queries.length > 0 ? (
                    <div className="border-t border-line pt-5">
                      <p className="flex items-center gap-1.5 text-micro font-semibold tracking-[0.12em] text-ink-subtle uppercase">
                        <TargetIcon size={13} />
                        Questions this scenario asks
                      </p>
                      <ul className="mt-3 flex flex-col gap-2">
                        {selectedScenario.suggested_queries.map((query) => (
                          <li
                            key={query}
                            className="flex items-start gap-2 text-caption text-ink-muted"
                          >
                            <span
                              aria-hidden="true"
                              className="mt-[7px] h-px w-3 shrink-0 bg-line-strong"
                            />
                            <span className="measure">{query}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </CardBody>
              </Card>

              {/* The registration is a quiet disclosure under the form, not a
                  second card competing with it. */}
              <section className="overflow-hidden rounded-card border border-line bg-surface-muted/40">
                <div className="px-5 py-4">
                  <button
                    type="button"
                    aria-expanded={isRegisterOpen}
                    aria-controls="register-panel"
                    onClick={() => setIsRegisterOpen((open) => !open)}
                    className="flex w-full items-center justify-between gap-3 text-left"
                  >
                    <span>
                      <span className="block text-small font-semibold text-ink">
                        Create an account
                      </span>
                      <span className="mt-0.5 block text-caption text-ink-muted">
                        {isRegisterOpen
                          ? 'Hide the registration form'
                          : 'Register with an email address, a name and a password'}
                      </span>
                    </span>
                    <ChevronDownIcon
                      size={18}
                      className={cn(
                        'shrink-0 text-ink-subtle transition-transform duration-200',
                        isRegisterOpen && 'rotate-180',
                      )}
                    />
                  </button>
                </div>

                {isRegisterOpen ? (
                  <div
                    id="register-panel"
                    className="flex flex-col gap-4 border-t border-line bg-surface px-5 py-5"
                  >
                    {registerFailure ? (
                      <Alert tone="danger" title={registerFailure.title} code={registerFailure.code}>
                        {registerFailure.message}
                      </Alert>
                    ) : null}

                    {registerNotice ? (
                      <Alert tone="success" title="The account was created">
                        {registerNotice}
                      </Alert>
                    ) : null}

                    <form onSubmit={handleRegister} noValidate className="flex flex-col gap-4">
                      <Input
                        label="Full name"
                        id="register-full-name"
                        type="text"
                        autoComplete="name"
                        inputRef={registerNameRef}
                        value={registerName}
                        onChange={(event) => setRegisterName(event.target.value)}
                        error={registerErrors.fullName ?? null}
                        required
                      />
                      <Input
                        label="Email address"
                        id="register-email"
                        type="email"
                        autoComplete="email"
                        inputRef={registerEmailRef}
                        value={registerEmail}
                        onChange={(event) => setRegisterEmail(event.target.value)}
                        error={registerErrors.email ?? null}
                        required
                      />
                      <Input
                        label="Password"
                        id="register-password"
                        type="password"
                        autoComplete="new-password"
                        inputRef={registerPasswordRef}
                        value={registerPassword}
                        onChange={(event) => setRegisterPassword(event.target.value)}
                        error={registerErrors.password ?? null}
                        required
                      />
                      <Button
                        type="submit"
                        variant="secondary"
                        loading={isRegistering}
                        loadingLabel="Creating the account…"
                        className="w-full"
                      >
                        Create the account
                      </Button>
                    </form>
                  </div>
                ) : null}
              </section>
            </section>
          </div>
        </div>
      </main>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto w-full max-w-page px-5 py-5 sm:px-8">
          <Brand compact />
        </div>
      </footer>
    </div>
  )
}