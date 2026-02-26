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
import inspect
import json
import os
import statistics
import uuid
import math
import types
import warnings
import time
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


def _cosine_similarity(a: List[float], b: List[float]) -> Optional[float]:
    if not a or not b or len(a) != len(b):
        return None
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        xf = float(x)
        yf = float(y)
        dot += xf * yf
        na += xf * xf
        nb += yf * yf
    if na <= 0.0 or nb <= 0.0:
        return None
    return float(dot / ((na ** 0.5) * (nb ** 0.5)))


def _to_contexts(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        vals = [str(x).strip() for x in raw if str(x).strip()]
        return vals
    s = str(raw).strip()
    return [s] if s else []


def _join_contexts(contexts: List[str]) -> str:
    return "\n\n".join([c for c in contexts if c]).strip()


def _contexts_for_ragas(contexts: List[str]) -> List[str]:
    """RAGAS Dataset expects non-empty list values for `contexts`."""
    vals = [c for c in (contexts or []) if str(c).strip()]
    return vals if vals else [""]


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


def call_chat_api(chat_api_url: str, query: str, timeout_sec: int = 30) -> Tuple[str, List[str]]:
    payload = {
        "query": query,
        "session_id": f"ragas-{uuid.uuid4().hex[:10]}",
        "include_eval_context": True,
    }
    r = requests.post(chat_api_url, json=payload, timeout=timeout_sec)
    if not r.ok:
        raise RuntimeError(f"Chat API failed ({r.status_code}): {r.text[:200]}")
    data = r.json() or {}
    answer = str(data.get("answer") or "").strip()
    contexts = _to_contexts(
        data.get("retrieved_contexts")
        if "retrieved_contexts" in data
        else (data.get("retrieved_context") if "retrieved_context" in data else data.get("contexts"))
    )
    return answer, contexts


def _looks_like_metric_instance(obj: Any) -> bool:
    if obj is None:
        return False
    # Keep this duck-typed to survive API changes across ragas versions.
    return hasattr(obj, "name") and (
        hasattr(obj, "score") or hasattr(obj, "single_turn_ascore") or hasattr(obj, "ascore")
    )


def _to_metric_instance(symbol: Any, llm: Any = None, embeddings: Any = None) -> Optional[Any]:
    if _looks_like_metric_instance(symbol):
        return symbol
    if isinstance(symbol, type):
        kwargs = {}
        try:
            sig = inspect.signature(symbol)
            if "llm" in sig.parameters and llm is not None:
                kwargs["llm"] = llm
            if "embeddings" in sig.parameters and embeddings is not None:
                kwargs["embeddings"] = embeddings
        except Exception:
            kwargs = {}
        try:
            obj = symbol(**kwargs)
            if _looks_like_metric_instance(obj):
                return obj
        except Exception:
            return None
    if callable(symbol):
        kwargs = {}
        try:
            sig = inspect.signature(symbol)
            if "llm" in sig.parameters and llm is not None:
                kwargs["llm"] = llm
            if "embeddings" in sig.parameters and embeddings is not None:
                kwargs["embeddings"] = embeddings
        except Exception:
            kwargs = {}
        try:
            obj = symbol(**kwargs)
            if _looks_like_metric_instance(obj):
                return obj
        except Exception:
            return None
    return None


def _metric_from_module(module_obj: Any, class_candidates: List[str], llm: Any = None, embeddings: Any = None) -> Optional[Any]:
    if not isinstance(module_obj, types.ModuleType):
        return None
    for cls_name in class_candidates:
        if not hasattr(module_obj, cls_name):
            continue
        cls_or_obj = getattr(module_obj, cls_name)
        metric = _to_metric_instance(cls_or_obj, llm=llm, embeddings=embeddings)
        if metric is not None:
            return metric
    return None


def resolve_ragas_metrics(metric_names: List[str], llm: Any = None, embeddings: Any = None, debug: bool = False) -> Tuple[List[Any], List[str]]:
    # RAGAS API differs by version; resolve by trying multiple symbol names/modules.
    metric_aliases = {
        "faithfulness": ["faithfulness", "Faithfulness"],
        # In ragas==0.4.3, response_relevancy is typically more stable than answer_relevancy.
        "answer_relevancy": ["answer_relevancy", "response_relevancy", "answer_relevance", "AnswerRelevancy", "ResponseRelevancy"],
        # Keep logical name `response_relevancy` for CLI compatibility; map to answer_relevancy where needed.
        "response_relevancy": ["response_relevancy", "answer_relevancy", "AnswerRelevancy", "ResponseRelevancy"],
        "context_relevance": ["context_relevance", "ContextRelevance"],
        "context_precision": ["context_precision", "ContextPrecision"],
        "context_recall": ["context_recall", "ContextRecall"],
    }
    module_class_hints = {
        "faithfulness": ["Faithfulness"],
        "answer_relevancy": ["AnswerRelevancy", "ResponseRelevancy"],
        "response_relevancy": ["ResponseRelevancy", "AnswerRelevancy"],
        "context_relevance": ["ContextRelevance"],
        "context_precision": ["ContextPrecision"],
        "context_recall": ["ContextRecall"],
    }
    candidate_modules = ["ragas.metrics.collections", "ragas.metrics"]

    resolved = []
    unresolved = []
    for logical_name in metric_names:
        aliases = metric_aliases.get(logical_name, [logical_name])
        metric_obj = None
        for mod_name in candidate_modules:
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue
            for alias in aliases:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=DeprecationWarning)
                    if not hasattr(mod, alias):
                        continue
                    raw = getattr(mod, alias)
                metric_obj = _to_metric_instance(raw, llm=llm, embeddings=embeddings)
                if metric_obj is None:
                    metric_obj = _metric_from_module(
                        raw,
                        module_class_hints.get(logical_name, []),
                        llm=llm,
                        embeddings=embeddings,
                    )
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
        else:
            unresolved.append(logical_name)
    return resolved, unresolved


