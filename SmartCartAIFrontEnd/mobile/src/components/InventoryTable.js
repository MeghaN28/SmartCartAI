import React from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function InventoryTable({
  inventory,
  editingId,
  editForm,
  setEditForm,
  categories,
  getStockStatus,
  handleEdit,
  handleSaveEdit,
  handleCancelEdit,
  handleDelete,
}) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  const statusLabel = (s) => s.replace('-', ' ');

  return (
    <View style={styles.container}>
      {inventory.map((item) => (
        <View key={item.id} style={[styles.row, { backgroundColor: c.card, borderColor: c.border }]}>
          {editingId === item.id ? (
            <>
              <TextInput
                style={[styles.input, { color: c.text, borderColor: c.border }]}
                value={editForm.name}
                onChangeText={(v) => setEditForm({ ...editForm, name: v })}
                placeholder="Name"
              />
              <View style={styles.catRow}>
                {categories.map((cat) => (
                  <TouchableOpacity
                    key={cat}
                    style={[styles.catBtn, editForm.category === cat && { backgroundColor: c.primary }]}
                    onPress={() => setEditForm({ ...editForm, category: cat })}
                  >
                    <Text style={{ color: editForm.category === cat ? '#fff' : c.text, fontSize: 12 }}>{cat}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <TextInput
                style={[styles.input, { color: c.text, borderColor: c.border }]}
                value={editForm.quantity}
                onChangeText={(v) => setEditForm({ ...editForm, quantity: v })}
                keyboardType="numeric"
                placeholder="Qty"
              />
              <TextInput
                style={[styles.input, { color: c.text, borderColor: c.border }]}
                value={editForm.threshold}
                onChangeText={(v) => setEditForm({ ...editForm, threshold: v })}
                keyboardType="numeric"
                placeholder="Threshold"
              />
              <View style={styles.actions}>
                <TouchableOpacity style={[styles.actionBtn, { backgroundColor: c.success }]} onPress={handleSaveEdit}>
                  <Text style={styles.actionBtnText}>Save</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.actionBtn, { backgroundColor: c.textSecondary }]} onPress={handleCancelEdit}>
                  <Text style={styles.actionBtnText}>Cancel</Text>
                </TouchableOpacity>
              </View>
            </>
          ) : (
            <>
              <Text style={[styles.cell, { color: c.text }]} numberOfLines={1}>{item.name}</Text>
              <Text style={[styles.cell, { color: c.textSecondary }]}>{item.category}</Text>
              <Text style={[styles.cell, { color: c.text }]}>{item.quantity}</Text>
              <Text style={[styles.cell, { color: c.text }]}>{item.threshold}</Text>
              <View style={[styles.badge, { backgroundColor: c.card }]}>
                <Text style={[styles.badgeText, { color: c.text }]}>{statusLabel(getStockStatus(item))}</Text>
              </View>
              <View style={styles.actions}>
                <TouchableOpacity style={[styles.actionBtn, { backgroundColor: c.primary }]} onPress={() => handleEdit(item)}>
                  <Text style={styles.actionBtnText}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.actionBtn, { backgroundColor: c.danger }]} onPress={() => handleDelete(item.id)}>
                  <Text style={styles.actionBtnText}>Del</Text>
                </TouchableOpacity>
              </View>
            </>
          )}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.sm },
  row: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  input: { borderWidth: 1, borderRadius: radius.sm, padding: spacing.sm, marginBottom: spacing.sm },
  catRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: spacing.sm },
  catBtn: { paddingVertical: 4, paddingHorizontal: 8, borderRadius: 4 },
  cell: { fontSize: 14, marginBottom: 2 },
  badge: { paddingVertical: 2, paddingHorizontal: 6, borderRadius: 4, alignSelf: 'flex-start', marginVertical: 4 },
  badgeText: { fontSize: 12 },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  actionBtn: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: radius.sm },
  actionBtnText: { color: '#fff', fontSize: 12, fontWeight: '600' },
});
