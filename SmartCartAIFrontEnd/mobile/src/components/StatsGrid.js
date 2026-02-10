import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography, shadows } from '../theme';

const ITEMS = [
  { label: 'Total Items', key: 'totalItems', icon: '📦' },
  { label: 'In Stock', key: 'inStock', icon: '✅' },
  { label: 'Low Stock', key: 'lowStock', icon: '⚠️' },
  { label: 'Out of Stock', key: 'outOfStock', icon: '❌' },
];

const COLOR_KEYS = { totalItems: 'primary', inStock: 'success', lowStock: 'warning', outOfStock: 'danger' };

export default function StatsGrid({ stats }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.grid}>
      {ITEMS.map(({ label, key, icon }) => {
        const colorKey = COLOR_KEYS[key];
        const color = c[colorKey];
        return (
          <View
            key={key}
            style={[styles.card, { backgroundColor: c.card, borderColor: c.border }, shadows.sm]}
          >
            <Text style={styles.icon}>{icon}</Text>
            <Text style={[styles.value, { color: c.text }]}>{stats[key]}</Text>
            <Text style={[styles.label, { color: c.textSecondary }]}>{label}</Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.lg },
  card: {
    width: '48%',
    padding: spacing.md + 2,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  icon: { fontSize: 24, marginBottom: spacing.xs },
  value: { ...typography.titleSmall, fontSize: 22 },
  label: { fontSize: 12, marginTop: 2, fontWeight: '500' },
});
