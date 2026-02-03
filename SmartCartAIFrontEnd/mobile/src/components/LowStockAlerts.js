import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function LowStockAlerts({ lowStockAlerts }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.section}>
      <Text style={[styles.title, { color: c.text }]}>Low Stock Alerts</Text>
      {lowStockAlerts && lowStockAlerts.length > 0 ? (
        <View style={styles.grid}>
          {lowStockAlerts.map((item) => (
            <View key={item.id} style={[styles.card, { backgroundColor: c.card, borderColor: c.warning }]}>
              <Text style={styles.icon}>⚠️</Text>
              <Text style={[styles.name, { color: c.text }]}>{item.name}</Text>
              <Text style={[styles.details, { color: c.textSecondary }]}>
                Current: {item.quantity} | Threshold: {item.threshold}
              </Text>
            </View>
          ))}
        </View>
      ) : (
        <Text style={[styles.noAlerts, { color: c.textSecondary }]}>No low stock alerts.</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: spacing.lg },
  title: { fontSize: 18, fontWeight: '600', marginBottom: spacing.sm },
  grid: { gap: spacing.sm },
  card: { flexDirection: 'row', alignItems: 'center', padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  icon: { fontSize: 20, marginRight: spacing.sm },
  name: { flex: 1, fontWeight: '600' },
  details: { fontSize: 12 },
  noAlerts: { fontSize: 14, fontStyle: 'italic' },
});
