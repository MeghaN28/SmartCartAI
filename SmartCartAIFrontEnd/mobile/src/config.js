import { Platform } from 'react-native';

// Use your machine's LAN IP when testing on a physical device (e.g. 'http://192.168.1.100:8080')
const API_BASE = __DEV__ && Platform.OS === 'android'
  ? 'http://10.0.2.2:8080'
  : 'http://127.0.0.1:8080';

export const API = {
  base: API_BASE,
  inventory: `${API_BASE}/api/inventory`,
  sales: `${API_BASE}/api/sales`,
  consumption: `${API_BASE}/api/consumption`,
  demand: `${API_BASE}/api/demand`,
  dashboardOverview: `${API_BASE}/api/dashboard/overview`,
  all: `${API_BASE}/api/all`,
  suggestions: `${API_BASE}/api/suggestions`,
  ragasRuns: `${API_BASE}/api/ragas/runs`,
  ragasFailures: `${API_BASE}/api/ragas/failures?latestRunOnly=true`,
  deleteSuggestion: (id) => `${API_BASE}/api/suggestions/${id}`,
  reorderLog: `${API_BASE}/api/reorder-log`, // Keep for backward compatibility
  purchaseUpload: `${API_BASE}/api/purchase/upload_bulk`,
  tts: `${API_BASE}/api/tts`,
  // Agent endpoints
  agents: {
    signalInventory: `${API_BASE}/api/agents/inventory/signal`,
    orchestrate: `${API_BASE}/api/agents/orchestrate`,
    chat: `${API_BASE}/api/agents/chat`,
    proactive: `${API_BASE}/api/agents/proactive`,
    dashboardItemInsights: `${API_BASE}/api/agents/dashboard/item-insights`,
    inventoryHealth: `${API_BASE}/api/agents/inventory/health`,
    orchestratorHealth: `${API_BASE}/api/agents/orchestrator/health`,
    chatHealth: `${API_BASE}/api/agents/chat/health`,
    dashboardHealth: `${API_BASE}/api/agents/dashboard/health`,
    startMonitoring: `${API_BASE}/api/agents/inventory/monitor/start`,
    monitoringStatus: `${API_BASE}/api/agents/inventory/monitor/status`,
  },
};

// Placeholder for future iGentic agent integration. Set when ready to use.
export const IGENTIC = {
  endpointBase: '',
  agentIdChat: '',
  agentIdOrchestrator: '',
  agentIdUpload: '',
  headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ...' },
};
