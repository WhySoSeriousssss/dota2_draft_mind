# Project Structure

```text
dota2_draft_mind/
├── algorithms/
│   ├── v1/                 # Pair-statistics scorer
│   └── v2/                 # LightGBM features, training, and inference
├── backend/                # FastAPI application and API orchestration
├── data/
│   ├── raw/                # Immutable source match batches
│   └── derived/            # Rebuildable statistics and datasets
├── data_pipeline/
│   ├── ingestion/          # OpenDota acquisition
│   └── processing/         # Parsing, statistics, and dataset construction
├── docs/                   # Architecture, algorithm, and deployment guides
├── experiments/            # Disposable queries and notebooks
├── frontend/               # React application
├── metadata/               # Heroes and maintained position definitions
├── models/                 # Trained model artifacts, not source code
├── tests/                  # Automated tests across layer boundaries
└── tools/                  # Local maintenance tools
```

## Dependency Rules

Dependencies point inward in one direction:

```text
ingestion -> raw data -> processing -> derived data -> algorithms -> backend
                                                         ^             |
                                                         |             v
                                             V2 feature contract    frontend
```

- Ingestion knows only the remote source and raw batch format.
- Processing owns reusable match parsing and generated training/stat data.
- Algorithms consume derived data and expose Python inference interfaces.
- The V2 dataset builder imports only the algorithm's pure feature schema so
  training and online inference cannot disagree about feature order.
- Backend coordinates algorithms and metadata but never builds training data.
- Frontend calls HTTP APIs and does not import backend or algorithm code.

## Commands

Install the project commands and offline pipeline dependencies:

```bash
python3 -m pip install -e ".[pipeline,train,dev]"
```

```text
dota-fetch-matches      Fetch raw OpenDota match batches
dota-hero-rank-stats    Export rank-segment hero statistics
dota-build-v1           Build the V1 SQLite statistics database
dota-score-v1           Run V1 recommendations from the terminal
dota-build-v2           Build the V2 sparse training dataset
dota-train-v2           Train and evaluate the V2 LightGBM model
```

Run the application separately with:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
