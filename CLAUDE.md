# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KU Schedule Builder is a course schedule builder for students. Users search for courses, select lecture/lab sections, drag them onto a weekly grid, block unwanted times, and detect conflicts — all client-side.

## Commands

### Frontend (`frontend/`)
```bash
npm install          # install dependencies
npm run dev          # start dev server at http://localhost:3000
npm run build        # production build
npm run lint         # TypeScript type-check (tsc --noEmit)
npm run clean        # remove dist/
```

### Backend (`backend/`)
```bash
python backend/app.py              # run Flask dev server (debug mode)
flask --app backend/app run        # alternative Flask CLI start
```
No package.json scripts exist for the backend — run Python directly. The backend requires Flask and flask-cors installed in the active Python environment.

## Architecture

### Frontend

**Entry:** `frontend/src/main.tsx` → `frontend/src/App.tsx`

**State:** Zustand store at `frontend/src/store/useScheduleStore.ts`, persisted to localStorage under key `schedule-storage`. Contains: selected courses, active semester, lecture/lab section selections, blocked times per semester, and blocking mode flag. Derived selectors `useScheduledMeetings` and `useConflicts` are exported from the same file — all conflict detection logic lives here, not in the backend.

**Data adapter:** `frontend/src/lib/data.ts` exports three async functions:
- `listSemesters()` — returns available semesters
- `searchCourses({ semesterId, query })` — filters by normalized course ID substring
- `getCourseById({ semesterId, courseId })` — fetches a single course

Currently these functions use hardcoded mock data. The backend's job is to replace them while keeping the same function signatures.

**Schedule logic:** `frontend/src/lib/schedule.ts` — grid constants (`START_HOUR=8`, `END_HOUR=20`, `MIN_PER_CELL=30`), `timeToMinutes`, conflict overlap check, and `getBestSection` scoring algorithm used when dragging sections onto the grid.

**Components:**
- `SearchPanel` — debounced search input, calls `searchCourses`, allows quick-add
- `SelectedCoursesPanel` — shows selected courses with LEC/LAB section pickers
- `Grid` — weekly time grid, renders `ScheduledMeeting` blocks, accepts drag drops
- `BlockTool` — creates/removes `BlockedTime` entries for the active semester
- `ConflictPanel` — displays conflict list derived from `useConflicts`

**Drag-and-drop:** `@dnd-kit/core`. Dragging a LEC or LAB chip from `SelectedCoursesPanel` onto a grid slot triggers `getBestSection` scoring to auto-select the best matching section.

**Types:** `frontend/src/lib/types.ts` — canonical domain types: `Course`, `CourseComponent`, `Meeting`, `DayOfWeek`, `ScheduledMeeting`, `BlockedTime`, `Conflict`. `DayOfWeek` = `"M" | "T" | "W" | "Th" | "F" | "Sa" | "Su"` — **"T" and "Th" are distinct and must never be conflated.**

### Backend

**Entry:** `backend/app.py` → factory `backend/src/server.py:create_app()` → registers routes + error handlers.

**Routes:** `backend/src/routes.py` — Flask Blueprint `api`. Current routes:
- `GET /health` → `{"data": {"status": "ok"}}`
- `GET /api/v1/courses/search` → not yet implemented (raises `NotImplementedErrorApi`)
- `GET /search` → alias for the above

**Error handling:** `backend/src/shared/errors.py` — `ApiError` base class, `ValidationError` (400), `NotImplementedErrorApi` (501). All errors are serialized as `{"error": {"code", "message", "details"?, "requestId"?}}`.

**DTOs:** `backend/src/shared/dtos.py` — `CourseSearchItemDTO`, `SuccessResponseDTO`, `ErrorResponseDTO`.

**Request IDs:** Every request gets a `g.request_id` (from `X-Request-Id` header or generated), echoed back in `X-Request-Id` response header.

**Normalization utilities:** `backend/src/shared/normalize.py` and `backend/utils/` — course code normalization (trim, collapse whitespace, uppercase subject).

### Data

`backend/courseDatabase.json` and `backend/normalized_courseDatabase.json` are the raw course data sources. `backend/normalize.py` is a standalone script that produces the normalized version.

## Key Domain Rules

- Conflict = any overlap >= 1 minute on the same day (`start1 < end2 && start2 < end1`)
- Blocked time is a **soft constraint** — shown in conflicts panel but does not prevent section selection
- Search matches by normalized course ID only (whitespace-collapsed, case-insensitive)
- Semester filter is required for all searches
- Switching the active semester clears all selected courses (after user confirmation)
- A course may have multiple LEC sections; labs are optional and can pair with any lecture
- Course ID format: `"SUBJECT NUMBER"` (e.g., `"EECS 388"`)
- Times are stored as `"HH:MM"` 24-hour strings; minutes-since-midnight used internally for math

## Working Rules (from AGENTS.md)

- Frontend and `docs/product-context.md` are the source of truth — do not invent product behavior
- MVP has no auth; uses localStorage for persistence
- Do not move schedule/conflict logic to the backend unless explicitly asked
- Preserve the `listSemesters / searchCourses / getCourseById` adapter contract when replacing mock data
- Do not add new production dependencies without approval
- Before editing: list files to change and assumptions. After editing: summarize what changed, how verified, and remaining risks
