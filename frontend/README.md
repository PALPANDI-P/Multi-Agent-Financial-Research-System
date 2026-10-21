# Research Workspace — frontend

React + TypeScript + Vite frontend for the Multi-Agent Financial Research System.
It is a working research tool, not a landing page: every number, name, status and
passage rendered by the UI is read from the backend API.

## Stack

- Vite 8 + React 19 + TypeScript
- Tailwind CSS v4 (`@tailwindcss/vite` plugin, single `@import "tailwindcss";` entry)
- TanStack Query for server state (loading / error / refetch / invalidation)
- react-router-dom 7 (`/` → dashboard, `/workspaces/:id` → detail)
- ESLint 10 flat config with `typescript-eslint`, `react-hooks` and `react-refresh`

## Getting started

```bash
npm install
cp .env.example .env      # optional
npm run dev               # http://localhost:5173
```

| Script              | Description                                  |
| ------------------- | -------------------------------------------- |
| `npm run dev`       | Vite dev server on port 5173                 |
| `npm run build`     | `tsc -b && vite build` (type-checks, then bundles) |
| `npm run typecheck` | `tsc --noEmit`                               |
| `npm run lint`      | `eslint .`                                   |
| `npm run preview`   | Serve the production build on port 4173      |

## API configuration

`VITE_API_BASE_URL` (see `.env.example`) selects the API root.
Default: `http://localhost:8000/api/v1`.

The dev server also proxies `/api` → `http://localhost:8000`
(override with `VITE_DEV_PROXY_TARGET`). Set `VITE_API_BASE_URL=/api/v1` to route
browser traffic through that proxy and avoid CORS entirely during development.

## Screens

- **Dashboard** (`src/pages/DashboardPage.tsx`) — workspace list with name, description,
  document count and timestamps, a debounced name filter, create-workspace dialog and
  pagination. Loading, empty, error and success states are all rendered.
- **Workspace detail** (`src/pages/WorkspaceDetailPage.tsx`) — workspace header, in-workspace
  search, upload panel and the document list (company, title, type, fiscal period, filename,
  size, pages, processing status + stage, chunk count, error code/message, timestamps),
  plus retry, remove, rename and delete actions.
- **Search** (`src/features/search/`) — query box with chunk-type and result-count filters;
  each hit shows document title, company, page range, section heading, chunk type, relevance
  score, passage text and source metadata, plus the result count and the elapsed time.

## Structure

```
src/
  api/         typed fetch client, error envelope handling, multipart upload with progress
  components/  Button, Input, Textarea, Select, Badge, Card, Spinner, Alert, EmptyState,
               Modal, Dropzone, Table, Pagination
  features/    workspaces/, documents/, search/
  hooks/       TanStack Query hooks
  lib/         cn.ts (class joiner), format.ts (bytes, dates, scores, durations)
  pages/       DashboardPage, WorkspaceDetailPage, NotFoundPage
  routes/      router definition and app layout
```

## Design tokens

The palette, fonts and radii are declared as CSS custom properties in the `@theme` block of
`src/index.css`; every component consumes them through Tailwind utilities such as
`bg-surface`, `text-ink-muted`, `border-line` and `rounded-card`.