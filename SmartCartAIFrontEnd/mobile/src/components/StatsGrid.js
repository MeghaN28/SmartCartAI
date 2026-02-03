import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function StatsGrid({ stats }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  const items = [
    { label: 'Total Items', value: stats.totalItems, icon: '📦', color: c.primary },
    { label: 'In Stock', value: stats.inStock, icon: '✅', color: c.success },
    { label: 'Low Stock', value: stats.lowStock, icon: '⚠️', color: c.warning },
    { label: 'Out of Stock', value: stats.outOfStock, icon: '❌', color: c.danger },
  ];

  return (
    <View style={styles.grid}>
      {items.map((item) => (
        <View key={item.label} style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}>
          <Text style={styles.icon}>{item.icon}</Text>
          <Text style={[styles.value, { color: c.text }]}>{item.value}</Text>
          <Text style={[styles.label, { color: c.textSecondary }]}>{item.label}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.lg },
  card: { width: '48%', padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  icon: { fontSize: 24, marginBottom: spacing.xs },
  value: { fontSize: 22, fontWeight: '700' },
  label: { fontSize: 12, marginTop: 2 },
});
