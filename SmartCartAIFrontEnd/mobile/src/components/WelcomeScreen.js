import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function WelcomeScreen({ quickQuestions, handleQuickQuestion }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={styles.container}>
      <Text style={styles.emoji}>💬</Text>
      <Text style={[styles.title, { color: c.text }]}>SmartCartAI Assistant</Text>
      <Text style={[styles.subtitle, { color: c.textSecondary }]}>How can I help you with your inventory today?</Text>
      <View style={styles.grid}>
        {quickQuestions.map((q, i) => (
          <TouchableOpacity
            key={i}
            style={[styles.suggestion, { backgroundColor: c.card, borderColor: c.border }]}
            onPress={() => handleQuickQuestion(q)}
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
  emoji: { fontSize: 48, marginBottom: spacing.md },
  title: { fontSize: 22, fontWeight: '700', marginBottom: spacing.xs },
  subtitle: { fontSize: 14, marginBottom: spacing.lg },
  grid: { width: '100%', gap: spacing.sm },
  suggestion: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  suggestionText: { fontSize: 14, textAlign: 'center' },
});
