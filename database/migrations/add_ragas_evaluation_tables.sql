-- RAGAS evaluation storage
-- Stores run-level summaries and per-case metric scores for LLM quality tracking.

CREATE TABLE IF NOT EXISTS ragas_eval_runs (
  run_id BIGSERIAL PRIMARY KEY,
  run_label TEXT,
  app_component TEXT NOT NULL DEFAULT 'chat-agent',
  dataset_name TEXT,
  model_name TEXT,
  evaluator_model TEXT,
  git_commit VARCHAR(64),
  total_cases INT,
  metadata JSONB DEFAULT '{}'::jsonb,
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  status VARCHAR(20) NOT NULL DEFAULT 'running',
  avg_faithfulness NUMERIC(6,4),
  avg_answer_relevancy NUMERIC(6,4),
  avg_context_precision NUMERIC(6,4),
  avg_context_recall NUMERIC(6,4),
  avg_harmfulness NUMERIC(6,4),
  avg_overall_score NUMERIC(6,4)
);

CREATE INDEX IF NOT EXISTS idx_ragas_eval_runs_started_at
  ON ragas_eval_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ragas_eval_runs_component
  ON ragas_eval_runs(app_component);
CREATE INDEX IF NOT EXISTS idx_ragas_eval_runs_status
  ON ragas_eval_runs(status);

CREATE TABLE IF NOT EXISTS ragas_eval_results (
  result_id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES ragas_eval_runs(run_id) ON DELETE CASCADE,
  case_id TEXT,
  user_query TEXT NOT NULL,
  expected_answer TEXT,
  model_answer TEXT,
  retrieved_context TEXT,
  faithfulness NUMERIC(6,4),
  answer_relevancy NUMERIC(6,4),
  context_precision NUMERIC(6,4),
  context_recall NUMERIC(6,4),
  harmfulness NUMERIC(6,4),
  overall_score NUMERIC(6,4),
  pass BOOLEAN,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ragas_eval_results_run_id
  ON ragas_eval_results(run_id);
CREATE INDEX IF NOT EXISTS idx_ragas_eval_results_pass
  ON ragas_eval_results(pass);
CREATE INDEX IF NOT EXISTS idx_ragas_eval_results_created_at
  ON ragas_eval_results(created_at DESC);

CREATE OR REPLACE VIEW ragas_eval_run_summary AS
SELECT
  r.run_id,
  r.run_label,
  r.app_component,
  r.dataset_name,
  r.model_name,
  r.evaluator_model,
  r.status,
  r.started_at,
  r.completed_at,
  r.total_cases,
  r.avg_faithfulness,
  r.avg_answer_relevancy,
  r.avg_context_precision,
  r.avg_context_recall,
  r.avg_harmfulness,
  r.avg_overall_score,
  COUNT(res.result_id) AS stored_case_count,
  SUM(CASE WHEN res.pass IS TRUE THEN 1 ELSE 0 END) AS pass_count,
  SUM(CASE WHEN res.pass IS FALSE THEN 1 ELSE 0 END) AS fail_count
FROM ragas_eval_runs r
LEFT JOIN ragas_eval_results res ON res.run_id = r.run_id
GROUP BY
  r.run_id, r.run_label, r.app_component, r.dataset_name, r.model_name, r.evaluator_model,
  r.status, r.started_at, r.completed_at, r.total_cases, r.avg_faithfulness, r.avg_answer_relevancy,
  r.avg_context_precision, r.avg_context_recall, r.avg_harmfulness, r.avg_overall_score;
