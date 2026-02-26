import React, { useEffect, useRef } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity, Linking } from 'react-native';
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

  const buildMapUrl = (foodBank) => {
    const lat = foodBank?.lat;
    const lon = foodBank?.lon;
    if (lat != null && lon != null) {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${lat},${lon}`)}`;
    }
    const query = [
      foodBank?.name || '',
      foodBank?.address || '',
      foodBank?.city || '',
      foodBank?.state || '',
      foodBank?.zip || '',
    ].join(' ').trim();
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query || 'food bank')}`;
  };

  const openUrl = async (url) => {
    if (!url) return;
    try {
      const supported = await Linking.canOpenURL(url);
      if (supported) {
        await Linking.openURL(url);
      }
    } catch (_) {}
  };

  const renderItem = ({ item }) => {
    const isUser = item.sender === 'user';
    const nearestFoodBanks = !isUser && Array.isArray(item.nearestFoodBanks) ? item.nearestFoodBanks : [];
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
          {!isUser && nearestFoodBanks.length > 0 ? (
            <View style={[styles.mapWrap, { borderTopColor: c.border }]}>
              <Text style={[styles.mapTitle, { color: c.text }]}>Nearest food banks</Text>
              {nearestFoodBanks.slice(0, 3).map((fb, idx) => (
                <TouchableOpacity
                  key={`${fb.name || 'fb'}-${idx}`}
                  onPress={() => openUrl(buildMapUrl(fb))}
                  style={[styles.mapButton, { backgroundColor: c.primary + '15', borderColor: c.primary + '40' }]}
                >
                  <Text style={[styles.mapButtonText, { color: c.primary }]}>
                    {`View map: ${fb.name || 'Food bank'}`}
                  </Text>
                </TouchableOpacity>
              ))}
              {item.mapSearchUrl ? (
                <TouchableOpacity
                  onPress={() => openUrl(item.mapSearchUrl)}
                  style={[styles.mapButton, { backgroundColor: c.card, borderColor: c.border }]}
                >
                  <Text style={[styles.mapButtonText, { color: c.textSecondary }]}>Open nearby map search</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          ) : null}
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
  mapWrap: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
  },
  mapTitle: {
    fontSize: 13,
    marginBottom: spacing.sm,
    fontWeight: '600',
  },
  mapButton: {
    borderWidth: 1,
    borderRadius: radius.md,
    paddingVertical: 8,
    paddingHorizontal: 10,
    marginTop: 6,
  },
  mapButtonText: {
    fontSize: 13,
    fontWeight: '600',
  },
  typing: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.xl,
    borderWidth: 1,
  },
  typingText: { fontSize: 15, fontStyle: 'italic' },
});
