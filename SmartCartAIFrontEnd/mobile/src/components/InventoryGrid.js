import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing } from '../theme';
import InventoryCard from './InventoryCard';

export default function InventoryGrid({ filteredAndSortedInventory, getStockStatus, statusLabels, statusColors }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: c.text }]}>
        Inventory Items ({filteredAndSortedInventory.length})
      </Text>
      {filteredAndSortedInventory.map((item) => (
        <InventoryCard
          key={item.id}
          item={item}
          getStockStatus={getStockStatus}
          statusLabels={statusLabels}
          statusColors={statusColors}
        />
      ))}
      {filteredAndSortedInventory.length === 0 && (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>🔍</Text>
          <Text style={[styles.emptyTitle, { color: c.text }]}>No items found</Text>
          <Text style={[styles.emptyDesc, { color: c.textSecondary }]}>Adjust search or filters</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: spacing.sm },
  sectionTitle: { fontSize: 18, fontWeight: '600', marginBottom: spacing.md },
  empty: { alignItems: 'center', paddingVertical: spacing.xl * 2 },
  emptyIcon: { fontSize: 48, marginBottom: spacing.md },
  emptyTitle: { fontSize: 18, fontWeight: '600' },
  emptyDesc: { fontSize: 14, marginTop: spacing.xs },
});
