import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import { API } from '../config';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function RagasScreen() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [etsError, setEtsError] = useState(null);
  const [runs, setRuns] = useState([]);
  const [fails, setFails] = useState([]);
  const [ets, setEts] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      setEtsError(null);
      const [runsRes, failRes] = await Promise.all([
        fetch(API.ragasRuns),
        fetch(API.ragasFailures),
      ]);
      const runsData = await runsRes.json().catch(() => []);
      const failData = await failRes.json().catch(() => []);
      if (!runsRes.ok) throw new Error('Could not load RAGAS runs');
      if (!failRes.ok) throw new Error('Could not load RAGAS failures');
      setRuns(Array.isArray(runsData) ? runsData : []);
      setFails(Array.isArray(failData) ? failData : []);

      // ETS metrics are optional; don't fail the whole screen if unavailable.
      try {
        const etsRes = await fetch(API.etsMetrics);
        const etsData = await etsRes.json().catch(() => null);
        if (!etsRes.ok) throw new Error('Could not load ETS metrics');
        setEts(etsData && typeof etsData === 'object' ? etsData : null);
      } catch (e) {
        setEts(null);
        setEtsError(e.message || 'ETS metrics unavailable');
      }
    } catch (e) {
      setError(e.message || 'RAGAS metrics unavailable');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const latest = runs[0] || null;
  const fmt = (v) => {
    if (v === null || v === undefined) return '-';
    const n = Number(v);
    if (!Number.isFinite(n)) return '-';
    return n.toFixed(4);
  };
  const fmt2 = (v) => {
    if (v === null || v === undefined) return '-';
    const n = Number(v);
    if (!Number.isFinite(n)) return '-';
    return n.toFixed(2);
  };
  const etsCls = ets?.classification || null;
  const etsErr = ets?.forecastError || null;
  const etsBases = ets?.baselines || null;
  const naive = etsBases?.naive || null;
  const sma = etsBases?.movingAverage || null;
  const ema = etsBases?.ema || null;

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: c.bg }]}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={[styles.title, { color: c.text }]}>RAGAS Evaluation</Text>
      <Text style={[styles.subtitle, { color: c.textSecondary }]}>Admin-only quality dashboard for LLM evaluations</Text>

      {loading ? <Text style={[styles.msg, { color: c.textSecondary }]}>Loading...</Text> : null}
      {error ? <Text style={[styles.msg, { color: c.danger }]}>{error}</Text> : null}

      {latest ? (
        <View style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}>
          <Text style={[styles.cardTitle, { color: c.text }]}>Latest Run</Text>
          <Text style={[styles.line, { color: c.textSecondary }]}>Label: {latest.runLabel || '-'}</Text>
          <Text style={[styles.line, { color: c.textSecondary }]}>Status: {latest.status || '-'}</Text>
          <Text style={[styles.line, { color: c.textSecondary }]}>Cases: {latest.totalCases ?? 0}</Text>
          <Text style={[styles.line, { color: c.textSecondary }]}>Pass/Fail: {latest.passCount ?? 0} / {latest.failCount ?? 0}</Text>
          <Text style={[styles.line, { color: c.textSecondary }]}>Overall: {fmt(latest.avgOverallScore)}</Text>
          <Text style={[styles.line, { color: c.textSecondary }]}>Faithfulness: {fmt(latest.avgFaithfulness)}</Text>
          <Text style={[styles.line, { color: c.textSecondary }]}>Relevancy: {fmt(latest.avgAnswerRelevancy)}</Text>
        </View>
      ) : null}

      <View style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}>
        <Text style={[styles.cardTitle, { color: c.text }]}>Demand Forecast Evaluation</Text>
        <Text style={[styles.line, { color: c.textSecondary, fontStyle: 'italic' }]}>
          Primary: MAE, RMSE, WAPE. Classification (F1/confusion) is for research comparison only.
        </Text>
        {etsError ? <Text style={[styles.msg, { color: c.danger }]}>{etsError}</Text> : null}
        {!ets && !etsError ? (
          <Text style={[styles.line, { color: c.textSecondary }]}>No ETS metrics available.</Text>
        ) : null}
        {ets ? (
          <>
            <Text style={[styles.line, { color: c.textSecondary }]}>Lookback days: {ets.lookbackDays ?? '-'}</Text>
            <Text style={[styles.line, { color: c.textSecondary }]}>Window days: {ets.windowDays ?? '-'}</Text>
            <Text style={[styles.line, { color: c.textSecondary }]}>Items used: {ets.itemsUsed ?? 0}</Text>
            <Text style={[styles.line, { color: c.textSecondary }]}>Samples: {ets.samples ?? 0}</Text>
            <Text style={[styles.sectionTitle, { color: c.text }]}>ETS</Text>
            <Text style={[styles.line, { color: c.textSecondary }]}>F1: {fmt(etsCls?.f1)} | Precision: {fmt(etsCls?.precision)} | Recall: {fmt(etsCls?.recall)} | Acc: {fmt(etsCls?.accuracy)}</Text>
            <Text style={[styles.line, { color: c.textSecondary }]}>MAE: {fmt2(etsErr?.mae)} | RMSE: {fmt2(etsErr?.rmse)}</Text>
            <Text style={[styles.line, { color: c.textSecondary }]}>WAPE: {fmt(etsErr?.wape)} | sMAPE: {fmt(etsErr?.smape)} | MAPE: {fmt(etsErr?.mape)}</Text>

            {naive ? (
              <>
                <Text style={[styles.sectionTitle, { color: c.text }]}>Baseline (Naive)</Text>
                <Text style={[styles.line, { color: c.textSecondary }]}>F1: {fmt(naive.classification?.f1)} | Precision: {fmt(naive.classification?.precision)} | Recall: {fmt(naive.classification?.recall)} | Acc: {fmt(naive.classification?.accuracy)}</Text>
                <Text style={[styles.line, { color: c.textSecondary }]}>MAE: {fmt2(naive.forecastError?.mae)} | RMSE: {fmt2(naive.forecastError?.rmse)}</Text>
                <Text style={[styles.line, { color: c.textSecondary }]}>WAPE: {fmt(naive.forecastError?.wape)} | sMAPE: {fmt(naive.forecastError?.smape)}</Text>
              </>
            ) : null}

            {sma ? (
              <>
                <Text style={[styles.sectionTitle, { color: c.text }]}>Baseline (Moving Avg)</Text>
                <Text style={[styles.line, { color: c.textSecondary }]}>F1: {fmt(sma.classification?.f1)} | Precision: {fmt(sma.classification?.precision)} | Recall: {fmt(sma.classification?.recall)} | Acc: {fmt(sma.classification?.accuracy)}</Text>
                <Text style={[styles.line, { color: c.textSecondary }]}>MAE: {fmt2(sma.forecastError?.mae)} | RMSE: {fmt2(sma.forecastError?.rmse)}</Text>
                <Text style={[styles.line, { color: c.textSecondary }]}>WAPE: {fmt(sma.forecastError?.wape)} | sMAPE: {fmt(sma.forecastError?.smape)}</Text>
              </>
            ) : null}

            {ema ? (
              <>
                <Text style={[styles.sectionTitle, { color: c.text }]}>App default (EMA)</Text>
                <Text style={[styles.line, { color: c.textSecondary }]}>F1: {fmt(ema.classification?.f1)} | Precision: {fmt(ema.classification?.precision)} | Recall: {fmt(ema.classification?.recall)} | Acc: {fmt(ema.classification?.accuracy)}</Text>
                <Text style={[styles.line, { color: c.textSecondary }]}>MAE: {fmt2(ema.forecastError?.mae)} | RMSE: {fmt2(ema.forecastError?.rmse)}</Text>
                <Text style={[styles.line, { color: c.textSecondary }]}>WAPE: {fmt(ema.forecastError?.wape)} | sMAPE: {fmt(ema.forecastError?.smape)}</Text>
              </>
            ) : null}
          </>
        ) : null}
      </View>

      <View style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}>
        <Text style={[styles.cardTitle, { color: c.text }]}>Recent Failed Cases</Text>
        {fails.length === 0 ? (
          <Text style={[styles.line, { color: c.textSecondary }]}>No failed cases in latest results.</Text>
        ) : (
          fails.slice(0, 20).map((f, idx) => (
            <View key={`${f.runId || 'r'}-${f.caseId || idx}`} style={styles.failItem}>
              <Text style={[styles.failQuery, { color: c.text }]}>{f.userQuery || '(no query)'}</Text>
              <Text style={[styles.failMeta, { color: c.textSecondary }]}>
                score {fmt(f.overallScore)} | faithfulness {fmt(f.faithfulness)} | relevancy {fmt(f.answerRelevancy)}
              </Text>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: spacing.lg, paddingBottom: spacing.xl },
  title: { fontSize: 24, fontWeight: '700' },
  subtitle: { marginTop: 4, marginBottom: spacing.lg, fontSize: 14 },
  msg: { marginVertical: spacing.sm, fontSize: 14 },
  card: { borderWidth: 1, borderRadius: radius.lg, padding: spacing.md, marginBottom: spacing.lg },
  cardTitle: { fontSize: 17, fontWeight: '700', marginBottom: spacing.sm },
  sectionTitle: { fontSize: 14, fontWeight: '700', marginTop: spacing.sm, marginBottom: 4 },
  line: { fontSize: 14, marginBottom: 4 },
  failItem: { marginBottom: spacing.md },
  failQuery: { fontSize: 14, fontWeight: '600', marginBottom: 2 },
  failMeta: { fontSize: 13 },
});
