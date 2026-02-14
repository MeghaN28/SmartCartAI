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
            style={[styles.card, { backgroundColor: c.card, borderColor: c.border }, shadows.card]}
          >
            <View style={[styles.iconWrap, { backgroundColor: color + '18' }]}>
              <Text style={styles.icon}>{icon}</Text>
            </View>
            <Text style={[styles.value, { color: c.text }]}>{stats[key]}</Text>
            <Text style={[styles.label, { color: c.textSecondary }]}>{label}</Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md, marginBottom: spacing.lg },
  card: {
    width: '47%',
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
  },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  icon: { fontSize: 22 },
  value: { ...typography.titleSmall, fontSize: 24 },
  label: { fontSize: 13, marginTop: 4, fontWeight: '500' },
});
