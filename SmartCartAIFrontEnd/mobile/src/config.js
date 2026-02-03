import { Platform } from 'react-native';

// Use your machine's LAN IP when testing on a physical device (e.g. 'http://192.168.1.100:8080')
const API_BASE = __DEV__ && Platform.OS === 'android'
  ? 'http://10.0.2.2:8080'
  : 'http://127.0.0.1:8080';

export const API = {
  inventory: `${API_BASE}/api/inventory`,
  reorderLog: `${API_BASE}/api/reorder-log`,
  purchaseUpload: `${API_BASE}/api/purchase/upload_bulk`,
  tts: `${API_BASE}/api/tts`,
};

export const IGENTIC = {
  endpointBase: 'https://container-hackathon-sk.salmonpebble-59bd07ab.eastus.azurecontainerapps.io/api/iGenticAutonomousAgent/Executor',
  agentIdChat: 'f800f4c2-eb25-467c-942b-b81de85e2f1c',
  agentIdOrchestrator: 'df6578f6-7485-4946-85d3-0c6c1fb9114e',
  agentIdUpload: '612e3775-c2a3-40a5-b9ff-016be034a246',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_IGENTIC_TOKEN',
  },
};
