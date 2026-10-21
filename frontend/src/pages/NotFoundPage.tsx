import { Link } from 'react-router-dom'
import { Button, Card, CardBody } from '../components'

export function NotFoundPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-16 sm:px-6">
      <Card>
        <CardBody className="flex flex-col items-start gap-3">
          <p className="font-mono text-sm text-ink-subtle">404</p>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Page not found</h1>
          <p className="text-sm text-ink-muted">
            The page you requested does not exist in this application.
          </p>
          <Link to="/">
            <Button>Back to all workspaces</Button>
          </Link>
        </CardBody>
      </Card>
    </div>
  )
}
