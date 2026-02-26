-- Quick queries to inspect RAGAS evaluation results.
-- Usage:
-- psql -h localhost -U <user> -d smartcart_ai -f database/scripts/view_ragas_results.sql

-- Latest runs with summary metrics.
SELECT
  run_id,
  run_label,
  app_component,
  dataset_name,
  status,
  started_at,
  completed_at,
  total_cases,
  pass_count,
  fail_count,
  avg_overall_score,
  avg_faithfulness,
  avg_answer_relevancy,
  avg_context_precision,
  avg_context_recall,
  avg_harmfulness
FROM ragas_eval_run_summary
ORDER BY started_at DESC
LIMIT 20;

-- Latest failed cases (if any).
SELECT
  r.run_id,
  r.run_label,
  e.case_id,
  e.user_query,
  e.overall_score,
  e.faithfulness,
  e.answer_relevancy,
  e.context_precision,
  e.context_recall,
  e.harmfulness,
  e.notes,
  e.created_at
FROM ragas_eval_results e
JOIN ragas_eval_runs r ON r.run_id = e.run_id
WHERE e.pass IS FALSE
ORDER BY e.created_at DESC
LIMIT 50;
