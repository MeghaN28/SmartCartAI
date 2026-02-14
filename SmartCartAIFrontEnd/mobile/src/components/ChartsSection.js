import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import { BarChart, PieChart } from 'react-native-chart-kit';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography, shadows } from '../theme';

const chartConfig = (c) => ({
  backgroundColor: c.card,
  backgroundGradientFrom: c.card,
  backgroundGradientTo: c.card,
  decimalPlaces: 0,
  color: (opacity = 1) => {
    const hex = c.primary.replace('#', '');
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  },
  labelColor: () => c.textSecondary,
});

export default function ChartsSection({ categoryChartData, statusData, colors: chartColors }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const config = chartConfig(c);
  const width = Dimensions.get('window').width - spacing.lg * 4;

  const pieData = (statusData || []).map((s) => ({
    name: s.name,
    population: s.value || 0,
    color: s.color,
  }));

  return (
    <View style={styles.section}>
      {categoryChartData && categoryChartData.length > 0 && (
        <View
          style={[
            styles.chartCard,
            { backgroundColor: c.card, borderColor: c.border },
            shadows.sm,
          ]}
        >
          <Text style={[styles.chartTitle, { color: c.text }]}>Inventory by Category</Text>
          <BarChart
            data={{
              labels: categoryChartData.map((d) => (d.name || '').slice(0, 8)),
              datasets: [{ data: categoryChartData.map((d) => d.quantity || 0) }],
            }}
            width={width}
            height={220}
            yAxisLabel=""
            chartConfig={config}
            style={styles.chart}
            fromZero
          />
        </View>
      )}
      {statusData && statusData.length > 0 && (
        <View
          style={[
            styles.chartCard,
            { backgroundColor: c.card, borderColor: c.border },
            shadows.sm,
          ]}
        >
          <Text style={[styles.chartTitle, { color: c.text }]}>Stock Status</Text>
          <PieChart
            data={pieData}
            width={width}
            height={180}
            chartConfig={config}
            accessor="population"
            backgroundColor="transparent"
            paddingLeft="0"
            absolute
            style={styles.chart}
          />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: spacing.lg },
  chartCard: {
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    marginBottom: spacing.lg,
  },
  chartTitle: { ...typography.subtitle, marginBottom: spacing.md },
  chart: { borderRadius: radius.lg },
});
