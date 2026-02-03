import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function InventoryCard({ item, getStockStatus, statusLabels, statusColors }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const status = getStockStatus(item);
  const stockPercentage = item.threshold > 0 ? Math.min((item.quantity / (item.threshold * 3)) * 100, 100) : 0;

  return (
    <View style={[styles.card, { backgroundColor: c.card, borderColor: `${statusColors[status]}40` }]}>
      <View style={[styles.visual, { borderBottomColor: `${statusColors[status]}40` }]}>
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
        <Text style={[styles.title, { color: c.text }]} numberOfLines={1}>{item.name}</Text>
        <View style={styles.tags}>
          <Text style={[styles.tag, { color: c.textSecondary }]}>{item.category}</Text>
          <View style={[styles.statusTag, { backgroundColor: `${statusColors[status]}20` }]}>
            <Text style={[styles.statusText, { color: statusColors[status] }]}>{statusLabels[status]}</Text>
          </View>
        </View>
        <View style={styles.progressWrap}>
          <Text style={[styles.progressLabel, { color: c.textSecondary }]}>Stock</Text>
          <Text style={[styles.progressVal, { color: statusColors[status] }]}>{Math.round(stockPercentage)}%</Text>
        </View>
        <View style={[styles.barBg, { backgroundColor: c.border }]}>
          <View style={[styles.barFill, { width: `${stockPercentage}%`, backgroundColor: statusColors[status] }]} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.lg, borderWidth: 1, overflow: 'hidden', marginBottom: spacing.md },
  visual: { flexDirection: 'row', alignItems: 'center', padding: spacing.md, borderBottomWidth: 2 },
  emoji: { fontSize: 24, marginRight: spacing.md },
  miniStats: { marginRight: spacing.lg },
  miniVal: { fontSize: 18, fontWeight: '700' },
  miniLabel: { fontSize: 11 },
  content: { padding: spacing.md },
  title: { fontSize: 16, fontWeight: '600', marginBottom: spacing.xs },
  tags: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.sm },
  tag: { fontSize: 12 },
  statusTag: { paddingHorizontal: spacing.sm, paddingVertical: 2, borderRadius: radius.sm },
  statusText: { fontSize: 11, fontWeight: '600' },
  progressWrap: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  progressLabel: { fontSize: 12 },
  progressVal: { fontSize: 12, fontWeight: '600' },
  barBg: { height: 6, borderRadius: 3, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 3 },
});
