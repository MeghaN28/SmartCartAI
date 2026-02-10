import React from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography } from '../theme';

export default function AddItemForm({ newItem, setNewItem, categories, handleAddItem }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={[styles.form, { backgroundColor: c.card, borderColor: c.border }]}>
      <Text style={[styles.label, { color: c.textSecondary }]}>Item name</Text>
      <TextInput
        style={[styles.input, { color: c.text, borderColor: c.border }]}
        placeholder="e.g. Olive Oil"
        placeholderTextColor={c.textMuted}
        value={newItem.name}
        onChangeText={(v) => setNewItem({ ...newItem, name: v })}
      />
      <Text style={[styles.label, { color: c.textSecondary }]}>Category</Text>
      <View style={styles.pickerRow}>
        {categories.map((cat) => (
          <TouchableOpacity
            key={cat}
            style={[
              styles.pickerOpt,
              { borderColor: c.border },
              newItem.category === cat && { backgroundColor: c.primary, borderColor: c.primary },
            ]}
            onPress={() => setNewItem({ ...newItem, category: cat })}
            activeOpacity={0.8}
          >
            <Text style={[styles.pickerOptText, { color: newItem.category === cat ? '#fff' : c.text }]}>
              {cat}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={[styles.label, { color: c.textSecondary }]}>Quantity</Text>
      <TextInput
        style={[styles.input, { color: c.text, borderColor: c.border }]}
        placeholder="0"
        placeholderTextColor={c.textMuted}
        value={newItem.quantity}
        onChangeText={(v) => setNewItem({ ...newItem, quantity: v })}
        keyboardType="numeric"
      />
      <Text style={[styles.label, { color: c.textSecondary }]}>Min threshold</Text>
      <TextInput
        style={[styles.input, { color: c.text, borderColor: c.border }]}
        placeholder="0"
        placeholderTextColor={c.textMuted}
        value={newItem.threshold}
        onChangeText={(v) => setNewItem({ ...newItem, threshold: v })}
        keyboardType="numeric"
      />
      <TouchableOpacity
        style={[styles.btn, { backgroundColor: c.primary }]}
        onPress={handleAddItem}
        activeOpacity={0.85}
      >
        <Text style={styles.btnText}>Add Item</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  form: {
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    marginBottom: spacing.lg,
  },
  label: { ...typography.label, marginBottom: spacing.xs },
  input: {
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: spacing.md,
    marginBottom: spacing.sm,
    fontSize: 16,
  },
  pickerRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.sm },
  pickerOpt: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    borderWidth: 1,
  },
  pickerOptText: { fontSize: 14, fontWeight: '600' },
  btn: {
    padding: spacing.md + 2,
    borderRadius: radius.md,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
