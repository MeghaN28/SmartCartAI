import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, RefreshControl } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';
import { API } from '../config';

export default function ReorderLogScreen() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchLogs = async () => {
    try {
      const res = await fetch(API.reorderLog);
      const data = await res.json();
      setLogs(Array.isArray(data) ? data : []);
    } catch (err) {
      setLogs([]);
    }
    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchLogs();
  };

  if (loading) {
    return (
      <View style={[styles.centered, { backgroundColor: c.bg }]}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={[styles.loadingText, { color: c.textSecondary }]}>Loading reorder logs...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: c.bg }]}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={c.primary} />}
    >
      <Text style={[styles.title, { color: c.text }]}>Reorder Log</Text>

      {logs.length === 0 ? (
        <Text style={[styles.noData, { color: c.textSecondary }]}>No reorder logs found.</Text>
      ) : (
        logs.map((log) => (
          <View key={log.log_id} style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}>
            <View style={styles.row}>
              <Text style={[styles.label, { color: c.textSecondary }]}>Item</Text>
              <Text style={[styles.value, { color: c.text }]}>{log.item_name}</Text>
            </View>
            <View style={styles.row}>
              <Text style={[styles.label, { color: c.textSecondary }]}>Inv ID</Text>
              <Text style={[styles.value, { color: c.text }]}>{log.inventory_id}</Text>
            </View>
            <View style={styles.row}>
              <Text style={[styles.label, { color: c.textSecondary }]}>Reorder Qty</Text>
              <Text style={[styles.value, { color: c.text }]}>{log.reorder_quantity}</Text>
            </View>
            <View style={styles.row}>
              <Text style={[styles.label, { color: c.textSecondary }]}>Current Stock</Text>
              <Text style={[styles.value, { color: c.text }]}>{log.current_stock}</Text>
            </View>
            <View style={styles.row}>
              <Text style={[styles.label, { color: c.textSecondary }]}>Status</Text>
              <View style={[styles.statusBadge, { backgroundColor: (log.status || '').toLowerCase() === 'sent' ? c.success + '30' : c.warning + '30' }]}>
                <Text style={[styles.statusText, { color: c.text }]}>{log.status}</Text>
              </View>
            </View>
            {log.email_recipient ? (
              <View style={styles.row}>
                <Text style={[styles.label, { color: c.textSecondary }]}>Recipient</Text>
                <Text style={[styles.value, { color: c.text }]} numberOfLines={1}>{log.email_recipient}</Text>
              </View>
            ) : null}
            <View style={styles.row}>
              <Text style={[styles.label, { color: c.textSecondary }]}>Created</Text>
              <Text style={[styles.value, { color: c.textSecondary }]}>
                {new Date(log.created_at).toLocaleString()}
              </Text>
            </View>
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 3 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: spacing.md },
  title: { fontSize: 22, fontWeight: '700', marginBottom: spacing.lg },
  noData: { fontSize: 16 },
  card: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm },
  label: { fontSize: 12 },
  value: { fontSize: 14, flex: 1, marginLeft: spacing.sm, textAlign: 'right' },
  statusBadge: { paddingHorizontal: spacing.sm, paddingVertical: 2, borderRadius: radius.sm },
  statusText: { fontSize: 12, fontWeight: '600' },
});
