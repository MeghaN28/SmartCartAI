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
    <View style={[styles.hero, { backgroundColor: c.card, borderColor: c.border }, shadows.md]}>
      <View style={[styles.badge, { backgroundColor: c.primary + '20' }]}>
        <Text style={[styles.badgeText, { color: c.primary }]}>AI-Powered Inventory</Text>
      </View>
      <Text style={[styles.desc, { color: c.textSecondary }]}>
        Real-time tracking and AI insights for smarter stock management.
      </Text>
      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Text style={[styles.statNum, { color: c.text }]}>{stats.total}</Text>
          <Text style={[styles.statLabel, { color: c.textSecondary }]}>Total</Text>
        </View>
        <View style={styles.stat}>
          <Text style={[styles.statNum, { color: c.success }]}>{stats.inStock}</Text>
          <Text style={[styles.statLabel, { color: c.textSecondary }]}>In Stock</Text>
        </View>
        <View style={styles.stat}>
          <Text style={[styles.statNum, { color: c.warning }]}>{stats.lowStock}</Text>
          <Text style={[styles.statLabel, { color: c.textSecondary }]}>Low</Text>
        </View>
        <View style={styles.stat}>
          <Text style={[styles.statNum, { color: c.danger }]}>{stats.outOfStock}</Text>
          <Text style={[styles.statLabel, { color: c.textSecondary }]}>Out</Text>
        </View>
      </View>
      <View style={styles.buttons}>
        <TouchableOpacity
          style={[styles.btnPrimary, { backgroundColor: c.primary }]}
          onPress={() => navigation.navigate('Chatbot')}
          activeOpacity={0.85}
        >
          <Text style={styles.btnText}>Ask AI</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.btnSecondary, { backgroundColor: c.cardElevated, borderColor: c.border }]}
          onPress={() => navigation.navigate('Dashboard')}
          activeOpacity={0.85}
        >
          <Text style={[styles.btnTextSecondary, { color: c.text }]}>Dashboard</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: {
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    marginBottom: spacing.lg,
    overflow: 'hidden',
  },
  badge: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    marginBottom: spacing.sm,
  },
  badgeText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.4 },
  desc: { fontSize: 14, lineHeight: 22, marginBottom: spacing.lg },
  statsRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: spacing.lg },
  stat: { alignItems: 'center' },
  statNum: { ...typography.titleSmall, fontSize: 22 },
  statLabel: { fontSize: 11, marginTop: 2, fontWeight: '500' },
  buttons: { flexDirection: 'row', gap: spacing.sm },
  btnPrimary: {
    flex: 1,
    paddingVertical: spacing.md + 2,
    borderRadius: radius.md,
    alignItems: 'center',
  },
  btnSecondary: {
    flex: 1,
    paddingVertical: spacing.md + 2,
    borderRadius: radius.md,
    alignItems: 'center',
    borderWidth: 1,
  },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  btnTextSecondary: { fontWeight: '600', fontSize: 15 },
});
