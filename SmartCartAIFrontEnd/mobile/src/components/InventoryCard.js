import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography, shadows } from '../theme';

export default function InventoryCard({ item, getStockStatus, statusLabels, statusColors, getDaysUntilExpiry }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const status = getStockStatus(item);
  const stockPercentage =
    item.threshold > 0 ? Math.min((item.quantity / (item.threshold * 3)) * 100, 100) : 0;
  const daysUntilExpiry = getDaysUntilExpiry ? getDaysUntilExpiry(item.expiryDate) : null;
  const expirySoon = daysUntilExpiry != null && daysUntilExpiry <= 14;
  const expired = daysUntilExpiry != null && daysUntilExpiry < 0;
  // sell_by/use_by/best_by carry different urgency: use_by is a food-safety cutoff,
  // sell_by is a retailer stocking cutoff, best_by is quality-only.
  const dateTypeLabel = { sell_by: 'Sell by', use_by: 'Use by', best_by: 'Best by' }[item.expiryDateType] || 'Expires';
  const expiryLabel = expired ? 'Expired' : `${dateTypeLabel} in ${daysUntilExpiry}d`;
  const expiryTagBg = expired ? '#f8717166' : item.expiryDateType === 'use_by' ? '#dc262633' : '#f9731633';
  const expiryTagColor = expired ? '#dc2626' : item.expiryDateType === 'use_by' ? '#dc2626' : '#f97316';
  const priceLabel = item.sellingPrice != null ? `$${Number(item.sellingPrice).toFixed(2)}` : null;

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
          {expirySoon && (
            <View style={[styles.statusTag, { backgroundColor: expiryTagBg }]}>
              <Text style={[styles.statusText, { color: expiryTagColor }]}>
                {expiryLabel}
              </Text>
            </View>
          )}
          {priceLabel && (
            <Text style={[styles.tag, { color: c.textSecondary }]}>{priceLabel}</Text>
          )}
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
    padding: spacing.lg,
    borderBottomWidth: 2,
  },
  emoji: { fontSize: 28, marginRight: spacing.md },
  miniStats: { marginRight: spacing.lg },
  miniVal: { fontSize: 20, fontWeight: '700' },
  miniLabel: { fontSize: 12, fontWeight: '500' },
  content: { padding: spacing.lg },
  title: { ...typography.subtitle, fontSize: 16, marginBottom: spacing.sm },
  tags: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.sm, flexWrap: 'wrap' },
  tag: { fontSize: 13 },
  statusTag: {
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: 4,
    borderRadius: radius.sm,
  },
  statusText: { fontSize: 12, fontWeight: '700' },
  progressWrap: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  progressLabel: { fontSize: 13 },
  progressVal: { fontSize: 13, fontWeight: '700' },
  barBg: { height: 8, borderRadius: radius.full, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: radius.full },
});