def run_ragas(
    rows: List[EvalRow],
    metric_names: List[str],
    mistral_api_key: str,
    evaluator_model: str,
    debug_metrics: bool = False,
    max_workers: int = 1,
    fill_missing_with_zero: bool = False,
    evaluator_json_mode: bool = False,
    relevancy_retry_attempts: int = 2,
    use_embedding_relevancy_fallback: bool = True,
):
    from datasets import Dataset
    from ragas import evaluate
    from ragas.run_config import RunConfig
    from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings

    llm_kwargs: Dict[str, Any] = {"model": evaluator_model, "mistral_api_key": mistral_api_key, "temperature": 0}
    if evaluator_json_mode:
        llm_kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    try:
        evaluator_llm = ChatMistralAI(**llm_kwargs)
    except Exception:
        # Fallback if installed langchain-mistralai version does not support response_format model kwargs.
        llm_kwargs.pop("model_kwargs", None)
        evaluator_llm = ChatMistralAI(**llm_kwargs)
    evaluator_embeddings = MistralAIEmbeddings(mistral_api_key=mistral_api_key)

    metrics, unresolved = resolve_ragas_metrics(
        metric_names,
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        debug=debug_metrics,
    )
    if unresolved:
        raise ValueError(
            "Requested metrics not available in installed RAGAS version: "
            + ", ".join(unresolved)
        )
    if not metrics:
        raise ValueError(
            "No supported RAGAS metrics resolved for your installed version. "
            "Try --metrics faithfulness,response_relevancy and --debug-metrics."
        )

    dataset = Dataset.from_dict(
        {
            "question": [r.user_query for r in rows],
            "answer": [r.model_answer for r in rows],
            "contexts": [_contexts_for_ragas(r.contexts) for r in rows],
            "ground_truth": [r.expected_answer for r in rows],
        }
    )

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=RunConfig(
            timeout=180,
            max_retries=10,
            max_wait=60,
            max_workers=max(1, int(max_workers)),
        ),
        raise_exceptions=False,
    )

    if not hasattr(result, "to_pandas"):
        raise RuntimeError("Unsupported RAGAS result format: missing to_pandas().")

    df = result.to_pandas()
    if debug_metrics:
        print(f"[ragas] result columns: {list(df.columns)}")

    def _pick(df_row, cols: List[str]):
        for c in cols:
            if c in df.columns:
                return _safe_float(df_row[c])
        return None

    def _retry_relevancy_for_row(row_idx: int, attempts: int = 2) -> Optional[float]:
        """Best-effort second pass for relevancy only when main pass returned null."""
        if attempts <= 0:
            return None
        requested = [m.strip().lower() for m in metric_names]
        if "response_relevancy" not in requested and "answer_relevancy" not in requested:
            return None
        rel_metric_names = ["response_relevancy"]
        from datasets import Dataset
        from ragas import evaluate
        from ragas.run_config import RunConfig
        one = rows[row_idx]
        single_ds = Dataset.from_dict(
            {
                "question": [one.user_query],
                "answer": [one.model_answer],
                "contexts": [_contexts_for_ragas(one.contexts)],
                "ground_truth": [one.expected_answer],
            }
        )
        for _ in range(attempts):
            try:
                rel_metrics, unresolved_rel = resolve_ragas_metrics(
                    rel_metric_names,
                    llm=evaluator_llm,
                    embeddings=evaluator_embeddings,
                    debug=False,
                )
                if unresolved_rel or not rel_metrics:
                    return None
                rel_result = evaluate(
                    dataset=single_ds,
                    metrics=rel_metrics,
                    llm=evaluator_llm,
                    embeddings=evaluator_embeddings,
                    run_config=RunConfig(timeout=180, max_retries=10, max_wait=60, max_workers=1),
                    raise_exceptions=False,
                )
                if not hasattr(rel_result, "to_pandas"):
                    return None
                rel_df = rel_result.to_pandas()
                if rel_df.empty:
                    return None
                val = _safe_float(
                    rel_df.iloc[0].get("response_relevancy")
                    if "response_relevancy" in rel_df.columns
                    else rel_df.iloc[0].get("answer_relevancy")
                )
                if val is not None:
                    return val
            except Exception:
                pass
            time.sleep(0.25)
        return None

    def _embedding_relevancy_for_row(row_idx: int) -> Optional[float]:
        """Fallback relevancy using cosine similarity between answer and ground-truth embeddings."""
        try:
            row = rows[row_idx]
            answer = (row.model_answer or "").strip()
            ground_truth = (row.expected_answer or "").strip()
            if not answer or not ground_truth:
                return None
            vecs = evaluator_embeddings.embed_documents([answer, ground_truth])
            if not vecs or len(vecs) != 2:
                return None
            return _safe_float(_cosine_similarity(vecs[0], vecs[1]))
        except Exception:
            return None

    row_scores: List[Dict[str, Any]] = []
    for i, r in enumerate(rows):
        faithfulness = _pick(df.loc[i], ["faithfulness"])
        answer_relevancy = _pick(df.loc[i], ["answer_relevancy", "answer_relevance", "response_relevancy", "context_relevance"])
        context_precision = _pick(df.loc[i], ["context_precision"])
        context_recall = _pick(df.loc[i], ["context_recall"])
        harmfulness = _safe_float(df.loc[i, "harmfulness"]) if "harmfulness" in df.columns else None

        if fill_missing_with_zero:
            if faithfulness is None:
                faithfulness = 0.0
            if context_precision is None:
                context_precision = 0.0
            if context_recall is None:
                context_recall = 0.0

        if answer_relevancy is None and relevancy_retry_attempts > 0:
            answer_relevancy = _retry_relevancy_for_row(i, attempts=relevancy_retry_attempts)
        if answer_relevancy is None and use_embedding_relevancy_fallback:
            answer_relevancy = _embedding_relevancy_for_row(i)

        if fill_missing_with_zero and answer_relevancy is None:
            answer_relevancy = 0.0

        rec = {
            "case_id": r.case_id,
            "user_query": r.user_query,
            "expected_answer": r.expected_answer,
            "model_answer": r.model_answer,
            "retrieved_context": _join_contexts(r.contexts),
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "harmfulness": harmfulness,
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
    p.add_argument("--metrics", default="faithfulness,response_relevancy,context_precision,context_recall")
    p.add_argument("--debug-metrics", action="store_true")
    p.add_argument("--max-workers", type=int, default=1, help="RAGAS evaluator worker concurrency. Use 1 to avoid rate limits.")
    p.add_argument(
        "--fill-missing-with-zero",
        action="store_true",
        help="If a metric value is missing/null from RAGAS, persist it as 0.0 so dashboards always show all metrics.",
    )
    p.add_argument(
        "--disable-evaluator-json-mode",
        action="store_true",
        help="Disable JSON-object response mode for the evaluator LLM.",
    )
    p.add_argument(
        "--relevancy-retry-attempts",
        type=int,
        default=2,
        help="Second-pass attempts for missing relevancy scores (single-row retry).",
    )
    p.add_argument(
        "--disable-embedding-relevancy-fallback",
        action="store_true",
        help="Disable embedding-cosine fallback when RAGAS relevancy is missing.",
    )
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
                answer, contexts = call_chat_api(args.chat_api_url, r.user_query)
                r.model_answer = answer
                if not r.contexts and contexts:
                    r.contexts = contexts
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
                max_workers=args.max_workers,
                fill_missing_with_zero=args.fill_missing_with_zero,
                evaluator_json_mode=not args.disable_evaluator_json_mode,
                relevancy_retry_attempts=max(0, int(args.relevancy_retry_attempts)),
                use_embedding_relevancy_fallback=not args.disable_embedding_relevancy_fallback,
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
