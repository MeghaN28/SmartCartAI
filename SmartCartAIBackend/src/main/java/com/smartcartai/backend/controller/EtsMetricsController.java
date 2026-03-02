package com.smartcartai.backend.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/ets")
@Tag(name = "ETS", description = "ETS (Holt-Winters) demand forecast evaluation metrics")
public class EtsMetricsController {

    private final JdbcTemplate jdbcTemplate;

    public EtsMetricsController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping("/metrics")
    @Operation(summary = "Compute ETS forecast metrics from consumption history")
    public ResponseEntity<Map<String, Object>> getMetrics(
            @RequestParam(name = "lookbackDays", defaultValue = "60") int lookbackDays,
            @RequestParam(name = "windowDays", defaultValue = "7") int windowDays,
            @RequestParam(name = "demandThreshold", defaultValue = "1.0") double demandThreshold
    ) {
        int lb = clamp(lookbackDays, 14, 365);
        int w = clamp(windowDays, 3, 30);
        double thr = demandThreshold <= 0 ? 1.0 : demandThreshold;

        // ETS params should mirror Agents/common/forecasting.py defaults
        double alpha = envDouble("ETS_ALPHA", 0.3);
        double beta = envDouble("ETS_BETA", 0.1);
        double gamma = envDouble("ETS_GAMMA", 0.1);
        int period = envInt("ETS_PERIOD", 7);
        period = clamp(period, 2, 30);

        List<Map<String, Object>> rows;
        try {
            int backDays = Math.max(1, lb - 1);
            String sql = """
                WITH latest AS (
                  SELECT MAX(date) AS max_date
                  FROM consumption
                )
                SELECT
                  c.inventory_id AS "inventoryId",
                  c.date AS "date",
                  COALESCE(SUM(c.quantity_consumed), 0) AS "qty"
                FROM consumption c
                CROSS JOIN latest l
                WHERE l.max_date IS NOT NULL
                  AND c.date IS NOT NULL
                  AND c.date >= (l.max_date - (? * INTERVAL '1 day'))
                GROUP BY c.inventory_id, c.date
                ORDER BY c.inventory_id ASC, c.date ASC
                """;
            try {
                rows = jdbcTemplate.queryForList(sql, backDays);
            } catch (Exception ignored) {
                // Compatibility fallback for older schemas that used transaction_date instead of date.
                String sql2 = """
                    WITH latest AS (
                      SELECT MAX(transaction_date) AS max_date
                      FROM consumption
                    )
                    SELECT
                      c.inventory_id AS "inventoryId",
                      c.transaction_date AS "date",
                      COALESCE(SUM(c.quantity_consumed), 0) AS "qty"
                    FROM consumption c
                    CROSS JOIN latest l
                    WHERE l.max_date IS NOT NULL
                      AND c.transaction_date IS NOT NULL
                      AND c.transaction_date >= (l.max_date - (? * INTERVAL '1 day'))
                    GROUP BY c.inventory_id, c.transaction_date
                    ORDER BY c.inventory_id ASC, c.transaction_date ASC
                    """;
                rows = jdbcTemplate.queryForList(sql2, backDays);
            }
        } catch (Exception e) {
            return ResponseEntity.ok(Collections.emptyMap());
        }

        // Build per-item daily series (oldest -> newest)
        Map<String, List<Double>> seriesByItem = new LinkedHashMap<>();
        for (Map<String, Object> r : rows) {
            Object invObj = r.get("inventoryId");
            if (invObj == null) continue;
            String invId = String.valueOf(invObj);
            Number qtyNum = (r.get("qty") instanceof Number) ? (Number) r.get("qty") : null;
            double qty = qtyNum == null ? 0.0 : qtyNum.doubleValue();
            seriesByItem.computeIfAbsent(invId, k -> new ArrayList<>()).add(qty);
        }

        long tp = 0, fp = 0, tn = 0, fn = 0;
        double sumAbs = 0.0;
        double sumSq = 0.0;
        double sumApe = 0.0;
        long mapeCount = 0;
        double sumActualAbs = 0.0;
        double sumSmape = 0.0;
        long smapeCount = 0;
        long samples = 0;
        int itemsUsed = 0;

        // Baselines
        long tpNaive = 0, fpNaive = 0, tnNaive = 0, fnNaive = 0;
        double sumAbsNaive = 0.0, sumSqNaive = 0.0, sumApeNaive = 0.0, sumActualAbsNaive = 0.0, sumSmapeNaive = 0.0;
        long mapeCountNaive = 0, smapeCountNaive = 0;

        long tpSma = 0, fpSma = 0, tnSma = 0, fnSma = 0;
        double sumAbsSma = 0.0, sumSqSma = 0.0, sumApeSma = 0.0, sumActualAbsSma = 0.0, sumSmapeSma = 0.0;
        long mapeCountSma = 0, smapeCountSma = 0;

        for (Map.Entry<String, List<Double>> entry : seriesByItem.entrySet()) {
            List<Double> series = entry.getValue();
            if (series == null || series.size() < (w + 2)) {
                continue;
            }
            itemsUsed++;
            for (int i = w; i < series.size(); i++) {
                int start = Math.max(0, i - w);
                List<Double> history = series.subList(start, i);
                double pred = etsForecast(history, alpha, beta, gamma, period);
                double predNaive = safe(history.get(history.size() - 1)); // yesterday == today
                double predSma = mean(history); // moving average over windowDays

                Double actualObj = series.get(i);
                double actual = actualObj == null ? 0.0 : actualObj.doubleValue();

                double err = pred - actual;
                sumAbs += Math.abs(err);
                sumSq += err * err;
                sumActualAbs += Math.abs(actual);
                samples++;

                if (actual > 0.0) {
                    sumApe += Math.abs(err) / actual;
                    mapeCount++;
                }
                double denom = Math.abs(pred) + Math.abs(actual);
                if (denom > 0.0) {
                    sumSmape += (2.0 * Math.abs(err)) / denom;
                    smapeCount++;
                }

                boolean predPos = pred >= thr;
                boolean actPos = actual >= thr;
                if (predPos && actPos) tp++;
                else if (predPos) fp++;
                else if (actPos) fn++;
                else tn++;

                // Naive baseline
                double errN = predNaive - actual;
                sumAbsNaive += Math.abs(errN);
                sumSqNaive += errN * errN;
                sumActualAbsNaive += Math.abs(actual);
                if (actual > 0.0) {
                    sumApeNaive += Math.abs(errN) / actual;
                    mapeCountNaive++;
                }
                double denomN = Math.abs(predNaive) + Math.abs(actual);
                if (denomN > 0.0) {
                    sumSmapeNaive += (2.0 * Math.abs(errN)) / denomN;
                    smapeCountNaive++;
                }
                boolean predPosN = predNaive >= thr;
                if (predPosN && actPos) tpNaive++;
                else if (predPosN) fpNaive++;
                else if (actPos) fnNaive++;
                else tnNaive++;

                // Moving-average baseline (SMA over windowDays)
                double errS = predSma - actual;
                sumAbsSma += Math.abs(errS);
                sumSqSma += errS * errS;
                sumActualAbsSma += Math.abs(actual);
                if (actual > 0.0) {
                    sumApeSma += Math.abs(errS) / actual;
                    mapeCountSma++;
                }
                double denomS = Math.abs(predSma) + Math.abs(actual);
                if (denomS > 0.0) {
                    sumSmapeSma += (2.0 * Math.abs(errS)) / denomS;
                    smapeCountSma++;
                }
                boolean predPosS = predSma >= thr;
                if (predPosS && actPos) tpSma++;
                else if (predPosS) fpSma++;
                else if (actPos) fnSma++;
                else tnSma++;
            }
        }

        double mae = samples > 0 ? (sumAbs / samples) : 0.0;
        double rmse = samples > 0 ? Math.sqrt(sumSq / samples) : 0.0;
        double mape = mapeCount > 0 ? (sumApe / mapeCount) : 0.0;
        double wape = sumActualAbs > 0 ? (sumAbs / sumActualAbs) : 0.0;
        double smape = smapeCount > 0 ? (sumSmape / smapeCount) : 0.0;
        double accuracy = (tp + tn + fp + fn) > 0 ? ((double) (tp + tn) / (double) (tp + tn + fp + fn)) : 0.0;
        double precision = (tp + fp) > 0 ? ((double) tp / (double) (tp + fp)) : 0.0;
        double recall = (tp + fn) > 0 ? ((double) tp / (double) (tp + fn)) : 0.0;
        double f1 = (precision + recall) > 0 ? (2.0 * precision * recall / (precision + recall)) : 0.0;

        // Baseline aggregates
        double maeNaive = samples > 0 ? (sumAbsNaive / samples) : 0.0;
        double rmseNaive = samples > 0 ? Math.sqrt(sumSqNaive / samples) : 0.0;
        double mapeNaive = mapeCountNaive > 0 ? (sumApeNaive / mapeCountNaive) : 0.0;
        double wapeNaive = sumActualAbsNaive > 0 ? (sumAbsNaive / sumActualAbsNaive) : 0.0;
        double smapeNaive = smapeCountNaive > 0 ? (sumSmapeNaive / smapeCountNaive) : 0.0;
        double accuracyNaive = (tpNaive + tnNaive + fpNaive + fnNaive) > 0
                ? ((double) (tpNaive + tnNaive) / (double) (tpNaive + tnNaive + fpNaive + fnNaive))
                : 0.0;
        double precisionNaive = (tpNaive + fpNaive) > 0 ? ((double) tpNaive / (double) (tpNaive + fpNaive)) : 0.0;
        double recallNaive = (tpNaive + fnNaive) > 0 ? ((double) tpNaive / (double) (tpNaive + fnNaive)) : 0.0;
        double f1Naive = (precisionNaive + recallNaive) > 0 ? (2.0 * precisionNaive * recallNaive / (precisionNaive + recallNaive)) : 0.0;

        double maeSma = samples > 0 ? (sumAbsSma / samples) : 0.0;
        double rmseSma = samples > 0 ? Math.sqrt(sumSqSma / samples) : 0.0;
        double mapeSma = mapeCountSma > 0 ? (sumApeSma / mapeCountSma) : 0.0;
        double wapeSma = sumActualAbsSma > 0 ? (sumAbsSma / sumActualAbsSma) : 0.0;
        double smapeSma = smapeCountSma > 0 ? (sumSmapeSma / smapeCountSma) : 0.0;
        double accuracySma = (tpSma + tnSma + fpSma + fnSma) > 0
                ? ((double) (tpSma + tnSma) / (double) (tpSma + tnSma + fpSma + fnSma))
                : 0.0;
        double precisionSma = (tpSma + fpSma) > 0 ? ((double) tpSma / (double) (tpSma + fpSma)) : 0.0;
        double recallSma = (tpSma + fnSma) > 0 ? ((double) tpSma / (double) (tpSma + fnSma)) : 0.0;
        double f1Sma = (precisionSma + recallSma) > 0 ? (2.0 * precisionSma * recallSma / (precisionSma + recallSma)) : 0.0;

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("generatedAt", Instant.now().toString());
        out.put("lookbackDays", lb);
        out.put("windowDays", w);
        out.put("demandThreshold", thr);
        out.put("etsParams", Map.of(
                "alpha", alpha,
                "beta", beta,
                "gamma", gamma,
                "period", period
        ));
        out.put("itemsUsed", itemsUsed);
        out.put("samples", samples);
        if (samples == 0) {
            out.put("note", "No usable consumption history found for the requested lookback/window. "
                    + "This often happens when the dataset dates are far from today's date or items have too few daily points.");
        }
        out.put("classification", Map.of(
                "tp", tp, "fp", fp, "tn", tn, "fn", fn,
                "accuracy", accuracy,
                "precision", precision,
                "recall", recall,
                "f1", f1
        ));
        out.put("forecastError", Map.of(
                "mae", mae,
                "rmse", rmse,
                "mape", mape,
                "wape", wape,
                "smape", smape
        ));
        out.put("baselines", Map.of(
                "naive", Map.of(
                        "description", "Naive: predict next day equals previous day",
                        "classification", Map.of(
                                "tp", tpNaive, "fp", fpNaive, "tn", tnNaive, "fn", fnNaive,
                                "accuracy", accuracyNaive,
                                "precision", precisionNaive,
                                "recall", recallNaive,
                                "f1", f1Naive
                        ),
                        "forecastError", Map.of(
                                "mae", maeNaive,
                                "rmse", rmseNaive,
                                "mape", mapeNaive,
                                "wape", wapeNaive,
                                "smape", smapeNaive
                        )
                ),
                "movingAverage", Map.of(
                        "description", "SMA: predict next day as mean of last windowDays",
                        "classification", Map.of(
                                "tp", tpSma, "fp", fpSma, "tn", tnSma, "fn", fnSma,
                                "accuracy", accuracySma,
                                "precision", precisionSma,
                                "recall", recallSma,
                                "f1", f1Sma
                        ),
                        "forecastError", Map.of(
                                "mae", maeSma,
                                "rmse", rmseSma,
                                "mape", mapeSma,
                                "wape", wapeSma,
                                "smape", smapeSma
                        )
                )
        ));
        return ResponseEntity.ok(out);
    }

