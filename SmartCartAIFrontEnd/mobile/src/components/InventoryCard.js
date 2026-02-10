import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography, shadows } from '../theme';

export default function InventoryCard({ item, getStockStatus, statusLabels, statusColors }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const status = getStockStatus(item);
  const stockPercentage =
    item.threshold > 0 ? Math.min((item.quantity / (item.threshold * 3)) * 100, 100) : 0;

  return (
    <View
      style={[
        styles.card,
        { backgroundColor: c.card, borderColor: `${statusColors[status]}30` },
        shadows.sm,
      ]}
    >
      <View style={[styles.visual, { borderBottomColor: `${statusColors[status]}25` }]}>
        <Text style={styles.emoji}>📦</Text>
        <View style={styles.miniStats}>
          <Text style={[styles.miniVal, { color: statusColors[status] }]}>{item.quantity}</Text>
          <Text style={[styles.miniLabel, { color: c.textSecondary }]}>Qty</Text>
        </View>
        <View style={styles.miniStats}>
          <Text style={[styles.miniVal, { color: statusColors[status] }]}>{item.threshold}</Text>
          <Text style={[styles.miniLabel, { color: c.textSecondary }]}>Min</Text>
        </View>
      </View>
      <View style={styles.content}>
        <Text style={[styles.title, { color: c.text }]} numberOfLines={1}>
          {item.name}
        </Text>
        <View style={styles.tags}>
          <Text style={[styles.tag, { color: c.textSecondary }]}>{item.category}</Text>
          <View style={[styles.statusTag, { backgroundColor: `${statusColors[status]}22` }]}>
            <Text style={[styles.statusText, { color: statusColors[status] }]}>
              {statusLabels[status]}
            </Text>
          </View>
        </View>
        <View style={styles.progressWrap}>
          <Text style={[styles.progressLabel, { color: c.textSecondary }]}>Stock level</Text>
          <Text style={[styles.progressVal, { color: statusColors[status] }]}>
            {Math.round(stockPercentage)}%
          </Text>
        </View>
        <View style={[styles.barBg, { backgroundColor: c.border }]}>
          <View
            style={[
              styles.barFill,
              { width: `${stockPercentage}%`, backgroundColor: statusColors[status] },
            ]}
          />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.lg,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: spacing.md,
  },
  visual: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    borderBottomWidth: 2,
  },
  emoji: { fontSize: 26, marginRight: spacing.md },
  miniStats: { marginRight: spacing.lg },
  miniVal: { fontSize: 18, fontWeight: '700' },
  miniLabel: { fontSize: 11, fontWeight: '500' },
  content: { padding: spacing.md },
  title: { ...typography.subtitle, fontSize: 15, marginBottom: spacing.xs },
  tags: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.sm },
  tag: { fontSize: 12 },
  statusTag: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radius.sm,
  },
  statusText: { fontSize: 11, fontWeight: '700' },
  progressWrap: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  progressLabel: { fontSize: 12 },
  progressVal: { fontSize: 12, fontWeight: '700' },
  barBg: { height: 6, borderRadius: radius.full, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: radius.full },
});
