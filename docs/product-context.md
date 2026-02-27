# Product Context

## Product Goal
This product is a course schedule builder for students.

Users can:
- search courses by course ID, filtered by semester
- quick-add courses to a selected list
- choose lecture sections and optionally lab sections
- drag courses or sections to a weekly grid
- auto-select the best section pattern based on drop location
- block unwanted time as a soft constraint
- detect and visualize schedule conflicts

## Frontend Stack
- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- lucide-react
- @dnd-kit/core
- @dnd-kit/sortable

## Current Persistence
- single-user local state
- localStorage
- hydration-safe client-side handling
- no backend persistence yet

## MVP Scope
MVP does NOT include:
- authentication
- multi-user support
- cross-device sync
- backend-driven scheduling logic

MVP DOES include:
- semester-based course search
- selected course management
- lecture selection
- optional lab selection
- weekly grid rendering
- blocked time support
- conflict detection and visualization
- local save/load via localStorage

## Important Domain Rules
- Search matches by normalized course ID only
- Semester filter is required
- A course may have multiple lecture sections and multiple lab sections
- Labs are optional for some courses
- Labs can pair with any lecture
- Conflict exists if overlap is >= 1 minute on the same day
- "T" and "Th" must be handled distinctly
- Blocked time is a soft constraint, not a hard blocker
- Semester switch clears current selection after confirmation

## Frontend Source of Truth
The frontend currently assumes adapter-style functions:
- listSemesters()
- searchCourses({ semesterId, query })
- getCourseById({ semesterId, courseId })

These should be preserved when replacing the mock adapter.

## Backend Goal
The first backend version should minimally support replacing the mock adapter with a real data source while preserving the current frontend contract.

## Open Product Decision
Decide whether backend scope is:
1. read-only course catalog API only, or
2. course catalog API plus persistence of user schedules