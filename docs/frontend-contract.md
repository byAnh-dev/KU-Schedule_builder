# Frontend Contract (Source of Truth)

## Scope inspected
- `front-end/src/App.js` (mounted entry via `front-end/src/index.js`)
- `front-end/src/components/CourseSearchBar.js`
- `front-end/src/components/CourseSummary.js`
- `front-end/src/components/ScheduleTable.js`
- `front-end/src/CourseScheduler.js` (present but not mounted)

## Important repo findings
- `docs/product-context.md` was not found in this workspace.
- Requested frontend paths `app/`, `store/`, `lib/data/`, and `lib/schedule/` were not found.
- Actual active frontend is under `front-end/src`.

## Runtime flow (active UI)
1. User types in `CourseSearchBar`.
2. If query length >= 2, frontend calls `GET http://127.0.0.1:5000/search` with `query` as query param (300ms debounce).
3. Selecting a suggestion pushes that suggestion object directly into `selectedCourses` (no detail fetch in active path).
4. `CourseSummary` renders selected course fields.
5. `ScheduleTable` supports drag/drop scheduling in local state only; no backend call is made for schedule placement.

## API contract required by active UI

### 1) Search courses
- Method: `GET`
- URL: `http://127.0.0.1:5000/search`
- Query params:
  - `query` (string, required by behavior)
- Response: JSON array of course objects.

### Course object shape consumed by active UI
- Required:
  - `courseCode: string` (unique key, display, duplicate check)
  - `courseName: string` (display)
- Expected/used (should be provided to avoid blank/undefined UI):
  - `seatAvailable: string | number` (displayed as-is)
- Optional with fallback:
  - `professor?: string` (fallback: `"Unknown"`)
  - `prerequisite?: string` (fallback: `"None"`)
- Optional for schedule drag/drop payload continuity:
  - `sections?: Array|Object` (not currently rendered in active search/summary flow)

## Local state contracts (frontend internal)

### selectedCourses
- Type: `Array<Course>`
- Duplicate rule: reject if `courseCode` already exists.

### schedule
- Type:
```ts
type Schedule = {
  [day: number]: {
    [timeSlot: number]: Array<{
      course: Course;
      section: {
        SectionType?: string;
        [k: string]: unknown;
      };
    }>;
  };
};
```
- Day indices are numeric (`1..5`) in the active schedule grid.
- `moveCourse` currently overwrites a slot with a single-item array.

## Non-mounted/legacy frontend path
- `front-end/src/CourseScheduler.js` defines additional contracts:
  - `GET /search?query=&semester=&level=`
  - `GET /get_course?courseCode=`
  - `POST /check_conflict` with `{ courses: string[] }`
- This file is not mounted by `index.js`; treat it as legacy or future path, not current MVP source of truth.
