import React from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

export default function ChatInput({ inputText, setInputText, handleSendMessage, isProcessing }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <View style={[styles.wrapper, { backgroundColor: c.card, borderTopColor: c.border }]}>
      <View style={[styles.inputRow, { backgroundColor: c.bg, borderColor: c.border }]}>
        <TextInput
          style={[styles.input, { color: c.text }]}
          placeholder="Message SmartCartAI..."
          placeholderTextColor={c.textSecondary}
          value={inputText}
          onChangeText={setInputText}
          multiline
          maxLength={2000}
        />
        {inputText.length > 0 && (
          <TouchableOpacity onPress={() => setInputText('')} style={styles.clearBtn}>
            <Text style={{ color: c.textSecondary, fontSize: 18 }}>✕</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity
          style={[styles.sendBtn, { backgroundColor: inputText.trim() && !isProcessing ? c.primary : c.border }]}
          onPress={() => handleSendMessage()}
          disabled={!inputText.trim() || isProcessing}
        >
          <Text style={styles.sendText}>Send</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { padding: spacing.md, borderTopWidth: 1 },
  inputRow: { flexDirection: 'row', alignItems: 'center', borderRadius: radius.lg, borderWidth: 1, paddingHorizontal: spacing.sm },
  input: { flex: 1, paddingVertical: spacing.md, fontSize: 16, maxHeight: 100 },
  clearBtn: { padding: spacing.sm },
  sendBtn: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: radius.md },
  sendText: { color: '#fff', fontWeight: '600' },
});
