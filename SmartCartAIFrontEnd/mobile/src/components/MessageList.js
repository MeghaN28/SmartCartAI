import React, { useEffect, useRef } from 'react';
import { View, Text, FlatList, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';
import { stripMarkdown } from '../utils/stripMarkdown';

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
        <View style={[styles.avatarWrap, { backgroundColor: isUser ? c.primary + '30' : c.card }]}>
          <Text style={styles.avatar}>{isUser ? '👤' : '🤖'}</Text>
        </View>
        <View
          style={[
            styles.bubble,
            isUser
              ? { backgroundColor: c.primary }
              : { backgroundColor: c.card, borderWidth: 1, borderColor: c.border },
          ]}
        >
          <Text
            style={[styles.bubbleText, { color: isUser ? '#fff' : c.text }]}
            selectable
          >
            {isUser ? item.text : stripMarkdown(item.text)}
          </Text>
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
            <View style={[styles.avatarWrap, { backgroundColor: c.card }]}>
              <Text style={styles.avatar}>🤖</Text>
            </View>
            <View style={[styles.typing, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.typingText, { color: c.textSecondary }]}>Thinking...</Text>
            </View>
          </View>
        ) : null
      }
    />
  );
}

const styles = StyleSheet.create({
  list: { flexGrow: 1, padding: spacing.lg },
  row: { flexDirection: 'row', alignItems: 'flex-end', marginBottom: spacing.lg },
  userRow: { flexDirection: 'row-reverse' },
  botRow: {},
  avatarWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: spacing.sm,
  },
  avatar: { fontSize: 22 },
  bubble: {
    maxWidth: '80%',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.xl,
  },
  bubbleText: { fontSize: 16, lineHeight: 24 },
  typing: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.xl,
    borderWidth: 1,
  },
  typingText: { fontSize: 15, fontStyle: 'italic' },
});
