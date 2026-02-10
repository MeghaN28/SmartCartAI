import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography } from '../theme';

const SORT_OPTIONS = [
  { key: 'name', label: 'Name' },
  { key: 'quantity', label: 'Qty' },
  { key: 'category', label: 'Category' },
  { key: 'status', label: 'Status' },
];

export default function FilterSection({
  sortBy,
  setSortBy,
  selectedStockStatus,
  setSelectedStockStatus,
  stockStatusOptions,
}) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.container}>
      <Text style={[styles.label, { color: c.textSecondary }]}>Sort by</Text>
      <View style={styles.sortRow}>
        {SORT_OPTIONS.map(({ key, label }) => (
          <TouchableOpacity
            key={key}
            style={[
              styles.pill,
              {
                backgroundColor: sortBy === key ? c.primary : c.card,
                borderColor: sortBy === key ? c.primary : c.border,
              },
            ]}
            onPress={() => setSortBy(key)}
            activeOpacity={0.8}
          >
            <Text style={[styles.pillText, { color: sortBy === key ? '#fff' : c.text }]}>{label}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={[styles.label, { color: c.textSecondary, marginTop: spacing.md }]}>Stock status</Text>
      <View style={styles.statusRow}>
        {stockStatusOptions.map((status) => (
          <TouchableOpacity
            key={status}
            style={[
              styles.pill,
              {
                backgroundColor: selectedStockStatus === status ? c.primary : c.card,
                borderColor: selectedStockStatus === status ? c.primary : c.border,
              },
            ]}
            onPress={() => setSelectedStockStatus(status)}
            activeOpacity={0.8}
          >
            <Text style={[styles.pillText, { color: selectedStockStatus === status ? '#fff' : c.text }]}>
              {status}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginTop: spacing.md },
  label: { ...typography.label, marginBottom: spacing.xs },
  sortRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  statusRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  pill: {
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.md,
    borderRadius: radius.full,
    borderWidth: 1,
  },
  pillText: { fontSize: 13, fontWeight: '600' },
});
