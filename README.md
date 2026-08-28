# Dota 2 Draft Mind

FastAPI backend and React + TypeScript frontend for ranked draft recommendations.

Production VPS deployment, Nginx, systemd, HTTPS, updates, rollback, and
troubleshooting are documented in [DEPLOYMENT.md](DEPLOYMENT.md).

## Setup

```bash
python3 -m pip install -e ".[dev]"
cd frontend
npm install
npm run build
```

## Run

Start the API and Vite development servers in separate terminals:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend && npm run dev
```

Open `http://127.0.0.1:5173` during development. Vite proxies `/api` requests to
FastAPI on port 8000.

For a production-style local run, build the frontend and let FastAPI serve it:

```bash
cd frontend && npm run build
cd ..
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Interactive API documentation is available at
`http://127.0.0.1:8000/api/docs`.

## API

- `GET /api/v1/config`
- `POST /api/v1/recommend`
- `GET /api/v1/leaderboard`
- `GET /api/v1/healthz`

The recommendation request already accepts `excluded_hero_ids`; the frontend can
later populate it from local storage or a registered user's cloud preferences.

`position_ids` filters recommendation candidates by common position. An empty
array means all heroes, and multiple IDs use the union of their hero pools:

- `0`: Carry
- `1`: Mid
- `2`: Offlane
- `3`: Support

`hero_proficiencies` maps hero IDs to `-1` (不会), `0` (还行), or `1` (绝活).
The frontend stores non-default values in browser local storage. Draft Score V1
adds `delta * proficiency` to the existing base, counter, and synergy score.

## Configuration

- `DRAFT_DATABASE_PATH`
- `DRAFT_HEROES_PATH`
- `DRAFT_HERO_POSITIONS_PATH`
- `DRAFT_FRONTEND_PATH`

`DRAFT_FRONTEND_PATH` points to the Vite build directory and defaults to
`frontend/dist`.

## Position Debug Tool

Run the local-only position editor after changing hero position definitions:

```bash
python tools/position_editor/app.py
```

Open `http://127.0.0.1:8010`. Saving validates full hero coverage, writes the
JSON atomically, and creates a timestamped backup under `metadata/backups/`.
