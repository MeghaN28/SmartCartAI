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
  etsMetrics: `${API_BASE}/api/ets/metrics`,
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

const AUTH = {
  username: process.env.EXPO_PUBLIC_APP_AUTH_USERNAME || 'admin',
  password: process.env.EXPO_PUBLIC_APP_AUTH_PASSWORD || 'change-me',
};

let _accessToken = null;
let _refreshPromise = null;
let _installed = false;
let _rawFetch = null;

function _isApiUrl(url) {
  try {
    const s = String(url || '');
    return s.startsWith(`${API.base}/api/`) || s.includes('/api/');
  } catch {
    return false;
  }
}

function _isAuthEndpoint(url) {
  return String(url || '').includes('/api/auth/token');
}

async function _fetchToken() {
  const res = await _rawFetch(`${API.base}/api/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: AUTH.username, password: AUTH.password }),
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => '');
    throw new Error(`Auth token request failed (${res.status}): ${msg}`);
  }
  const data = await res.json();
  const token = data?.access_token;
  if (!token) throw new Error('No access_token returned from /api/auth/token');
  _accessToken = token;
  return token;
}

async function _getToken() {
  if (_accessToken) return _accessToken;
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = _fetchToken().finally(() => {
    _refreshPromise = null;
  });
  return _refreshPromise;
}

async function _authFetch(input, init = {}) {
  const url = typeof input === 'string' ? input : input?.url;
  if (!_isApiUrl(url) || _isAuthEndpoint(url)) {
    return _rawFetch(input, init);
  }

  const token = await _getToken();
  const headers = { ...(init.headers || {}), Authorization: `Bearer ${token}` };
  let res = await _rawFetch(input, { ...init, headers });

  if (res.status === 401) {
    _accessToken = null;
    const retryToken = await _getToken();
    const retryHeaders = { ...(init.headers || {}), Authorization: `Bearer ${retryToken}` };
    res = await _rawFetch(input, { ...init, headers: retryHeaders });
  }
  return res;
}

export function installGlobalAuthFetch() {
  if (_installed) return;
  _rawFetch = global.fetch.bind(global);
  global.fetch = _authFetch;
  _installed = true;
}

// Placeholder for future iGentic agent integration. Set when ready to use.
export const IGENTIC = {
  endpointBase: '',
  agentIdChat: '',
  agentIdOrchestrator: '',
  agentIdUpload: '',
  headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ...' },
};
