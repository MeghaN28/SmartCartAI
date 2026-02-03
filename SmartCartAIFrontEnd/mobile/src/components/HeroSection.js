import React from 'react';
import { View, Text, TouchableOpacity, Image, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function HeroSection({ stats }) {
  const navigation = useNavigation();
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={[styles.hero, { backgroundColor: c.card, borderColor: c.border }]}>
      <View style={styles.badge}>
        <Text style={[styles.badgeText, { color: c.primary }]}>AI-Powered Inventory Management</Text>
      </View>
      <Text style={[styles.desc, { color: c.textSecondary }]}>
        Intelligent inventory management with real-time tracking and AI insights.
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
        <TouchableOpacity style={[styles.btnPrimary, { backgroundColor: c.primary }]} onPress={() => navigation.navigate('Chatbot')}>
          <Text style={styles.btnText}>Ask AI</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.btnSecondary, { borderColor: c.border }]} onPress={() => navigation.navigate('Dashboard')}>
          <Text style={[styles.btnTextSecondary, { color: c.text }]}>Dashboard</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { padding: spacing.lg, borderRadius: radius.lg, borderWidth: 1, marginBottom: spacing.lg },
  badge: { marginBottom: spacing.sm },
  badgeText: { fontSize: 12, fontWeight: '600', letterSpacing: 0.5 },
  desc: { fontSize: 14, lineHeight: 20, marginBottom: spacing.md },
  statsRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: spacing.lg },
  stat: { alignItems: 'center' },
  statNum: { fontSize: 20, fontWeight: '700' },
  statLabel: { fontSize: 11, marginTop: 2 },
  buttons: { flexDirection: 'row', gap: spacing.sm },
  btnPrimary: { flex: 1, paddingVertical: spacing.md, borderRadius: radius.md, alignItems: 'center' },
  btnSecondary: { flex: 1, paddingVertical: spacing.md, borderRadius: radius.md, alignItems: 'center', borderWidth: 1 },
  btnText: { color: '#fff', fontWeight: '600' },
  btnTextSecondary: { fontWeight: '600' },
});
