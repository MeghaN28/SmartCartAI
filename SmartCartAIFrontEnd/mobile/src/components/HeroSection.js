import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography, shadows } from '../theme';

export default function HeroSection({ stats }) {
  const navigation = useNavigation();
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={[styles.hero, { backgroundColor: c.card, borderColor: c.border }, shadows.card]}>
      <View style={[styles.badge, { backgroundColor: c.primary + '18' }]}>
        <Text style={[styles.badgeText, { color: c.primary }]}>AI-Powered</Text>
      </View>
      <Text style={[styles.heading, { color: c.text }]}>Inventory at a glance</Text>
      <Text style={[styles.desc, { color: c.textSecondary }]}>
        Real-time tracking and AI insights for smarter stock management.
      </Text>
      <View style={[styles.statsRow, { backgroundColor: c.bgSecondary }]}>
        <View style={styles.stat}>
          <Text style={[styles.statNum, { color: c.text }]}>{stats.total}</Text>
          <Text style={[styles.statLabel, { color: c.textSecondary }]}>Total</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.stat}>
          <Text style={[styles.statNum, { color: c.success }]}>{stats.inStock}</Text>
          <Text style={[styles.statLabel, { color: c.textSecondary }]}>In Stock</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.stat}>
          <Text style={[styles.statNum, { color: c.warning }]}>{stats.lowStock}</Text>
          <Text style={[styles.statLabel, { color: c.textSecondary }]}>Low</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.stat}>
          <Text style={[styles.statNum, { color: c.danger }]}>{stats.outOfStock}</Text>
          <Text style={[styles.statLabel, { color: c.textSecondary }]}>Out</Text>
        </View>
      </View>
      <View style={styles.buttons}>
        <TouchableOpacity
          style={[styles.btnPrimary, { backgroundColor: c.primary }]}
          onPress={() => navigation.navigate('Chatbot')}
          activeOpacity={0.88}
        >
          <Text style={styles.btnText}>Ask AI</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.btnSecondary, { backgroundColor: 'transparent', borderColor: c.border }]}
          onPress={() => navigation.navigate('Dashboard')}
          activeOpacity={0.88}
        >
          <Text style={[styles.btnTextSecondary, { color: c.text }]}>Dashboard</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: {
    padding: spacing.xl,
    borderRadius: radius.xl,
    borderWidth: 1,
    marginBottom: spacing.lg,
    overflow: 'hidden',
  },
  badge: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: radius.full,
    marginBottom: spacing.sm,
  },
  badgeText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.5 },
  heading: { ...typography.title, fontSize: 22, marginBottom: spacing.xs },
  desc: { fontSize: 15, lineHeight: 22, marginBottom: spacing.lg },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.lg,
    marginBottom: spacing.lg,
  },
  stat: { alignItems: 'center', flex: 1 },
  statDivider: { width: 1, height: 32, backgroundColor: 'rgba(128,128,128,0.25)', borderRadius: 1 },
  statNum: { ...typography.titleSmall, fontSize: 24 },
  statLabel: { fontSize: 12, marginTop: 4, fontWeight: '500' },
  buttons: { flexDirection: 'row', gap: spacing.md },
  btnPrimary: {
    flex: 1,
    paddingVertical: spacing.md + 4,
    borderRadius: radius.lg,
    alignItems: 'center',
  },
  btnSecondary: {
    flex: 1,
    paddingVertical: spacing.md + 4,
    borderRadius: radius.lg,
    alignItems: 'center',
    borderWidth: 1.5,
  },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  btnTextSecondary: { fontWeight: '600', fontSize: 16 },
});
