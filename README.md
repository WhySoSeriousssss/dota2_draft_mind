# Dota 2 Draft Mind

FastAPI backend and native HTML/CSS/JavaScript frontend for ranked draft recommendations.

## Setup

```bash
python3 -m pip install -e ".[dev]"
```

## Run

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000`. Interactive API documentation is available at
`http://127.0.0.1:8000/api/docs`.

## API

- `GET /api/v1/config`
- `POST /api/v1/recommend`
- `GET /api/v1/healthz`

The recommendation request already accepts `excluded_hero_ids`; the frontend can
later populate it from local storage or a registered user's cloud preferences.

## Configuration

- `DRAFT_DATABASE_PATH`
- `DRAFT_HEROES_PATH`
- `DRAFT_FRONTEND_PATH`
