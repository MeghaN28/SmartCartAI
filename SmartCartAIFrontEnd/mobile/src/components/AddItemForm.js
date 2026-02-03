import React from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function AddItemForm({ newItem, setNewItem, categories, handleAddItem }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={[styles.form, { backgroundColor: c.card, borderColor: c.border }]}>
      <TextInput
        style={[styles.input, { color: c.text, borderColor: c.border }]}
        placeholder="Item Name"
        placeholderTextColor={c.textSecondary}
        value={newItem.name}
        onChangeText={(v) => setNewItem({ ...newItem, name: v })}
      />
      <View style={[styles.pickerWrap, { borderColor: c.border }]}>
        <Text style={[styles.pickerLabel, { color: c.textSecondary }]}>Category</Text>
        <View style={styles.pickerRow}>
          {categories.map((cat) => (
            <TouchableOpacity
              key={cat}
              style={[styles.pickerOpt, newItem.category === cat && { backgroundColor: c.primary }]}
              onPress={() => setNewItem({ ...newItem, category: cat })}
            >
              <Text style={[styles.pickerOptText, { color: newItem.category === cat ? '#fff' : c.text }]}>{cat}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
      <TextInput
        style={[styles.input, { color: c.text, borderColor: c.border }]}
        placeholder="Quantity"
        placeholderTextColor={c.textSecondary}
        value={newItem.quantity}
        onChangeText={(v) => setNewItem({ ...newItem, quantity: v })}
        keyboardType="numeric"
      />
      <TextInput
        style={[styles.input, { color: c.text, borderColor: c.border }]}
        placeholder="Threshold"
        placeholderTextColor={c.textSecondary}
        value={newItem.threshold}
        onChangeText={(v) => setNewItem({ ...newItem, threshold: v })}
        keyboardType="numeric"
      />
      <TouchableOpacity style={[styles.btn, { backgroundColor: c.primary }]} onPress={handleAddItem}>
        <Text style={styles.btnText}>Add Item</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  form: { padding: spacing.md, borderRadius: radius.lg, borderWidth: 1, marginBottom: spacing.lg },
  input: { borderWidth: 1, borderRadius: radius.sm, padding: spacing.md, marginBottom: spacing.sm },
  pickerWrap: { marginBottom: spacing.sm },
  pickerLabel: { fontSize: 12, marginBottom: spacing.xs },
  pickerRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  pickerOpt: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: radius.sm },
  pickerOptText: { fontSize: 14 },
  btn: { padding: spacing.md, borderRadius: radius.md, alignItems: 'center', marginTop: spacing.sm },
  btnText: { color: '#fff', fontWeight: '600' },
});
