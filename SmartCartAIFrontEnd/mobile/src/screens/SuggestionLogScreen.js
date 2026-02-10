import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, RefreshControl } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';
import { API } from '../config';

export default function SuggestionLogScreen() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchSuggestions = async () => {
    try {
      const res = await fetch(API.suggestions);
      const data = await res.json();
      setSuggestions(Array.isArray(data) ? data : []);
    } catch (err) {
      setSuggestions([]);
    }
    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => {
    fetchSuggestions();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchSuggestions();
  };

  const getPriorityColor = (priority) => {
    if (priority === 'High') return c.danger;
    if (priority === 'Medium') return c.warning;
    return c.success;
  };

  const getStatusColor = (status) => {
    if (status === 'approved') return c.success;
    if (status === 'rejected') return c.danger;
    if (status === 'implemented') return c.primary;
    return c.textSecondary;
  };

  if (loading) {
    return (
      <View style={[styles.centered, { backgroundColor: c.bg }]}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={[styles.loadingText, { color: c.textSecondary }]}>Loading suggestions...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: c.bg }]}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={c.primary} />}
    >
      <Text style={[styles.title, { color: c.text }]}>Suggestion Log</Text>
      <Text style={[styles.subtitle, { color: c.textSecondary }]}>
        AI-generated recommendations for inventory management.
      </Text>

      {suggestions.length === 0 ? (
        <View style={[styles.emptyState, { backgroundColor: c.card, borderColor: c.border }]}>
          <Text style={styles.emptyIcon}>💡</Text>
          <Text style={[styles.noData, { color: c.text }]}>No suggestions yet</Text>
          <Text style={[styles.noDataSub, { color: c.textSecondary }]}>
            Ask the chatbot to analyze your inventory and generate suggestions.
          </Text>
        </View>
      ) : (
        suggestions.map((suggestion) => (
          <View key={suggestion.suggestionId} style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}>
            <View style={styles.headerRow}>
              <Text style={[styles.itemName, { color: c.text }]}>{suggestion.itemName}</Text>
              <View style={[styles.priorityBadge, { backgroundColor: getPriorityColor(suggestion.priority) + '30' }]}>
                <Text style={[styles.priorityText, { color: getPriorityColor(suggestion.priority) }]}>
                  {suggestion.priority}
                </Text>
              </View>
            </View>

            <View style={styles.row}>
              <Text style={[styles.label, { color: c.textSecondary }]}>Action</Text>
              <Text style={[styles.value, { color: c.text, fontWeight: '600' }]}>
                {suggestion.action?.toUpperCase() || 'NONE'}
              </Text>
            </View>

            {suggestion.reasoning && (
              <View style={styles.section}>
                <Text style={[styles.label, { color: c.textSecondary }]}>Reasoning</Text>
                <Text style={[styles.reasoningText, { color: c.text }]}>{suggestion.reasoning}</Text>
              </View>
            )}

            {suggestion.expectedOutcome && (
              <View style={styles.section}>
                <Text style={[styles.label, { color: c.textSecondary }]}>Expected Outcome</Text>
                <Text style={[styles.outcomeText, { color: c.text }]}>{suggestion.expectedOutcome}</Text>
              </View>
            )}

            <View style={styles.detailsGrid}>
              <View style={styles.detailItem}>
                <Text style={[styles.detailLabel, { color: c.textSecondary }]}>Current Stock</Text>
                <Text style={[styles.detailValue, { color: c.text }]}>{suggestion.currentStock || 0}</Text>
              </View>
              <View style={styles.detailItem}>
                <Text style={[styles.detailLabel, { color: c.textSecondary }]}>Min Stock</Text>
                <Text style={[styles.detailValue, { color: c.text }]}>{suggestion.minStock || 0}</Text>
              </View>
              <View style={styles.detailItem}>
                <Text style={[styles.detailLabel, { color: c.textSecondary }]}>Risk Level</Text>
                <Text style={[styles.detailValue, { color: c.text }]}>{suggestion.riskLevel || 'N/A'}</Text>
              </View>
              {suggestion.estimatedCost && (
                <View style={styles.detailItem}>
                  <Text style={[styles.detailLabel, { color: c.textSecondary }]}>Est. Cost</Text>
                  <Text style={[styles.detailValue, { color: c.text }]}>
                    ${suggestion.estimatedCost.toFixed(2)}
                  </Text>
                </View>
              )}
            </View>

            <View style={styles.footerRow}>
              <View style={[styles.statusBadge, { backgroundColor: getStatusColor(suggestion.status) + '30' }]}>
                <Text style={[styles.statusText, { color: getStatusColor(suggestion.status) }]}>
                  {suggestion.status || 'pending'}
                </Text>
              </View>
              <Text style={[styles.timestamp, { color: c.textSecondary }]}>
                {new Date(suggestion.createdAt).toLocaleString()}
              </Text>
            </View>

            {suggestion.userQuery && (
              <View style={styles.queryBox}>
                <Text style={[styles.queryLabel, { color: c.textSecondary }]}>User Query:</Text>
                <Text style={[styles.queryText, { color: c.text }]}>{suggestion.userQuery}</Text>
              </View>
            )}
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 3 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: spacing.md },
  title: { fontSize: 22, fontWeight: '700', marginBottom: spacing.xs },
  subtitle: { fontSize: 14, marginBottom: spacing.lg, lineHeight: 20 },
  emptyState: {
    padding: spacing.xxl,
    borderRadius: radius.lg,
    borderWidth: 1,
    alignItems: 'center',
  },
  emptyIcon: { fontSize: 48, marginBottom: spacing.md },
  noData: { fontSize: 17, fontWeight: '600' },
  noDataSub: { fontSize: 14, marginTop: spacing.xs, textAlign: 'center' },
  card: {
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    marginBottom: spacing.md,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  itemName: { fontSize: 16, fontWeight: '700', flex: 1 },
  priorityBadge: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.sm },
  priorityText: { fontSize: 11, fontWeight: '700' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm },
  label: { fontSize: 12 },
  value: { fontSize: 14, flex: 1, marginLeft: spacing.sm, textAlign: 'right' },
  section: { marginBottom: spacing.sm },
  reasoningText: { fontSize: 13, marginTop: 4, lineHeight: 18 },
  outcomeText: { fontSize: 13, marginTop: 4, lineHeight: 18 },
  detailsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
  },
  detailItem: {
    width: '50%',
    marginBottom: spacing.xs,
  },
  detailLabel: { fontSize: 11 },
  detailValue: { fontSize: 13, fontWeight: '600', marginTop: 2 },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: 'rgba(128, 128, 128, 0.2)',
  },
  statusBadge: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.sm },
  statusText: { fontSize: 11, fontWeight: '600' },
  timestamp: { fontSize: 11 },
  queryBox: {
    marginTop: spacing.sm,
    padding: spacing.sm,
    backgroundColor: 'rgba(128, 128, 128, 0.1)',
    borderRadius: radius.sm,
  },
  queryLabel: { fontSize: 11, marginBottom: 4 },
  queryText: { fontSize: 12, fontStyle: 'italic' },
});
