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

  const { currentStock, reorderLevel, lowStock, actions, recommendation, priority, reasoning, expectedOutcome, riskAssessment, costImpact } = parsed;
  const width = Dimensions.get('window').width - spacing.lg * 4;

  const barData = {
    labels: ['Stock', 'Reorder'],
    datasets: [{ data: [currentStock, reorderLevel] }],
  };

  const priorityColor = priority === 'High' ? c.danger : priority === 'Medium' ? c.warning : c.success;

  return (
    <Modal visible transparent animationType="fade">
      <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={onClose}>
        <ScrollView style={[styles.content, { backgroundColor: c.bg }]} onStartShouldSetResponder={() => true}>
          <View style={styles.header}>
            <Text style={[styles.title, { color: c.text }]} numberOfLines={1}>{item.name} — Recommendation</Text>
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

          {recommendation && (
            <View style={[styles.recommendationBox, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.sectionTitle, { color: c.text }]}>Recommended Action</Text>
              <View style={styles.recommendationRow}>
                <Text style={[styles.recommendationAction, { color: c.text }]}>{recommendation.toUpperCase()}</Text>
                {priority && (
                  <View style={[styles.priorityBadge, { backgroundColor: priorityColor + '30' }]}>
                    <Text style={[styles.priorityText, { color: priorityColor }]}>{priority} Priority</Text>
                  </View>
                )}
              </View>
            </View>
          )}

          <View style={[styles.chartBox, { backgroundColor: c.card, borderColor: c.border }]}>
            <Text style={[styles.chartTitle, { color: c.text }]}>Stock vs Threshold</Text>
            <BarChart data={barData} width={width} height={180} yAxisLabel="" chartConfig={chartConfig(c)} fromZero style={styles.chart} />
          </View>

          {reasoning && (
            <View style={[styles.reasoningBox, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.sectionTitle, { color: c.text }]}>Reasoning</Text>
              <Text style={[styles.reasoningText, { color: c.textSecondary }]}>{reasoning}</Text>
            </View>
          )}

          {expectedOutcome && (
            <View style={[styles.outcomeBox, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.sectionTitle, { color: c.text }]}>Expected Outcome</Text>
              <Text style={[styles.outcomeText, { color: c.textSecondary }]}>{expectedOutcome}</Text>
            </View>
          )}

          {riskAssessment && riskAssessment.risk_level && (
            <View style={[styles.riskBox, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.sectionTitle, { color: c.text }]}>Risk Assessment</Text>
              <Text style={[styles.riskLevel, { color: riskAssessment.risk_level === 'critical' || riskAssessment.risk_level === 'high' ? c.danger : c.textSecondary }]}>
                Risk Level: {riskAssessment.risk_level.toUpperCase()}
              </Text>
              {riskAssessment.risk_factors && riskAssessment.risk_factors.length > 0 && (
                <View style={styles.riskFactors}>
                  {riskAssessment.risk_factors.slice(0, 3).map((factor, idx) => (
                    <Text key={idx} style={[styles.riskFactor, { color: c.textSecondary }]}>
                      • {factor.description || factor.factor}
                    </Text>
                  ))}
                </View>
              )}
            </View>
          )}

          {costImpact && costImpact.estimated_cost !== undefined && (
            <View style={[styles.costBox, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.sectionTitle, { color: c.text }]}>Cost Impact</Text>
              <Text style={[styles.costText, { color: c.textSecondary }]}>
                Estimated Cost: ${costImpact.estimated_cost.toFixed(2)}
              </Text>
              <Text style={[styles.budgetText, { color: costImpact.within_budget ? c.success : c.danger }]}>
                {costImpact.within_budget ? '✓ Within Budget' : '✗ Exceeds Budget'}
              </Text>
            </View>
          )}

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
        </ScrollView>
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
  recommendationBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  recommendationRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: spacing.sm },
  recommendationAction: { fontSize: 16, fontWeight: '700', textTransform: 'uppercase' },
  priorityBadge: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.sm },
  priorityText: { fontSize: 12, fontWeight: '600' },
  chartBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  chartTitle: { fontSize: 14, fontWeight: '600', marginBottom: spacing.sm },
  chart: { borderRadius: radius.sm },
  sectionTitle: { fontSize: 14, fontWeight: '600', marginBottom: spacing.sm },
  reasoningBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  reasoningText: { fontSize: 13, lineHeight: 20 },
  outcomeBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  outcomeText: { fontSize: 13, lineHeight: 20 },
  riskBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  riskLevel: { fontSize: 14, fontWeight: '600', marginBottom: spacing.sm },
  riskFactors: { marginTop: spacing.sm },
  riskFactor: { fontSize: 12, marginBottom: 4 },
  costBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  costText: { fontSize: 14, fontWeight: '600', marginBottom: spacing.xs },
  budgetText: { fontSize: 13 },
  actionsBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  actionsTitle: { fontSize: 14, fontWeight: '600', marginBottom: spacing.sm },
  actionItem: { fontSize: 13, marginBottom: 4 },
  doneBtn: { padding: spacing.md, borderRadius: radius.md, alignItems: 'center', marginTop: spacing.sm },
  doneBtnText: { color: '#fff', fontWeight: '600' },
});
