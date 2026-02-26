package com.smartcartai.backend.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/ragas")
@Tag(name = "RAGAS", description = "RAGAS evaluation run summaries and failures")
public class RagasController {

    private final JdbcTemplate jdbcTemplate;

    public RagasController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping("/runs")
    @Operation(summary = "Get latest RAGAS run summaries")
    public ResponseEntity<List<Map<String, Object>>> getRuns() {
        try {
            String sql = """
                SELECT
                  run_id AS "runId",
                  run_label AS "runLabel",
                  app_component AS "appComponent",
                  dataset_name AS "datasetName",
                  model_name AS "modelName",
                  evaluator_model AS "evaluatorModel",
                  status,
                  started_at AS "startedAt",
                  completed_at AS "completedAt",
                  total_cases AS "totalCases",
                  pass_count AS "passCount",
                  fail_count AS "failCount",
                  avg_overall_score AS "avgOverallScore",
                  avg_faithfulness AS "avgFaithfulness",
                  avg_answer_relevancy AS "avgAnswerRelevancy",
                  avg_context_precision AS "avgContextPrecision",
                  avg_context_recall AS "avgContextRecall",
                  avg_harmfulness AS "avgHarmfulness"
                FROM ragas_eval_run_summary
                ORDER BY run_id DESC
                LIMIT 50
                """;
            return ResponseEntity.ok(jdbcTemplate.queryForList(sql));
        } catch (Exception e) {
            return ResponseEntity.ok(Collections.emptyList());
        }
    }

    @GetMapping("/failures")
    @Operation(summary = "Get latest failed RAGAS cases")
    public ResponseEntity<List<Map<String, Object>>> getFailures(
            @RequestParam(name = "latestRunOnly", defaultValue = "true") boolean latestRunOnly) {
        try {
            String sql;
            if (latestRunOnly) {
                sql = """
                    WITH latest_run AS (
                      SELECT run_id
                      FROM ragas_eval_runs
                      ORDER BY run_id DESC
                      LIMIT 1
                    )
                    SELECT
                      r.run_id AS "runId",
                      r.run_label AS "runLabel",
                      e.case_id AS "caseId",
                      e.user_query AS "userQuery",
                      e.overall_score AS "overallScore",
                      e.faithfulness,
                      e.answer_relevancy AS "answerRelevancy",
                      e.context_precision AS "contextPrecision",
                      e.context_recall AS "contextRecall",
                      e.harmfulness,
                      e.notes,
                      e.created_at AS "createdAt"
                    FROM ragas_eval_results e
                    JOIN ragas_eval_runs r ON r.run_id = e.run_id
                    JOIN latest_run lr ON lr.run_id = e.run_id
                    WHERE e.pass IS FALSE
                    ORDER BY e.created_at DESC
                    LIMIT 200
                    """;
            } else {
                sql = """
                    SELECT
                      r.run_id AS "runId",
                      r.run_label AS "runLabel",
                      e.case_id AS "caseId",
                      e.user_query AS "userQuery",
                      e.overall_score AS "overallScore",
                      e.faithfulness,
                      e.answer_relevancy AS "answerRelevancy",
                      e.context_precision AS "contextPrecision",
                      e.context_recall AS "contextRecall",
                      e.harmfulness,
                      e.notes,
                      e.created_at AS "createdAt"
                    FROM ragas_eval_results e
                    JOIN ragas_eval_runs r ON r.run_id = e.run_id
                    WHERE e.pass IS FALSE
                    ORDER BY e.created_at DESC
                    LIMIT 200
                    """;
            }
            return ResponseEntity.ok(jdbcTemplate.queryForList(sql));
        } catch (Exception e) {
            return ResponseEntity.ok(Collections.emptyList());
        }
    }
}
