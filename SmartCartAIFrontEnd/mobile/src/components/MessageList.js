import React, { useEffect, useRef } from 'react';
import { View, Text, FlatList, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';

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
            {item.text}
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
  list: { flexGrow: 1, padding: spacing.md },
  row: { flexDirection: 'row', alignItems: 'flex-end', marginBottom: spacing.md },
  userRow: { flexDirection: 'row-reverse' },
  botRow: {},
  avatarWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: spacing.xs,
  },
  avatar: { fontSize: 20 },
  bubble: {
    maxWidth: '78%',
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.md,
    borderRadius: radius.lg,
  },
  bubbleText: { fontSize: 15, lineHeight: 22 },
  typing: {
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
  },
  typingText: { fontSize: 14, fontStyle: 'italic' },
});
