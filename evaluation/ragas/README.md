# RAGAS Evaluation Runner

This module runs RAGAS metrics for SmartCartAI chat responses and stores results in:
- `ragas_eval_runs`
- `ragas_eval_results`

## 1) Prerequisites

1. Apply DB migration:

```bash
psql -h localhost -U <user> -d smartcart_ai -f database/migrations/add_ragas_evaluation_tables.sql
```

2. Install dependencies:

```bash
pip install -r evaluation/ragas/requirements.txt
```

Pinned evaluator profile in this repo:
- `ragas==0.4.3`
- default metrics: `faithfulness,response_relevancy,context_precision,context_recall`

3. Ensure services and env:
- Backend running on `http://localhost:8080` (default)
- Chat agent available via backend `/api/agents/chat`
- `MISTRAL_API_KEY` exported in shell

## 2) Dataset format (JSONL)

Per row:
- `case_id` (optional)
- `user_query` (or `query` or `question`) required
- `expected_answer` (or `ground_truth`) recommended
- `retrieved_context` (string or list) optional
- `model_answer` optional (if omitted, runner calls chat API)

If `retrieved_context` is omitted and `model_answer` is generated live, the runner requests
`include_eval_context=true` from the chat endpoint and uses `retrieved_contexts` from response.

Sample:
- `evaluation/ragas/datasets/sample_inventory_eval.jsonl`
- `evaluation/ragas/datasets/sample_inventory_eval_v2_fixed.jsonl` (fixed answers + exact evidence; best for stable CI)

## 3) Run evaluation

```bash
python evaluation/ragas/run_eval.py \
  --dataset evaluation/ragas/datasets/sample_inventory_eval.jsonl \
  --chat-api-url http://localhost:8080/api/agents/chat \
  --run-label "chat-regression-1" \
  --dataset-name "inventory-core-v1"
```

To override default metrics:

```bash
python evaluation/ragas/run_eval.py \
  --dataset <path>.jsonl \
  --metrics faithfulness,response_relevancy,context_precision,context_recall
```

If your dataset already includes `model_answer` and you do not want live calls:

```bash
python evaluation/ragas/run_eval.py \
  --dataset evaluation/ragas/datasets/sample_inventory_eval_v2_fixed.jsonl \
  --skip-chat-call \
  --metrics faithfulness,response_relevancy \
  --max-workers 1 \
  --run-label "stable-fixed-set"
```

If you hit API 429/rate-limit errors, keep `--max-workers 1`.

## 4) View results

```bash
psql -h localhost -U <user> -d smartcart_ai -f database/scripts/view_ragas_results.sql
```

Or use Admin UI `RAGAS` tab.
