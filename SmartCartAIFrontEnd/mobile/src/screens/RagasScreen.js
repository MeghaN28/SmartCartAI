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
  const [runs, setRuns] = useState([]);
  const [fails, setFails] = useState([]);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
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
  line: { fontSize: 14, marginBottom: 4 },
  failItem: { marginBottom: spacing.md },
  failQuery: { fontSize: 14, fontWeight: '600', marginBottom: 2 },
  failMeta: { fontSize: 13 },
});
