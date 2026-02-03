import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function FilterSection({ sortBy, setSortBy, selectedStockStatus, setSelectedStockStatus, stockStatusOptions }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.container}>
      <Text style={[styles.label, { color: c.textSecondary }]}>Sort By</Text>
      <View style={styles.sortRow}>
        {['name', 'quantity', 'category', 'status'].map((key) => (
          <TouchableOpacity
            key={key}
            style={[styles.sortBtn, { backgroundColor: sortBy === key ? c.primary : c.card, borderColor: c.border }]}
            onPress={() => setSortBy(key)}
          >
            <Text style={[styles.sortBtnText, { color: sortBy === key ? '#fff' : c.text }]}>
              {key === 'name' ? 'Name' : key === 'quantity' ? 'Qty' : key === 'category' ? 'Category' : 'Status'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={[styles.label, { color: c.textSecondary, marginTop: spacing.md }]}>Stock Status</Text>
      <View style={styles.statusRow}>
        {stockStatusOptions.map((status) => (
          <TouchableOpacity
            key={status}
            style={[
              styles.statusBtn,
              { backgroundColor: selectedStockStatus === status ? c.primary : c.card, borderColor: c.border },
            ]}
            onPress={() => setSelectedStockStatus(status)}
          >
            <Text style={[styles.statusBtnText, { color: selectedStockStatus === status ? '#fff' : c.text }]}>{status}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginTop: spacing.md },
  label: { fontSize: 12, fontWeight: '600', marginBottom: spacing.xs },
  sortRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  sortBtn: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: radius.sm, borderWidth: 1 },
  sortBtnText: { fontSize: 13 },
  statusRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  statusBtn: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: radius.sm, borderWidth: 1 },
  statusBtnText: { fontSize: 12 },
});
