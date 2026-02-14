import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, RefreshControl, TouchableOpacity, Alert, Platform } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';
import { API } from '../config';
import { stripMarkdown } from '../utils/stripMarkdown';

export default function SuggestionLogScreen() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [bulkDeleting, setBulkDeleting] = useState(false);

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

  const performDelete = async (suggestion) => {
    setDeletingId(suggestion.suggestionId);
    try {
      const res = await fetch(API.deleteSuggestion(suggestion.suggestionId), { method: 'DELETE' });
      if (res.ok || res.status === 204) {
        setSuggestions((prev) => prev.filter((s) => s.suggestionId !== suggestion.suggestionId));
      } else {
        const msg = 'Could not delete suggestion. Please try again.';
        if (Platform.OS === 'web') window.alert(msg);
        else Alert.alert('Error', msg);
      }
    } catch (err) {
      const msg = 'Could not delete suggestion. Please try again.';
      if (Platform.OS === 'web') window.alert(msg);
      else Alert.alert('Error', msg);
    } finally {
      setDeletingId(null);
    }
  };

  const handleDelete = (suggestion) => {
    const message = `Remove suggestion for "${suggestion.itemName || 'this item'}"? This cannot be undone.`;
    if (Platform.OS === 'web') {
      if (window.confirm(message)) performDelete(suggestion);
    } else {
      Alert.alert('Delete suggestion', message, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => performDelete(suggestion) },
      ]);
    }
  };

  const toggleSelect = (suggestionId) => {
    setSelectedIds((prev) =>
      prev.includes(suggestionId) ? prev.filter((id) => id !== suggestionId) : [...prev, suggestionId]
    );
  };

  const selectAll = () => {
    if (selectedIds.length === suggestions.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(suggestions.map((s) => s.suggestionId));
    }
  };

  const performBulkDelete = () => {
    if (selectedIds.length === 0) return;
    const message = `Delete ${selectedIds.length} selected suggestion(s)? This cannot be undone.`;
    if (Platform.OS === 'web') {
      if (window.confirm(message)) doBulkDelete();
    } else {
      Alert.alert('Delete selected', message, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: doBulkDelete },
      ]);
    }
  };

  const doBulkDelete = async () => {
    setBulkDeleting(true);
    const idsToDelete = [...selectedIds];
    const failed = [];
    for (const id of idsToDelete) {
      try {
        const res = await fetch(API.deleteSuggestion(id), { method: 'DELETE' });
        if (!res.ok && res.status !== 204) failed.push(id);
      } catch (_) {
        failed.push(id);
      }
    }
    setSuggestions((prev) => prev.filter((s) => !idsToDelete.includes(s.suggestionId)));
    setSelectedIds([]);
    setBulkDeleting(false);
    if (failed.length > 0) {
      const msg = `${failed.length} suggestion(s) could not be deleted.`;
      if (Platform.OS === 'web') window.alert(msg);
      else Alert.alert('Error', msg);
    }
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
      <Text style={[styles.title, { color: c.text }]}>Suggestions</Text>
      <Text style={[styles.subtitle, { color: c.textSecondary }]}>
        AI-generated recommendations for your inventory.
      </Text>

      {suggestions.length > 0 && (
        <View style={[styles.toolbar, { backgroundColor: c.card, borderColor: c.border }]}>
          <TouchableOpacity
            style={[styles.selectAllBtn, { borderColor: c.border }]}
            onPress={selectAll}
            activeOpacity={0.85}
          >
            <Text style={[styles.checkbox, { color: c.text }]}>
              {selectedIds.length === suggestions.length ? '☑' : '☐'}
            </Text>
            <Text style={[styles.selectAllText, { color: c.text }]}>
              {selectedIds.length === suggestions.length ? 'Deselect all' : 'Select all'}
            </Text>
          </TouchableOpacity>
          {selectedIds.length > 0 && (
            <TouchableOpacity
              style={[styles.deleteSelectedBtn, { backgroundColor: c.danger }]}
              onPress={performBulkDelete}
              disabled={bulkDeleting}
              activeOpacity={0.85}
            >
              <Text style={styles.deleteSelectedText}>
                {bulkDeleting ? 'Deleting…' : `Delete selected (${selectedIds.length})`}
              </Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {suggestions.length === 0 ? (
        <View style={[styles.emptyState, { backgroundColor: c.card, borderColor: c.border }]}>
          <View style={[styles.emptyIconWrap, { backgroundColor: c.primary + '18' }]}>
            <Text style={styles.emptyIcon}>💡</Text>
          </View>
          <Text style={[styles.noData, { color: c.text }]}>No suggestions yet</Text>
          <Text style={[styles.noDataSub, { color: c.textSecondary }]}>
            Ask the chatbot to analyze your inventory and generate suggestions.
          </Text>
        </View>
      ) : (
        suggestions.map((suggestion) => {
          const isSelected = selectedIds.includes(suggestion.suggestionId);
          return (
          <View
            key={suggestion.suggestionId}
            style={[
              styles.card,
              { backgroundColor: c.card, borderColor: isSelected ? c.primary : c.border, borderWidth: isSelected ? 2 : 1 },
            ]}
          >
            <View style={styles.headerRow}>
              <TouchableOpacity
                style={styles.cardSelectWrap}
                onPress={() => toggleSelect(suggestion.suggestionId)}
                activeOpacity={0.8}
              >
                <Text style={[styles.checkbox, { color: c.text }]}>{isSelected ? '☑' : '☐'}</Text>
                <Text style={[styles.itemName, { color: c.text }]}>{suggestion.itemName}</Text>
              </TouchableOpacity>
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
                <Text style={[styles.reasoningText, { color: c.text }]}>{stripMarkdown(suggestion.reasoning)}</Text>
              </View>
            )}

            {suggestion.expectedOutcome && (
              <View style={styles.section}>
                <Text style={[styles.label, { color: c.textSecondary }]}>Expected Outcome</Text>
                <Text style={[styles.outcomeText, { color: c.text }]}>{stripMarkdown(suggestion.expectedOutcome)}</Text>
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

            <TouchableOpacity
              style={[styles.deleteBtn, { backgroundColor: c.danger + '20', borderColor: c.danger }]}
              onPress={() => handleDelete(suggestion)}
              disabled={deletingId === suggestion.suggestionId}
              activeOpacity={0.85}
            >
              <Text style={[styles.deleteBtnText, { color: c.danger }]}>
                {deletingId === suggestion.suggestionId ? 'Deleting…' : 'Delete suggestion'}
              </Text>
            </TouchableOpacity>
          </View>
          );
        })
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 3 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: spacing.md },
  title: { fontSize: 26, fontWeight: '700', marginBottom: spacing.xs },
  subtitle: { fontSize: 15, marginBottom: spacing.lg, lineHeight: 22 },
  toolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  selectAllBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  checkbox: { fontSize: 18, marginRight: spacing.sm },
  selectAllText: { fontSize: 15, fontWeight: '600' },
  deleteSelectedBtn: {
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
  },
  deleteSelectedText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  cardSelectWrap: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  emptyState: {
    padding: spacing.xxl,
    borderRadius: radius.xl,
    borderWidth: 1,
    alignItems: 'center',
  },
  emptyIconWrap: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  emptyIcon: { fontSize: 36 },
  noData: { fontSize: 18, fontWeight: '600' },
  noDataSub: { fontSize: 15, marginTop: spacing.sm, textAlign: 'center', paddingHorizontal: spacing.lg },
  card: {
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    marginBottom: spacing.lg,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  itemName: { fontSize: 17, fontWeight: '700', flex: 1 },
  priorityBadge: { paddingHorizontal: spacing.sm + 2, paddingVertical: 6, borderRadius: radius.sm },
  priorityText: { fontSize: 12, fontWeight: '700' },
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
  deleteBtn: {
    marginTop: spacing.md,
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: 'center',
  },
  deleteBtnText: { fontSize: 14, fontWeight: '600' },
});
