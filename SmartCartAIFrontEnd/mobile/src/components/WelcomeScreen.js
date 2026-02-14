import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography, shadows } from '../theme';

export default function WelcomeScreen({ quickQuestions, handleQuickQuestion }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.container}>
      <View style={[styles.iconWrap, { backgroundColor: c.primary + '20' }]}>
        <Text style={styles.emoji}>💬</Text>
      </View>
      <Text style={[styles.title, { color: c.text }]}>SmartCartAI Assistant</Text>
      <Text style={[styles.subtitle, { color: c.textSecondary }]}>
        Ask about stock levels, item details, or search your inventory.
      </Text>
      <Text style={[styles.promptLabel, { color: c.textSecondary }]}>Quick questions</Text>
      <View style={styles.grid}>
        {quickQuestions.map((q, i) => (
          <TouchableOpacity
            key={i}
            style={[styles.suggestion, { backgroundColor: c.card, borderColor: c.border }, shadows.sm]}
            onPress={() => handleQuickQuestion(q)}
            activeOpacity={0.85}
          >
            <Text style={[styles.suggestionText, { color: c.text }]}>{q}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', padding: spacing.xl },
  iconWrap: {
    width: 80,
    height: 80,
    borderRadius: 40,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  emoji: { fontSize: 40 },
  title: { ...typography.title, marginBottom: spacing.sm, textAlign: 'center' },
  subtitle: { fontSize: 16, textAlign: 'center', marginBottom: spacing.xl, lineHeight: 24, paddingHorizontal: spacing.lg },
  promptLabel: { ...typography.label, alignSelf: 'flex-start', marginBottom: spacing.sm },
  grid: { width: '100%', gap: spacing.md },
  suggestion: {
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
  },
  suggestionText: { fontSize: 15, textAlign: 'left', lineHeight: 22 },
});
