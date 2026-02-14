import React from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function SearchBar({ searchTerm, setSearchTerm }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={[styles.wrapper, { backgroundColor: c.card, borderColor: c.border }]}>
      <Text style={styles.icon}>🔍</Text>
      <TextInput
        style={[styles.input, { color: c.text }]}
        placeholder="Search by name or category..."
        placeholderTextColor={c.textMuted}
        value={searchTerm}
        onChangeText={setSearchTerm}
      />
      {searchTerm.length > 0 && (
        <TouchableOpacity
          onPress={() => setSearchTerm('')}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          style={styles.clearWrap}
        >
          <Text style={[styles.clear, { color: c.textSecondary }]}>✕</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    minHeight: 52,
  },
  icon: { fontSize: 20, marginRight: spacing.sm, opacity: 0.8 },
  input: { flex: 1, paddingVertical: spacing.md, fontSize: 16 },
  clearWrap: { padding: spacing.sm },
  clear: { fontSize: 18, fontWeight: '600' },
});
