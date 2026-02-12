import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, typography } from '../theme';
import InventoryCard from './InventoryCard';

export default function InventoryGrid({
  filteredAndSortedInventory,
  getStockStatus,
  statusLabels,
  statusColors,
  getDaysUntilExpiry,
}) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: c.text }]}>
        Inventory ({filteredAndSortedInventory.length})
      </Text>
      {filteredAndSortedInventory.map((item) => (
        <InventoryCard
          key={item.id}
          item={item}
          getStockStatus={getStockStatus}
          statusLabels={statusLabels}
          statusColors={statusColors}
          getDaysUntilExpiry={getDaysUntilExpiry}
        />
      ))}
      {filteredAndSortedInventory.length === 0 && (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>📋</Text>
          <Text style={[styles.emptyTitle, { color: c.text }]}>No items found</Text>
          <Text style={[styles.emptyDesc, { color: c.textSecondary }]}>
            Try adjusting your search or filters
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: spacing.sm },
  sectionTitle: { ...typography.subtitle, marginBottom: spacing.md },
  empty: { alignItems: 'center', paddingVertical: spacing.xxl * 1.5 },
  emptyIcon: { fontSize: 48, marginBottom: spacing.md },
  emptyTitle: { ...typography.subtitle, marginBottom: spacing.xs },
  emptyDesc: { fontSize: 14, color: '#64748b' },
});
