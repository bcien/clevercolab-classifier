@AGENTS.md

# Frontend — Clevercolab Classifier

## Overview
Next.js 16 + React 19 single-page app for uploading logistics PDFs, tracking processing progress, and reviewing classified results. Talks to the FastAPI backend (local dev on `localhost:8000`, production via Lambda Function URLs).

## Stack
- **Next.js 16.2.2** (App Router, `"use client"` components)
- **React 19.2** with `use()` for unwrapping async params
- **Tailwind CSS v4** (`@tailwindcss/postcss`, no `tailwind.config.js`)
- **shadcn/ui v4** (components in `src/components/ui/`)
- **TypeScript 5**, ESLint 9

## Commands
```bash
npm run dev      # Start dev server on localhost:3000
npm run build    # Production build
npm run lint     # ESLint
```

## Project structure
```
src/
  app/
    layout.tsx              # Root layout (Geist font, lang="es")
    page.tsx                # Upload page (DropZone + FileList)
    jobs/[id]/page.tsx      # Job results page (progress → report)
  components/
    ui/                     # shadcn/ui primitives (do not edit manually)
    upload/
      DropZone.tsx          # Drag-and-drop PDF upload area
      FileList.tsx          # Selected files list with remove
    processing/
      ProgressTracker.tsx   # Step-by-step pipeline progress indicator
    report/
      ReportSummary.tsx     # 4-card summary (files, docs, alerts, missing)
      DocumentTable.tsx     # Classified documents table with extracted data
      AlertList.tsx         # Consistency and validation alerts
      MissingDocs.tsx       # Missing required document badges
    download/
      DownloadButton.tsx    # ZIP download link
  hooks/
    useFileUpload.ts        # Upload API call with loading/error state
    useJobProgress.ts       # Polls backend every 2s until complete/failed
  lib/
    api.ts                  # fetch wrappers for backend endpoints
    types.ts                # TypeScript types mirroring backend Pydantic models
    utils.ts                # cn() helper for Tailwind class merging
```

## Key patterns
- **All components are client components** (`"use client"`) — no RSC data fetching yet
- **Polling, not WebSocket**: `useJobProgress` polls `GET /api/jobs/{id}` every 2 seconds
- **API base URL**: `NEXT_PUBLIC_API_URL` env var, defaults to `http://localhost:8000`
- **Spanish UI**: all user-facing labels are in Spanish
- **DOC_TYPE_LABELS** in `types.ts`: maps backend enum values to Spanish labels. Must stay in sync with `backend/app/models/document.py` `DOCUMENT_LABELS`
- **PIPELINE_STAGES** in `types.ts`: ordered list of stages for the progress tracker. Must match the pipeline execution order in `backend/app/services/pipeline.py`

## Backend API contract
```
POST /api/upload          → { job_id: string }
GET  /api/jobs/{id}       → JobStatus (stage, progress, report when complete)
GET  /api/jobs/{id}/download  → ZIP file
GET  /api/jobs/{id}/files     → { files: [{ name, size }] }
```

## Conventions
- Components receive typed props interfaces, no `any`
- shadcn/ui components in `components/ui/` are generated — modify with `npx shadcn` not by hand
- Keep types in `lib/types.ts` aligned with backend `models/schemas.py`

## Git
- Don't mention claude models as co-author in commit messages — the repository already considers it for all commits.