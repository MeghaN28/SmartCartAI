import React from 'react';
import { View, Text, Modal, TouchableOpacity, ScrollView, StyleSheet, Dimensions } from 'react-native';
import { BarChart } from 'react-native-chart-kit';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

const chartConfig = (c) => ({
  backgroundColor: c.card,
  backgroundGradientFrom: c.card,
  backgroundGradientTo: c.card,
  color: (opacity = 1) => `rgba(16, 185, 129, ${opacity})`,
  labelColor: () => c.textSecondary,
});

export default function ItemForecastModal({ item, parsed, onClose }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  if (!item || !parsed) return null;

  const { currentStock, reorderLevel, lowStock, actions } = parsed;
  const width = Dimensions.get('window').width - spacing.lg * 4;

  const barData = {
    labels: ['Stock', 'Reorder'],
    datasets: [{ data: [currentStock, reorderLevel] }],
  };

  return (
    <Modal visible transparent animationType="fade">
      <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={onClose}>
        <View style={[styles.content, { backgroundColor: c.bg }]} onStartShouldSetResponder={() => true}>
          <View style={styles.header}>
            <Text style={[styles.title, { color: c.text }]} numberOfLines={1}>{item.name} — Summary</Text>
            <TouchableOpacity onPress={onClose} style={[styles.closeBtn, { backgroundColor: c.card }]}>
              <Text style={[styles.closeText, { color: c.text }]}>✕</Text>
            </TouchableOpacity>
          </View>

          {lowStock && (
            <View style={[styles.alert, { backgroundColor: c.danger + '20' }]}>
              <Text style={[styles.alertText, { color: c.danger }]}>
                ⚠️ {currentStock === 0 ? 'Out of Stock!' : 'Low Stock!'}
              </Text>
            </View>
          )}

          <View style={[styles.chartBox, { backgroundColor: c.card, borderColor: c.border }]}>
            <Text style={[styles.chartTitle, { color: c.text }]}>Stock vs Threshold</Text>
            <BarChart data={barData} width={width} height={180} yAxisLabel="" chartConfig={chartConfig(c)} fromZero style={styles.chart} />
          </View>

          {actions && actions.length > 0 && (
            <View style={[styles.actionsBox, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.actionsTitle, { color: c.text }]}>Recommended Actions</Text>
              {actions.map((a, idx) => (
                <Text key={idx} style={[styles.actionItem, { color: c.textSecondary }]}>• {a}</Text>
              ))}
            </View>
          )}

          <TouchableOpacity style={[styles.doneBtn, { backgroundColor: c.primary }]} onPress={onClose}>
            <Text style={styles.doneBtnText}>Close</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: spacing.lg },
  content: { borderRadius: radius.lg, padding: spacing.lg, maxHeight: '90%' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.md },
  title: { flex: 1, fontSize: 18, fontWeight: '600' },
  closeBtn: { padding: spacing.sm, borderRadius: radius.sm },
  closeText: { fontSize: 18 },
  alert: { padding: spacing.md, borderRadius: radius.md, marginBottom: spacing.md },
  alertText: { fontWeight: '600' },
  chartBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  chartTitle: { fontSize: 14, fontWeight: '600', marginBottom: spacing.sm },
  chart: { borderRadius: radius.sm },
  actionsBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  actionsTitle: { fontSize: 14, fontWeight: '600', marginBottom: spacing.sm },
  actionItem: { fontSize: 13, marginBottom: 4 },
  doneBtn: { padding: spacing.md, borderRadius: radius.md, alignItems: 'center' },
  doneBtnText: { color: '#fff', fontWeight: '600' },
});
