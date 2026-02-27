# Backend Discovery for MVP

## Basis
- Frontend behavior is the source of truth.
- Active UI is `front-end/src/App.js` + `components/*`.
- MVP constraint: no auth.

## What backend is minimally required

### Required endpoint for current active UI
1. `GET /search`
- Purpose: autocomplete suggestions.
- Query:
  - `query: string` (minimum 2 chars enforced by frontend before calling)
- Response: `CourseSearchItem[]`
- No auth headers/tokens.

### `CourseSearchItem` minimum payload
```json
{
  "courseCode": "EECS 140",
  "courseName": "Programming I",
  "seatAvailable": "12",
  "professor": "Jane Doe",
  "prerequisite": "None"
}
```
- Hard-required by active behavior: `courseCode`, `courseName`.
- Strongly recommended for UI completeness: `seatAvailable`, `professor`, `prerequisite`.

## What is currently extra (not needed for current MVP UI)
- `GET /get_course`
- `POST /check_conflict`
- `POST /generate_schedule_combinations`

These are referenced by `front-end/src/CourseScheduler.js`, which is not mounted.

## Proposed shared backend conventions

### Route names
- Use versioned API namespace:
  - `GET /api/v1/courses/search`
  - `GET /api/v1/courses/:courseCode` (future)
  - `POST /api/v1/schedules/conflicts` (future)
  - `POST /api/v1/schedules/combinations` (future)
- Keep temporary compatibility alias during migration:
  - `/search` -> same handler as `/api/v1/courses/search`

### Request/response shapes

#### `GET /api/v1/courses/search`
- Query:
  - `query: string` (required)
  - `limit?: number` (default 10, max 25)
  - `semester?: string` (optional filter)
  - `level?: "undergrad" | "grad"` (optional filter)
- Success response:
```json
{
  "data": [
    {
      "courseCode": "EECS 140",
      "courseName": "Programming I",
      "seatAvailable": "12",
      "professor": "Jane Doe",
      "prerequisite": "None"
    }
  ],
  "meta": {
    "query": "eecs",
    "count": 1
  }
}
```

#### Future detail response (for mounted legacy path parity)
```json
{
  "data": {
    "courseCode": "EECS 140",
    "courseName": "Programming I",
    "creditHours": 4,
    "sections": [
      {
        "sectionId": "12345",
        "sectionType": "LEC",
        "instructor": "Jane Doe",
        "meetingTime": "MWF 09:00 - 09:50 AM",
        "location": "EATON 1001"
      }
    ]
  }
}
```

### Normalization rules
- Canonical casing:
  - API output uses camelCase.
  - Internally allow source keys like `CourseCode`, `CourseName`, `Sections`.
- Course code normalization:
  - trim, collapse whitespace, uppercase subject, preserve catalog number suffix.
  - Example: `"eecs   140 "` -> `"EECS 140"`.
- Seat normalization:
  - keep raw display string for UI (`"Full"`, `"12"`), plus optional numeric `seatCount` when parseable.
- Nullability:
  - convert `"N/A"` and empty strings to `null` internally.
  - map to UI-safe defaults in serializer (`professor: null` allowed; frontend fallback handles it).
- Meeting time normalization:
  - preserve raw source string in `meetingTimeRaw`.
  - optional parsed structure for conflict logic:
    - `days: string[]`, `startMinutes: number`, `endMinutes: number`.

### Error format
- Standard JSON error envelope:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "query is required",
    "details": [
      { "field": "query", "issue": "missing" }
    ],
    "requestId": "req_abc123"
  }
}
```
- HTTP mapping:
  - `400` validation
  - `404` not found
  - `409` scheduling conflict
  - `500` unexpected server error

### Shared utility files (recommended)
- `backend/utils/normalizeCourse.ts|py`
  - key mapping, code normalization, `N/A` to `null`.
- `backend/utils/serializeCourse.ts|py`
  - transform DB model -> API DTO.
- `backend/utils/parseMeetingTime.ts|py`
  - parse day/time ranges to normalized slots.
- `backend/utils/error.ts|py`
  - typed error classes + error envelope formatter.
- `backend/utils/validators.ts|py`
  - query/body validators for all routes.

## Gaps discovered in current backend vs active UI
- `backend/app.py` mixes list/dict assumptions for `database` (runtime bug risk).
- Active UI expects `seatAvailable`/`professor` in search items; current `/search` does not provide these consistently.
- Active UI uses fixed absolute host `http://127.0.0.1:5000`; environment-based base URL should be adopted later.
