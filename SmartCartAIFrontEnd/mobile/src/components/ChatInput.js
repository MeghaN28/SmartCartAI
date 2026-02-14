import React from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function ChatInput({ inputText, setInputText, handleSendMessage, isProcessing }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const canSend = inputText.trim().length > 0 && !isProcessing;

  return (
    <View style={[styles.wrapper, { backgroundColor: c.card, borderTopColor: c.border }]}>
      <View style={[styles.inputRow, { backgroundColor: c.bg, borderColor: c.border }]}>
        <TextInput
          style={[styles.input, { color: c.text }]}
          placeholder="Message SmartCartAI..."
          placeholderTextColor={c.textMuted}
          value={inputText}
          onChangeText={setInputText}
          multiline
          maxLength={2000}
        />
        {inputText.length > 0 && (
          <TouchableOpacity onPress={() => setInputText('')} style={styles.clearBtn}>
            <Text style={{ color: c.textSecondary, fontSize: 18, fontWeight: '600' }}>✕</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity
          style={[
            styles.sendBtn,
            { backgroundColor: canSend ? c.primary : c.border },
          ]}
          onPress={() => handleSendMessage()}
          disabled={!canSend}
          activeOpacity={0.85}
        >
          <Text style={styles.sendText}>Send</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { padding: spacing.lg, borderTopWidth: 1 },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: radius.xl,
    borderWidth: 1.5,
    paddingHorizontal: spacing.md,
    minHeight: 52,
  },
  input: { flex: 1, paddingVertical: spacing.md, fontSize: 16, maxHeight: 120 },
  clearBtn: { padding: spacing.sm },
  sendBtn: {
    paddingVertical: spacing.sm + 4,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.lg,
  },
  sendText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
