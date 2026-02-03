import React, { useEffect, useRef } from 'react';
import { View, Text, FlatList, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing } from '../theme';

export default function MessageList({ messages, isProcessing }) {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const listRef = useRef(null);

  useEffect(() => {
    if (messages.length > 0 && listRef.current) {
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [messages, isProcessing]);

  const renderItem = ({ item }) => {
    const isUser = item.sender === 'user';
    return (
      <View style={[styles.row, isUser ? styles.userRow : styles.botRow]}>
        <Text style={styles.avatar}>{isUser ? '👤' : '🤖'}</Text>
        <View style={[styles.bubble, isUser ? { backgroundColor: c.primary } : { backgroundColor: c.card }]}>
          <Text style={[styles.bubbleText, { color: isUser ? '#fff' : c.text }]}>{item.text}</Text>
        </View>
      </View>
    );
  };

  return (
    <FlatList
      ref={listRef}
      data={messages}
      keyExtractor={(item) => item.id}
      renderItem={renderItem}
      contentContainerStyle={[styles.list, { paddingBottom: spacing.xl }]}
      ListFooterComponent={
        isProcessing ? (
          <View style={[styles.row, styles.botRow]}>
            <Text style={styles.avatar}>🤖</Text>
            <View style={[styles.typing, { backgroundColor: c.card }]}>
              <Text style={[styles.typingText, { color: c.textSecondary }]}>...</Text>
            </View>
          </View>
        ) : null
      }
    />
  );
}

const styles = StyleSheet.create({
  list: { flexGrow: 1, padding: spacing.md },
  row: { flexDirection: 'row', alignItems: 'flex-end', marginBottom: spacing.md },
  userRow: { flexDirection: 'row-reverse' },
  botRow: {},
  avatar: { fontSize: 24, marginHorizontal: spacing.sm },
  bubble: { maxWidth: '80%', padding: spacing.md, borderRadius: 14 },
  bubbleText: { fontSize: 15 },
  typing: { padding: spacing.md, borderRadius: 14 },
  typingText: { fontSize: 16 },
});
