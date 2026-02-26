#!/usr/bin/env python3
"""
Run RAGAS evaluation and store results in Postgres.

Expected dataset JSONL fields (per row):
  - case_id (optional)
  - user_query | query | question (required)
  - expected_answer | ground_truth (optional but recommended)
  - retrieved_context | contexts (optional; string or list[str])
  - model_answer | answer (optional; if missing, script calls chat endpoint)
"""

import argparse
import importlib
import json
import os
import statistics
import uuid
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import requests
from psycopg2.extras import RealDictCursor


def load_env_files():
    """Load .env values from common project locations if present.

    Existing environment variables are not overwritten.
    """
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent.parent
    candidates = [
        project_root / ".env",
        project_root / "Agents" / "decision-orchestration-agent" / ".env",
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            val = v.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = val


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        val = float(x)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    except Exception:
        return None


def _mean(values: List[Optional[float]]) -> Optional[float]:
    cleaned = [v for v in values if (v is not None and not math.isnan(v) and not math.isinf(v))]
    if not cleaned:
        return None
    return float(statistics.fmean(cleaned))


def _to_contexts(raw: Any) -> List[str]:
    if raw is None:
        return [""]
    if isinstance(raw, list):
        vals = [str(x).strip() for x in raw if str(x).strip()]
        return vals if vals else [""]
    s = str(raw).strip()
    return [s] if s else [""]


def _join_contexts(contexts: List[str]) -> str:
    return "\n\n".join([c for c in contexts if c]).strip()


@dataclass
class EvalRow:
    case_id: str
    user_query: str
    expected_answer: str
    model_answer: str
    contexts: List[str]


def load_eval_rows(path: Path) -> List[EvalRow]:
    rows: List[EvalRow] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            query = (
                obj.get("user_query")
                or obj.get("query")
                or obj.get("question")
                or ""
            ).strip()
            if not query:
                raise ValueError(f"Row {i}: missing user_query/query/question")
            case_id = str(obj.get("case_id") or f"case_{i}")
            expected = str(obj.get("expected_answer") or obj.get("ground_truth") or "").strip()
            model_answer = str(obj.get("model_answer") or obj.get("answer") or "").strip()
            contexts = _to_contexts(obj.get("retrieved_context") if "retrieved_context" in obj else obj.get("contexts"))
            rows.append(
                EvalRow(
                    case_id=case_id,
                    user_query=query,
                    expected_answer=expected,
                    model_answer=model_answer,
                    contexts=contexts,
                )
            )
    if not rows:
        raise ValueError("No rows found in dataset file.")
    return rows


def call_chat_api(chat_api_url: str, query: str, timeout_sec: int = 30) -> str:
    payload = {"query": query, "session_id": f"ragas-{uuid.uuid4().hex[:10]}"}
    r = requests.post(chat_api_url, json=payload, timeout=timeout_sec)
    if not r.ok:
        raise RuntimeError(f"Chat API failed ({r.status_code}): {r.text[:200]}")
    data = r.json() or {}
    return str(data.get("answer") or "").strip()


def _looks_like_metric_instance(obj: Any) -> bool:
    if obj is None:
        return False
    # Keep this duck-typed to survive API changes across ragas versions.
    return hasattr(obj, "name") and (
        hasattr(obj, "score") or hasattr(obj, "single_turn_ascore") or hasattr(obj, "ascore")
    )


def _to_metric_instance(symbol: Any) -> Optional[Any]:
    if _looks_like_metric_instance(symbol):
        return symbol
    if isinstance(symbol, type):
        try:
            obj = symbol()
            if _looks_like_metric_instance(obj):
                return obj
        except Exception:
            return None
    if callable(symbol):
        try:
            obj = symbol()
            if _looks_like_metric_instance(obj):
                return obj
        except Exception:
            return None
    return None


def resolve_ragas_metrics(metric_names: List[str], debug: bool = False):
    # RAGAS API differs by version; resolve by trying multiple symbol names/modules.
    metric_aliases = {
        "faithfulness": ["faithfulness", "Faithfulness"],
        "answer_relevancy": ["answer_relevancy", "AnswerRelevancy", "ResponseRelevancy"],
        "context_precision": ["context_precision", "ContextPrecision"],
        "context_recall": ["context_recall", "ContextRecall"],
    }
    candidate_modules = ["ragas.metrics.collections", "ragas.metrics"]

    resolved = []
    for logical_name in metric_names:
        aliases = metric_aliases.get(logical_name, [logical_name])
        metric_obj = None
        for mod_name in candidate_modules:
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue
            for alias in aliases:
                if not hasattr(mod, alias):
                    continue
                raw = getattr(mod, alias)
                metric_obj = _to_metric_instance(raw)
                if metric_obj is not None:
                    if debug:
                        print(f"[ragas] metric '{logical_name}' resolved from {mod_name}.{alias} -> {type(metric_obj)}")
                    break
            if metric_obj is not None:
                break
        if metric_obj is None and debug:
            print(f"[ragas] metric '{logical_name}' could not be resolved; skipping")
        if metric_obj is not None:
            resolved.append(metric_obj)
    return resolved


def run_ragas(rows: List[EvalRow], metric_names: List[str], mistral_api_key: str, evaluator_model: str, debug_metrics: bool = False):
    from datasets import Dataset
    from ragas import evaluate
    from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings

    metrics = resolve_ragas_metrics(metric_names, debug=debug_metrics)
    if not metrics:
        raise ValueError(
            "No supported RAGAS metrics resolved for your installed version. "
            "Try --metrics faithfulness and --debug-metrics."
        )

    dataset = Dataset.from_dict(
        {
            "question": [r.user_query for r in rows],
            "answer": [r.model_answer for r in rows],
            "contexts": [r.contexts for r in rows],
            "ground_truth": [r.expected_answer for r in rows],
        }
    )

    evaluator_llm = ChatMistralAI(model=evaluator_model, mistral_api_key=mistral_api_key)
    evaluator_embeddings = MistralAIEmbeddings(mistral_api_key=mistral_api_key)

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        raise_exceptions=False,
    )

    if not hasattr(result, "to_pandas"):
        raise RuntimeError("Unsupported RAGAS result format: missing to_pandas().")

    df = result.to_pandas()
    row_scores: List[Dict[str, Any]] = []
    for i, r in enumerate(rows):
        rec = {
            "case_id": r.case_id,
            "user_query": r.user_query,
            "expected_answer": r.expected_answer,
            "model_answer": r.model_answer,
            "retrieved_context": _join_contexts(r.contexts),
            "faithfulness": _safe_float(df.loc[i, "faithfulness"]) if "faithfulness" in df.columns else None,
            "answer_relevancy": _safe_float(df.loc[i, "answer_relevancy"]) if "answer_relevancy" in df.columns else None,
            "context_precision": _safe_float(df.loc[i, "context_precision"]) if "context_precision" in df.columns else None,
            "context_recall": _safe_float(df.loc[i, "context_recall"]) if "context_recall" in df.columns else None,
            "harmfulness": _safe_float(df.loc[i, "harmfulness"]) if "harmfulness" in df.columns else None,
        }

        positives = [
            rec["faithfulness"],
            rec["answer_relevancy"],
            rec["context_precision"],
            rec["context_recall"],
        ]
        pos_avg = _mean(positives)
        if rec["harmfulness"] is not None and pos_avg is not None:
            rec["overall_score"] = float((pos_avg + (1.0 - rec["harmfulness"])) / 2.0)
        else:
            rec["overall_score"] = pos_avg
        row_scores.append(rec)

    agg = {
        "avg_faithfulness": _mean([r["faithfulness"] for r in row_scores]),
        "avg_answer_relevancy": _mean([r["answer_relevancy"] for r in row_scores]),
        "avg_context_precision": _mean([r["context_precision"] for r in row_scores]),
        "avg_context_recall": _mean([r["context_recall"] for r in row_scores]),
        "avg_harmfulness": _mean([r["harmfulness"] for r in row_scores]),
        "avg_overall_score": _mean([r["overall_score"] for r in row_scores]),
    }
    return row_scores, agg


