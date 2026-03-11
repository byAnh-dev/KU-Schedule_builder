# KU Schedule Builder

A course schedule builder for University of Kansas students. Search for courses, pick lecture and lab sections, drag them onto a weekly grid, block off busy times, and instantly see any time conflicts — all in your browser.

**Live site:** [ku-schedule-builder.vercel.app](https://ku-schedule-builder.vercel.app) *(update with your actual URL)*

---

## What it does

- **Search courses** by subject and number (e.g. `EECS 388`, `MATH 116`)
- **Pick sections** — choose which lecture and lab section you want
- **Drag onto the grid** — drop a course chip onto the weekly calendar; it auto-picks the best matching section
- **Block times** — mark times you can't attend (soft constraint; flagged in conflicts panel)
- **Conflict detection** — any overlapping meetings are highlighted instantly
- **Export to calendar** — download a `.ics` file to import into Google Calendar, Outlook, etc.
- **Persists across sessions** — your schedule is saved in your browser's localStorage

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Tailwind CSS, Vite |
| State | Zustand (persisted to localStorage) |
| Drag & drop | @dnd-kit/core |
| Backend | Python, Flask |
| Data | JSON course catalog (multi-semester) |
| Hosting | Vercel (frontend), any Python host (backend) |

---

## Prerequisites

Make sure you have these installed before starting:

- **Node.js** v18 or later — [nodejs.org](https://nodejs.org)
- **npm** v9 or later (comes with Node)
- **Python** 3.10 or later — [python.org](https://www.python.org)
- **pip** (comes with Python)

You can verify your versions:

```bash
node --version    # should be v18+
python --version  # should be 3.10+
```

---

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/byAnh-dev/KU-Schedule_builder.git
cd KU-Schedule_builder
```

### 2. Set up the backend

```bash
cd backend

# Create a Python virtual environment (keeps dependencies isolated)
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the backend server
python app.py
```

The backend runs at `http://localhost:5000`. You should see:
```
* Running on http://0.0.0.0:5000
```

### 3. Set up the frontend

Open a **new terminal** (keep the backend running in the first one):

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The frontend runs at `http://localhost:3000`. Open that URL in your browser.

---

## Project structure

```
KU-Schedule_builder/
├── frontend/                  # React app (what users see)
│   ├── src/
│   │   ├── App.tsx            # Root component, layout
│   │   ├── components/        # UI components
│   │   │   ├── SearchPanel    # Course search input
│   │   │   ├── SelectedCoursesPanel  # Picked courses + section pickers
│   │   │   ├── Grid           # Weekly calendar grid
│   │   │   ├── BlockTool      # Block-off-time tool
│   │   │   └── ConflictPanel  # Conflict list
│   │   ├── store/
│   │   │   └── useScheduleStore.ts  # All app state (Zustand)
│   │   └── lib/
│   │       ├── data.ts        # API calls to the backend
│   │       ├── schedule.ts    # Grid math, conflict logic, section scoring
│   │       ├── types.ts       # TypeScript types
│   │       └── ics.ts         # Calendar export
│   └── package.json
│
├── backend/                   # Flask API
│   ├── app.py                 # Entry point
│   ├── src/
│   │   ├── server.py          # Flask app factory
│   │   ├── routes.py          # API route handlers
│   │   ├── catalog/           # Course data loading + scraping
│   │   └── shared/            # Error types, DTOs, normalization
│   ├── courseDatabase.json           # Raw course catalog
│   └── normalized_courseDatabase.json  # Pre-processed catalog
│
└── .gitignore
```

---

## API overview

The backend exposes a simple REST API:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/semesters` | List available semesters |
| GET | `/api/v1/courses/search?semesterId=&query=` | Search courses |
| GET | `/api/v1/courses/:courseId?semesterId=` | Get a single course |

All responses follow this shape:
```json
{ "data": { ... } }
```
Errors return:
```json
{ "error": { "code": "...", "message": "..." } }
```

---

## Environment variables

The frontend reads one optional env variable. Create a `frontend/.env.local` file if you need to change the backend URL:

```bash
# frontend/.env.local
VITE_API_BASE=http://localhost:5000
```

If not set, it defaults to `http://localhost:5000` for local run. On deploy it will be the URL to the backend server. 

---

## Common issues

**Backend import error on start:**
Make sure your virtual environment is activated (`source venv/bin/activate`) and you ran `pip install flask flask-cors`.

**Frontend can't reach the backend (network error in browser console):**
Check that the backend is running at port 5000. Make sure both terminals are open.

**Courses not loading / empty search results:**
The backend serves courses from `backend/courseDatabase.json`. Make sure that file exists and is not empty.

**Port already in use:**
If port 3000 or 5000 is taken, stop the other process or change the port:
```bash
# Frontend on a different port
npm run dev -- --port 3001

# Backend on a different port (then update VITE_API_BASE)
flask --app backend/app run --port 5001
```

---

## Contributing

Pull requests are welcome. For large changes, open an issue first to discuss what you'd like to change.

```bash
# Run TypeScript type-check before submitting
cd frontend && npm run lint
```

**Key domain rules to know:**
- `"T"` = Tuesday, `"Th"` = Thursday — these are distinct and must never be conflated
- Conflict = any overlap >= 1 minute on the same day
- Blocked times are soft constraints (flagged, not enforced)
- Semester filter is required for all course searches

---

## Reporting bugs

Open an issue on GitHub or email the maintainer from the footer of the app.

