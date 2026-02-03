import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';
import { API, IGENTIC } from '../config';

export default function UploadPurchaseScreen() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  const [files, setFiles] = useState([]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [agentResponse, setAgentResponse] = useState(null);

  const pickFiles = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['image/*', 'application/pdf'],
        copyToCacheDirectory: true,
        multiple: true,
      });
      if (result.canceled) return;
      const newFiles = result.assets.map((a) => ({ name: a.name, uri: a.uri, mimeType: a.mimeType }));
      setFiles((prev) => [...prev, ...newFiles]);
      setUploadedFiles([]);
      setError(null);
      setAgentResponse(null);
    } catch (e) {
      setError(e.message || 'Failed to pick files');
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    setLoading(true);
    setError(null);
    setUploadedFiles([]);
    setAgentResponse(null);

    const formData = new FormData();
    files.forEach((f) => {
      formData.append('files', { uri: f.uri, name: f.name, type: f.mimeType || 'image/jpeg' });
    });

    try {
      const res = await fetch(API.purchaseUpload, { method: 'POST', body: formData });
      const data = await res.json();
      if (!data.success) {
        setError(data.error || 'Upload failed');
        setLoading(false);
        return;
      }
      setUploadedFiles(data.files || []);

      const promptPayload = {
        UserInput: `Process uploaded purchase receipts. Extract item names and quantities; use Inventory & Demand MCP tools to update inventory_master and consumption. Return a summary per receipt.`,
        base64string: '',
        additionalData: { receipts_path: '/home/meghanarendrasimha/Documents/receipts' },
      };

      const agentRes = await fetch(`${IGENTIC.endpointBase}/${IGENTIC.agentIdUpload}`, {
        method: 'POST',
        headers: IGENTIC.headers,
        body: JSON.stringify(promptPayload),
      });
      const agentData = await agentRes.json();
      setAgentResponse(agentData);
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const clearFiles = () => setFiles([]);

  return (
    <ScrollView style={[styles.container, { backgroundColor: c.bg }]} contentContainerStyle={styles.content}>
      <Text style={[styles.title, { color: c.text }]}>Upload Purchase Receipts</Text>

      <TouchableOpacity style={[styles.pickBtn, { backgroundColor: c.card, borderColor: c.border }]} onPress={pickFiles}>
        <Text style={[styles.pickBtnText, { color: c.primary }]}>Choose files (images/PDF)</Text>
      </TouchableOpacity>

      {files.length > 0 && (
        <View style={[styles.filesBox, { backgroundColor: c.card, borderColor: c.border }]}>
          <Text style={[styles.filesTitle, { color: c.text }]}>Selected ({files.length})</Text>
          {files.map((f, idx) => (
            <Text key={idx} style={[styles.fileName, { color: c.textSecondary }]} numberOfLines={1}>
              {f.name}
            </Text>
          ))}
          <TouchableOpacity onPress={clearFiles} style={styles.clearFiles}>
            <Text style={{ color: c.danger, fontSize: 14 }}>Clear all</Text>
          </TouchableOpacity>
        </View>
      )}

      <TouchableOpacity
        style={[styles.uploadBtn, { backgroundColor: files.length && !loading ? c.primary : c.border }]}
        onPress={handleUpload}
        disabled={files.length === 0 || loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.uploadBtnText}>Upload & Process</Text>
        )}
      </TouchableOpacity>

      {error && (
        <View style={[styles.errorBox, { backgroundColor: c.danger + '20' }]}>
          <Text style={[styles.errorText, { color: c.danger }]}>{error}</Text>
        </View>
      )}

      {uploadedFiles.length > 0 && (
        <View style={[styles.resultBox, { backgroundColor: c.card, borderColor: c.border }]}>
          <Text style={[styles.resultTitle, { color: c.text }]}>Uploaded</Text>
          {uploadedFiles.map((f, idx) => (
            <Text key={idx} style={[styles.fileName, { color: c.textSecondary }]}>{f}</Text>
          ))}
        </View>
      )}

      {agentResponse && (
        <View style={[styles.resultBox, { backgroundColor: c.card, borderColor: c.border }]}>
          <Text style={[styles.resultTitle, { color: c.text }]}>Agent response</Text>
          {agentResponse.receipts_summary ? (
            agentResponse.receipts_summary.map((receipt, idx) => (
              <View key={idx} style={styles.receiptCard}>
                <Text style={[styles.receiptTitle, { color: c.text }]}>{receipt.filename}</Text>
                {(receipt.processed_items || []).map((item, i) => (
                  <Text key={i} style={[styles.receiptItem, { color: c.textSecondary }]}>
                    {item.item}: {item.quantity_consumed || '-'} → {item.Updated_Stock || '-'}
                  </Text>
                ))}
              </View>
            ))
          ) : (
            <Text style={[styles.preText, { color: c.textSecondary }]} selectable>
              {agentResponse.result || JSON.stringify(agentResponse, null, 2)}
            </Text>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 3 },
  title: { fontSize: 20, fontWeight: '700', marginBottom: spacing.lg },
  pickBtn: { padding: spacing.lg, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  pickBtnText: { fontSize: 16, fontWeight: '600' },
  filesBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  filesTitle: { fontWeight: '600', marginBottom: spacing.sm },
  fileName: { fontSize: 13, marginBottom: 2 },
  clearFiles: { marginTop: spacing.sm },
  uploadBtn: { padding: spacing.lg, borderRadius: radius.md, alignItems: 'center', marginBottom: spacing.md },
  uploadBtnText: { color: '#fff', fontWeight: '600' },
  errorBox: { padding: spacing.md, borderRadius: radius.md, marginBottom: spacing.md },
  errorText: { fontSize: 14 },
  resultBox: { padding: spacing.md, borderRadius: radius.md, borderWidth: 1, marginBottom: spacing.md },
  resultTitle: { fontWeight: '600', marginBottom: spacing.sm },
  preText: { fontSize: 12 },
  receiptCard: { marginTop: spacing.sm, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.1)' },
  receiptTitle: { fontWeight: '600', marginBottom: 4 },
  receiptItem: { fontSize: 13, marginBottom: 2 },
});
