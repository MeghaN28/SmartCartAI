import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography } from '../theme';

export default function WelcomeScreen({ quickQuestions, handleQuickQuestion }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.container}>
      <View style={[styles.iconWrap, { backgroundColor: c.primary + '18' }]}>
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
            style={[styles.suggestion, { backgroundColor: c.card, borderColor: c.border }]}
            onPress={() => handleQuickQuestion(q)}
            activeOpacity={0.8}
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
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  emoji: { fontSize: 36 },
  title: { ...typography.title, marginBottom: spacing.xs },
  subtitle: { fontSize: 15, textAlign: 'center', marginBottom: spacing.lg, lineHeight: 22 },
  promptLabel: { ...typography.label, alignSelf: 'flex-start', marginBottom: spacing.sm },
  grid: { width: '100%', gap: spacing.sm },
  suggestion: {
    padding: spacing.md + 2,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  suggestionText: { fontSize: 14, textAlign: 'left', lineHeight: 20 },
});
