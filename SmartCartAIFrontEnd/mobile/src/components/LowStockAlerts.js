import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography, shadows } from '../theme';

export default function LowStockAlerts({ lowStockAlerts }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.section}>
      <Text style={[styles.title, { color: c.text }]}>Low Stock Alerts</Text>
      {lowStockAlerts && lowStockAlerts.length > 0 ? (
        <View style={styles.grid}>
          {lowStockAlerts.map((item) => (
            <View
              key={item.id}
              style={[
                styles.card,
                { backgroundColor: c.card, borderLeftColor: c.warning, borderColor: c.border },
                shadows.card,
              ]}
            >
              <View style={[styles.iconWrap, { backgroundColor: c.warning + '22' }]}>
                <Text style={styles.icon}>⚠️</Text>
              </View>
              <View style={styles.cardContent}>
                <Text style={[styles.name, { color: c.text }]}>{item.name}</Text>
                <Text style={[styles.details, { color: c.textSecondary }]}>
                  Current: {item.quantity} · Min: {item.threshold}
                </Text>
              </View>
            </View>
          ))}
        </View>
      ) : (
        <View style={[styles.empty, { backgroundColor: c.card, borderColor: c.border }]}>
          <Text style={[styles.noAlerts, { color: c.textSecondary }]}>No low stock alerts</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: spacing.lg },
  title: { ...typography.subtitle, marginBottom: spacing.md },
  grid: { gap: spacing.md },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderLeftWidth: 5,
  },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  icon: { fontSize: 22 },
  cardContent: { flex: 1 },
  name: { fontWeight: '600', fontSize: 16 },
  details: { fontSize: 13, marginTop: 4 },
  empty: {
    padding: spacing.xl,
    borderRadius: radius.lg,
    borderWidth: 1,
  },
  noAlerts: { fontSize: 15, fontStyle: 'italic', textAlign: 'center' },
});
