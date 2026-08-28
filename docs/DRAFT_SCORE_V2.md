# Draft Score V2: LightGBM

V2 predicts the probability that the candidate hero's team wins. It is
independent from the manually weighted V1 score and is exposed through a
separate API.

## Training sample

Each valid 5v5 match produces one sample from each side per repeat. A sample
contains:

- one candidate hero from that side;
- a random subset of the other four allied heroes;
- a random subset of the five enemy heroes;
- rank segment, Radiant/Dire side, and both visible hero counts;
- label `1` when that side won and `0` otherwise.

Both perspectives from a match always enter the same time split. This keeps
every match balanced with one positive and one negative sample and prevents
match leakage between train, validation, and test data.

The sparse feature fields are `candidate_hero_*`, `ally_hero_*`,
`enemy_hero_*`, `rank_*`, `is_radiant`, `ally_count`, and `enemy_count`.
The generated files use LightGBM's zero-based LibSVM format.

## Install

Training needs LightGBM, NumPy, SciPy, and scikit-learn:

```bash
python3 -m pip install -e ".[pipeline,train]"
```

An API server that only loads an existing model needs the smaller runtime set:

```bash
python3 -m pip install -e ".[ml]"
```

## Build data

The default split is deterministic random 80%/10%/10% by match ID. Both side
samples from one match always enter the same split, and the result is stable
for the same `--seed`:

```bash
dota-build-v2 \
  --matches-dir data/raw/ranked_matches_260802_260825 \
  --heroes metadata/heroes.json \
  --output data/derived/draft_score_v2_dataset \
  --overwrite
```

Customize the random split with `--validation-ratio` and `--test-ratio`.
For example, `--validation-ratio 0.15 --test-ratio 0.15` produces an expected
70%/15%/15% split without loading all matches into memory.

Use a chronological split when evaluating performance on future matches:

```bash
dota-build-v2 \
  --matches-dir data/raw/ranked_matches_260802_260825 \
  --heroes metadata/heroes.json \
  --split-strategy time \
  --validation-start 2026-08-20 \
  --test-start 2026-08-23 \
  --output data/derived/draft_score_v2_dataset \
  --overwrite
```

The command writes:

```text
data/derived/draft_score_v2_dataset/
  train.libsvm
  validation.libsvm
  test.libsvm
  metadata.json
```

Use `--samples-per-side 2` to generate two independently masked samples per
side and match. Start with the default `1`; larger values increase file size
and training time linearly. `--max-matches` is available for pipeline smoke
tests.

## Train

```bash
dota-train-v2 \
  --dataset data/derived/draft_score_v2_dataset \
  --output models/draft_score_v2_lightgbm \
  --overwrite
```

The default training configuration uses binary log loss, early stopping,
feature and row subsampling, and L1/L2 regularization. After training, a Platt
calibrator is fitted on validation logits. The test set is used only for the
final AUC, log loss, Brier score, and 15-bin ECE report.

The model directory contains:

```text
models/draft_score_v2_lightgbm/
  model.txt
  metadata.json
```

`metadata.json` records the exact feature order, source dataset, parameters,
best iteration, calibration coefficients, test metrics, and top feature
importance. Training and API inference both use the same `FeatureSchema` and
refuse incompatible artifacts.

## API

The default model path is `models/draft_score_v2_lightgbm`. Override it with:

```bash
export DRAFT_V2_MODEL_PATH=/absolute/path/to/model-directory
```

Check model readiness:

```bash
curl http://127.0.0.1:8000/api/v1/models/draft-score-v2
```

Request recommendations:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/recommend/v2 \
  -H 'Content-Type: application/json' \
  -d '{
    "rank": "Legend",
    "allies": [25, 26],
    "enemies": [89, 12],
    "excluded_hero_ids": [],
    "position_ids": [1],
    "side": null,
    "top_k": 15
  }'
```

Example result item:

```json
{
  "hero_id": 52,
  "hero_name": "Leshrac",
  "win_probability": 0.5482
}
```

When `side` is `null`, inference predicts every candidate once as Radiant and
once as Dire, then averages the two probabilities. Set it to `radiant` or
`dire` when that information is known.

Position and exclusion settings only filter candidates. V1 coefficients and
hero proficiency are intentionally absent because V2's output is a calibrated
match win probability. Personalization should be a separate reranking layer.

If the artifact is missing or the runtime ML dependency is unavailable, the
status endpoint reports `missing` or `unavailable`, and recommendation returns
HTTP `503 MODEL_NOT_READY`. V1 remains available.
