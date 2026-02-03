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
        placeholder="Search by name, category..."
        placeholderTextColor={c.textSecondary}
        value={searchTerm}
        onChangeText={setSearchTerm}
      />
      {searchTerm.length > 0 && (
        <TouchableOpacity onPress={() => setSearchTerm('')} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Text style={[styles.clear, { color: c.textSecondary }]}>✕</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  icon: { fontSize: 16, marginRight: spacing.sm },
  input: { flex: 1, paddingVertical: spacing.md, fontSize: 16 },
  clear: { fontSize: 18, padding: spacing.xs },
});