def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "smartcart_ai"),
        user=os.getenv("DB_USER", "meghanarendrasimha"),
        password=os.getenv("DB_PASSWORD", "Welcome@123"),
        cursor_factory=RealDictCursor,
    )


def create_run(cur, run_label: str, dataset_name: str, model_name: str, evaluator_model: str, git_commit: str, total_cases: int) -> int:
    cur.execute(
        """
        INSERT INTO ragas_eval_runs (
          run_label, app_component, dataset_name, model_name, evaluator_model,
          git_commit, total_cases, metadata, status, started_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        RETURNING run_id
        """,
        (
            run_label,
            "chat-agent",
            dataset_name,
            model_name,
            evaluator_model,
            git_commit,
            total_cases,
            json.dumps({}),
            "running",
            datetime.now(timezone.utc),
        ),
    )
    return int(cur.fetchone()["run_id"])


def store_results(cur, run_id: int, rows: List[Dict[str, Any]], pass_threshold: float, max_harmfulness: float):
    for r in rows:
        harmful = r.get("harmfulness")
        overall = r.get("overall_score")
        if overall is not None and (math.isnan(overall) or math.isinf(overall)):
            overall = None
        if harmful is not None and (math.isnan(harmful) or math.isinf(harmful)):
            harmful = None
        passed = (overall is not None and overall >= pass_threshold) and (harmful is None or harmful <= max_harmfulness)
        cur.execute(
            """
            INSERT INTO ragas_eval_results (
              run_id, case_id, user_query, expected_answer, model_answer, retrieved_context,
              faithfulness, answer_relevancy, context_precision, context_recall, harmfulness, overall_score, pass, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                r.get("case_id"),
                r.get("user_query"),
                r.get("expected_answer"),
                r.get("model_answer"),
                r.get("retrieved_context"),
                r.get("faithfulness"),
                r.get("answer_relevancy"),
                r.get("context_precision"),
                r.get("context_recall"),
                r.get("harmfulness"),
                r.get("overall_score"),
                passed,
                None,
            ),
        )


def complete_run(cur, run_id: int, agg: Dict[str, Optional[float]], status: str):
    cur.execute(
        """
        UPDATE ragas_eval_runs
        SET
          completed_at = %s,
          status = %s,
          avg_faithfulness = %s,
          avg_answer_relevancy = %s,
          avg_context_precision = %s,
          avg_context_recall = %s,
          avg_harmfulness = %s,
          avg_overall_score = %s
        WHERE run_id = %s
        """,
        (
            datetime.now(timezone.utc),
            status,
            agg.get("avg_faithfulness"),
            agg.get("avg_answer_relevancy"),
            agg.get("avg_context_precision"),
            agg.get("avg_context_recall"),
            agg.get("avg_harmfulness"),
            agg.get("avg_overall_score"),
            run_id,
        ),
    )


def parse_args():
    p = argparse.ArgumentParser(description="Run RAGAS evaluation and persist results in Postgres.")
    p.add_argument("--dataset", required=True, help="Path to JSONL dataset file.")
    p.add_argument("--chat-api-url", default="http://localhost:8080/api/agents/chat", help="Chat endpoint used to generate answers when missing.")
    p.add_argument("--run-label", default=None, help="Optional label for this run.")
    p.add_argument("--dataset-name", default=None, help="Optional dataset display name.")
    p.add_argument("--model-name", default="chat-agent", help="Model/app label for storage.")
    p.add_argument("--evaluator-model", default=os.getenv("MISTRAL_MODEL", "mistral-medium"))
    p.add_argument("--metrics", default="faithfulness")
    p.add_argument("--debug-metrics", action="store_true")
    p.add_argument("--pass-threshold", type=float, default=0.70)
    p.add_argument("--max-harmfulness", type=float, default=0.20)
    p.add_argument("--git-commit", default=os.getenv("GIT_COMMIT", ""))
    p.add_argument("--skip-chat-call", action="store_true", help="Do not call chat API; require model_answer in dataset.")
    return p.parse_args()


def main():
    load_env_files()
    args = parse_args()

    mistral_api_key = os.getenv("MISTRAL_API_KEY", "").strip()
    if not mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY is required for RAGAS evaluator LLM.")

    dataset_path = Path(args.dataset).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    rows = load_eval_rows(dataset_path)
    if not args.skip_chat_call:
        for r in rows:
            if not r.model_answer:
                r.model_answer = call_chat_api(args.chat_api_url, r.user_query)
    else:
        missing = [r.case_id for r in rows if not r.model_answer]
        if missing:
            raise RuntimeError(f"--skip-chat-call set, but model_answer missing for cases: {', '.join(missing[:10])}")

    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]
    run_label = args.run_label or f"ragas-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    dataset_name = args.dataset_name or dataset_path.name

    conn = get_db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                run_id = create_run(
                    cur=cur,
                    run_label=run_label,
                    dataset_name=dataset_name,
                    model_name=args.model_name,
                    evaluator_model=args.evaluator_model,
                    git_commit=args.git_commit,
                    total_cases=len(rows),
                )

        try:
            row_scores, agg = run_ragas(
                rows=rows,
                metric_names=metrics,
                mistral_api_key=mistral_api_key,
                evaluator_model=args.evaluator_model,
                debug_metrics=args.debug_metrics,
            )
            with conn:
                with conn.cursor() as cur:
                    store_results(
                        cur=cur,
                        run_id=run_id,
                        rows=row_scores,
                        pass_threshold=args.pass_threshold,
                        max_harmfulness=args.max_harmfulness,
                    )
                    complete_run(cur=cur, run_id=run_id, agg=agg, status="completed")
        except Exception:
            with conn:
                with conn.cursor() as cur:
                    complete_run(
                        cur=cur,
                        run_id=run_id,
                        agg={
                            "avg_faithfulness": None,
                            "avg_answer_relevancy": None,
                            "avg_context_precision": None,
                            "avg_context_recall": None,
                            "avg_harmfulness": None,
                            "avg_overall_score": None,
                        },
                        status="failed",
                    )
            raise

    finally:
        conn.close()

    print("RAGAS evaluation completed.")
    print(f"Run label: {run_label}")
    print(f"Dataset: {dataset_name}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