    private static int clamp(int v, int lo, int hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    private static double envDouble(String key, double defaultVal) {
        String raw = System.getenv(key);
        if (raw == null || raw.isBlank()) return defaultVal;
        try {
            return Double.parseDouble(raw.trim());
        } catch (Exception ignored) {
            return defaultVal;
        }
    }

    private static int envInt(String key, int defaultVal) {
        String raw = System.getenv(key);
        if (raw == null || raw.isBlank()) return defaultVal;
        try {
            return Integer.parseInt(raw.trim());
        } catch (Exception ignored) {
            return defaultVal;
        }
    }

    private static double exponentialSmoothing(List<Double> history, double alpha) {
        if (history == null || history.isEmpty()) return 0.0;
        if (history.size() == 1) return safe(history.get(0));
        double forecast = safe(history.get(0));
        for (int i = 1; i < history.size(); i++) {
            double value = safe(history.get(i));
            forecast = alpha * value + (1.0 - alpha) * forecast;
        }
        return forecast;
    }

    /**
     * ETS (Holt-Winters) forecast. Expects history ordered oldest -> newest.
     * Mirrors Agents/common/forecasting.py implementation to keep metrics aligned with the app behavior.
     */
    private static double etsForecast(List<Double> history, double alpha, double beta, double gamma, int period) {
        if (history == null || history.isEmpty()) return 0.0;
        if (history.size() == 1) return safe(history.get(0));

        int m = Math.max(2, period);
        int n = history.size();

        // If we don't have enough data for seasonal ETS, fall back to Holt's linear trend (or simple smoothing).
        if (n < 2 * m) {
            if (n < 2) return exponentialSmoothing(history, alpha);
            double level = safe(history.get(0));
            double trend = safe(history.get(1)) - safe(history.get(0));
            for (int i = 2; i < n; i++) {
                double y = safe(history.get(i));
                double levelPrev = level;
                level = alpha * y + (1.0 - alpha) * (level + trend);
                trend = beta * (level - levelPrev) + (1.0 - beta) * trend;
            }
            return Math.max(0.0, level + trend);
        }

        double[] seasonal = new double[m];
        int nCycles = n / m;
        for (int i = 0; i < m; i++) {
            double s = 0.0;
            for (int k = 0; k < nCycles; k++) {
                int idx = i + k * m;
                if (idx < n) s += safe(history.get(idx));
            }
            seasonal[i] = nCycles > 0 ? (s / (double) nCycles) : 0.0;
        }

        double sumFirst = 0.0;
        for (int i = 0; i < m; i++) sumFirst += safe(history.get(i));
        double sumSeasonal = 0.0;
        for (int i = 0; i < m; i++) sumSeasonal += seasonal[i];
        double level = (sumFirst / (double) m) - (sumSeasonal / (double) m);

        double trend;
        if (n >= 2 * m) {
            double sumSecond = 0.0;
            for (int i = m; i < 2 * m; i++) sumSecond += safe(history.get(i));
            trend = ((sumSecond / (double) m) - (sumFirst / (double) m)) / (double) m;
        } else {
            trend = 0.0;
        }

        for (int i = m; i < n; i++) {
            double y = safe(history.get(i));
            int si = i % m;
            double sOld = seasonal[si];
            double levelNew = alpha * (y - sOld) + (1.0 - alpha) * (level + trend);
            trend = beta * (levelNew - level) + (1.0 - beta) * trend;
            seasonal[si] = gamma * (y - levelNew) + (1.0 - gamma) * sOld;
            level = levelNew;
        }

        double nextSeasonal = seasonal[n % m];
        return Math.max(0.0, level + trend + nextSeasonal);
    }

    private static double safe(Double v) {
        if (v == null) return 0.0;
        if (Double.isNaN(v) || Double.isInfinite(v)) return 0.0;
        return v;
    }

    private static double mean(List<Double> vals) {
        if (vals == null || vals.isEmpty()) return 0.0;
        double s = 0.0;
        for (Double v : vals) s += safe(v);
        return s / (double) vals.size();
    }
}

