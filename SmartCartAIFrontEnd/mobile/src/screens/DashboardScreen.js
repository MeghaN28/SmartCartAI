import React, { useState, useEffect, useMemo } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, TextInput, TouchableOpacity, Alert } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius, typography } from '../theme';
import { API } from '../config';
import StatsGrid from '../components/StatsGrid';
import ChartsSection from '../components/ChartsSection';
import LowStockAlerts from '../components/LowStockAlerts';
import AddItemForm from '../components/AddItemForm';
import InventoryTable from '../components/InventoryTable';
import ItemForecastModal from './ItemForecastModal';

function generateId() {
  return 'INV' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

const safeNumber = (val) => {
  const n = Number(val);
  return isNaN(n) ? 0 : n;
};

const getStockStatus = (item) => {
  const qty = safeNumber(item.quantity);
  const th = safeNumber(item.threshold);
  if (qty === 0) return 'out-of-stock';
  if (qty > 0 && qty <= th) return 'low-stock';
  return 'in-stock';
};

export default function DashboardScreen() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', category: '', quantity: '', threshold: '' });
  const [newItem, setNewItem] = useState({ name: '', category: '', quantity: '', threshold: '' });
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedItemSearch, setSelectedItemSearch] = useState('');
  const [agentError, setAgentError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [currentItem, setCurrentItem] = useState(null);
  const [parsedData, setParsedData] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [agentLoading, setAgentLoading] = useState(false);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const [proactiveAlert, setProactiveAlert] = useState(null);
  const [proactiveLoading, setProactiveLoading] = useState(true);
  const [proactiveError, setProactiveError] = useState(null);
  const [salesChartData, setSalesChartData] = useState({ labels: [], quantity: [] });

  const itemsPerPage = 20;

  const fetchProactiveAlerts = React.useCallback(async () => {
    setProactiveLoading(true);
    setProactiveError(null);
    try {
      const res = await fetch(API.agents.proactive, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: 'dashboard-' + Date.now() }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setProactiveAlert(data.answer || null);
      } else {
        setProactiveAlert(null);
        setProactiveError(data.error || 'Could not load alerts');
      }
    } catch (e) {
      setProactiveAlert(null);
      setProactiveError(e.message || 'Proactive alerts unavailable');
    } finally {
      setProactiveLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProactiveAlerts();
  }, [fetchProactiveAlerts]);

  useEffect(() => {
    setLoading(true);
    fetch(API.inventory)
      .then((res) => res.json())
      .then((data) => {
        const rawList = Array.isArray(data) ? data : (data.items || []);
        const formatted = rawList.map((item, index) => ({
          id: item.inventoryId || item.itemName || generateId(),
          name: item.itemName || 'Unnamed',
          category: item.itemType || item.category || 'Unknown',
          quantity: safeNumber(item.openingStock ?? item.current_stock ?? item.initial_stock ?? 0),
          threshold: safeNumber(item.minStock ?? item.min_stock ?? item.minimum_required ?? 0),
          raw: item,
        }));
        setInventory(formatted);
        setLoading(false);
      })
      .catch(() => {
        setInventory([]);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetch(API.dashboardOverview)
      .then((res) => res.json())
      .then((data) => {
        const chart = data?.salesChart || {};
        setSalesChartData({
          labels: Array.isArray(chart.labels) ? chart.labels : [],
          quantity: Array.isArray(chart.quantity) ? chart.quantity.map(safeNumber) : [],
        });
      })
      .catch(() => {
        setSalesChartData({ labels: [], quantity: [] });
      });
  }, []);

  const chartColors = {
    dark: { bg: '#1e293b', border: '#334155', text: '#f1f5f9', textSecondary: '#cbd5e1', grid: '#334155' },
    light: { bg: '#ffffff', border: '#e2e8f0', text: '#1e293b', textSecondary: '#64748b', grid: '#e2e8f0' },
  };
  const chartC = chartColors[theme] || chartColors.light;

  const categories = useMemo(() => [...new Set(inventory.map((i) => i.category))], [inventory]);

  const filteredInventory = useMemo(() => {
    let data = inventory;
    if (selectedItemSearch) {
      data = data.filter((i) => i.name.toLowerCase().includes(selectedItemSearch.toLowerCase()));
    }
    return data;
  }, [inventory, selectedItemSearch]);

  const totalPages = Math.max(1, Math.ceil(filteredInventory.length / itemsPerPage));
  const paginatedInventory = filteredInventory.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const stats = {
    totalItems: inventory.length,
    inStock: inventory.filter((i) => getStockStatus(i) === 'in-stock').length,
    lowStock: inventory.filter((i) => getStockStatus(i) === 'low-stock').length,
    outOfStock: inventory.filter((i) => getStockStatus(i) === 'out-of-stock').length,
    totalQuantity: inventory.reduce((s, i) => s + safeNumber(i.quantity), 0),
  };

  const categoryData = inventory.reduce((acc, item) => {
    if (!acc[item.category]) acc[item.category] = { name: item.category, quantity: 0, items: 0 };
    acc[item.category].quantity += safeNumber(item.quantity);
    acc[item.category].items += 1;
    return acc;
  }, {});
  const categoryChartData = Object.values(categoryData).map((cat) => ({
    name: cat.name,
    quantity: cat.quantity,
    items: cat.items,
  }));

  const statusData = [
    { name: 'In Stock', value: stats.inStock, color: '#10b981' },
    { name: 'Low Stock', value: stats.lowStock, color: '#f59e0b' },
    { name: 'Out of Stock', value: stats.outOfStock, color: '#ef4444' },
  ];

  const stockChartData = React.useMemo(() => {
    if (!inventory.length) return [];
    const sorted = [...inventory].sort((a, b) => safeNumber(b.quantity) - safeNumber(a.quantity));
    return sorted.slice(0, 12).map((item) => ({
      name: item.name,
      quantity: safeNumber(item.quantity),
    }));
  }, [inventory]);

  const lowStockAlerts = inventory.filter((i) => getStockStatus(i) === 'low-stock');

  const handleEdit = (item) => {
    setEditingId(item.id);
    setEditForm({
      name: item.name,
      category: item.category,
      quantity: String(item.quantity),
      threshold: String(item.threshold),
    });
  };

  const handleSaveEdit = () => {
    setInventory(
      inventory.map((item) =>
        item.id === editingId
          ? {
              ...item,
              name: editForm.name,
              category: editForm.category,
              quantity: safeNumber(editForm.quantity),
              threshold: safeNumber(editForm.threshold),
            }
          : item
      )
    );
    setEditingId(null);
    setEditForm({ name: '', category: '', quantity: '', threshold: '' });
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditForm({ name: '', category: '', quantity: '', threshold: '' });
  };

  const sendToAgent = async (item) => {
    if (!item) return;
    setCurrentItem(item);
    setAgentLoading(true);
    setAgentError(null);
    setShowModal(false);
    setParsedData(null);

    // Use Decision Orchestrator Agent via backend API
    const payload = {
      inventory_id: item.id || item.inventory_id || `INV-${item.name?.replace(/\s+/g, '-').toUpperCase()}`,
      event_type: item.quantity <= item.threshold ? 'low_stock' : 'monitoring',
      remaining_stock: item.quantity || 0,
      suggested_action: item.quantity <= item.threshold ? 'reorder' : 'none',
      stock_signal: item.quantity === 0 ? 'critical' : item.quantity <= item.threshold ? 'low' : 'normal',
      consumption_signal: 'normal',
      item_data: {
        item_name: item.name,
        category: item.category,
        min_stock: item.threshold,
        max_capacity: item.maxCapacity || 1000,
        vendor_id: item.vendorId || item.raw?.vendor_id,
      },
      context: {
        threshold: item.threshold,
        current_quantity: item.quantity,
      },
    };

    try {
      const res = await fetch(API.agents.orchestrate, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `API ${res.status}`);
      }
      
      const data = await res.json();
      const recommendation = data.recommendation || {};
      const explanation = data.explanation || {};
      
      // Parse response for display
      const parsed = {
        currentStock: item.quantity,
        reorderLevel: item.threshold,
        lowStock: item.quantity <= item.threshold,
        recommendation: recommendation.action || 'none',
        priority: recommendation.priority || 'Medium',
        reasoning: recommendation.reasoning || explanation.explanation || 'No explanation available',
        expectedOutcome: recommendation.expected_outcome || '',
        riskAssessment: data.risk_assessment || {},
        feasibility: data.feasibility_check || {},
        costImpact: data.cost_impact || {},
        actions: recommendation.action === 'reorder' ? ['Reorder Item'] : [],
      };
      
      setParsedData(parsed);
      setShowModal(true);
    } catch (err) {
      setAgentError(err.message || String(err));
      console.error('Agent error:', err);
    } finally {
      setAgentLoading(false);
    }
  };

  const handleSearchInsights = async () => {
    const query = (selectedItemSearch || '').trim();
    if (!query) {
      Alert.alert('Item required', 'Enter an item name to open recommendations.');
      return;
    }
    setSuggestionLoading(true);
    setAgentError(null);
    try {
      const res = await fetch(API.agents.dashboardItemInsights, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Request failed: ${res.status}`);
      }

      const item = data.item || {};
      const metrics = data.metrics || {};
      const recommendation = data.recommendation || {};
      const charts = data.charts || {};
      const itemForModal = {
        id: item.inventory_id || query,
        name: item.item_name || query,
        category: item.category || 'Unknown',
        quantity: safeNumber(metrics.current_stock),
        threshold: safeNumber(metrics.min_stock),
      };

      setCurrentItem(itemForModal);
      setParsedData({
        currentStock: safeNumber(metrics.current_stock),
        reorderLevel: safeNumber(metrics.min_stock),
        lowStock: safeNumber(metrics.current_stock) <= safeNumber(metrics.min_stock),
        recommendation: recommendation.action || 'monitor',
        priority: recommendation.priority || 'Medium',
        reasoning: recommendation.reasoning || 'No recommendation details available.',
        expectedOutcome: metrics.stock_coverage_days
          ? `Estimated stock coverage is ${metrics.stock_coverage_days} days.`
          : 'No demand coverage estimate available.',
        actions: recommendation.queries || [],
        salesChart: charts.sales || null,
        demandChart: charts.demand || null,
        stockChart: charts.stock || null,
        metrics,
      });
      setShowModal(true);
    } catch (err) {
      setAgentError(err.message || String(err));
      Alert.alert('Error', err.message || 'Could not load item insights. Ensure backend and Dashboard agent are running.');
    } finally {
      setSuggestionLoading(false);
    }
  };

  const handleAddItem = () => {
    const created = {
      id: generateId(),
      name: newItem.name || 'New Item',
      category: newItem.category || 'Unknown',
      quantity: safeNumber(newItem.quantity),
      threshold: safeNumber(newItem.threshold),
    };
    setInventory([created, ...inventory]);
    setShowAddForm(false);
    setNewItem({ name: '', category: '', quantity: '', threshold: '' });
  };

  if (loading) {
    return (
      <View style={[styles.centered, { backgroundColor: c.bg }]}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={[styles.loadingText, { color: c.textSecondary }]}>Loading inventory...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={[styles.container, { backgroundColor: c.bg }]} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={[styles.pageTitle, { color: c.text }]}>Dashboard</Text>
        <View style={styles.searchRow}>
          <TextInput
            style={[styles.searchInput, { color: c.text, backgroundColor: c.card, borderColor: c.border }]}
            placeholder="Search item for AI insights (e.g. milk)..."
            placeholderTextColor={c.textMuted}
            value={selectedItemSearch}
            onChangeText={setSelectedItemSearch}
            onSubmitEditing={handleSearchInsights}
            returnKeyType="search"
          />
          <TouchableOpacity
            style={[styles.agentBtn, { backgroundColor: c.primary }]}
            onPress={handleSearchInsights}
            disabled={suggestionLoading}
            activeOpacity={0.88}
          >
            <Text style={styles.agentBtnText}>{suggestionLoading ? '…' : 'Analyze'}</Text>
          </TouchableOpacity>
        </View>
        <Text style={[styles.hint, { color: c.textSecondary }]}>
          Search and press Analyze to open the item insight popup with stock, sales, and demand charts.
        </Text>
      </View>

      <StatsGrid stats={stats} />
      <ChartsSection
        categoryChartData={categoryChartData}
        statusData={statusData}
        salesChartData={salesChartData}
        stockChartData={stockChartData}
        colors={chartC}
      />
      <LowStockAlerts lowStockAlerts={lowStockAlerts} />

      <View style={[styles.section, styles.proactiveSection]}>
        <View style={styles.sectionHeader}>
          <Text style={[styles.sectionTitle, { color: c.text }]}>Proactive Alerts</Text>
          <TouchableOpacity
            style={[styles.addBtn, { backgroundColor: c.primary }]}
            onPress={fetchProactiveAlerts}
            disabled={proactiveLoading}
            activeOpacity={0.85}
          >
            <Text style={styles.addBtnText}>{proactiveLoading ? 'Loading…' : 'Refresh'}</Text>
          </TouchableOpacity>
        </View>
        <View style={[styles.proactiveCard, { backgroundColor: c.card, borderColor: c.border }]}>
          {proactiveLoading && !proactiveAlert ? (
            <ActivityIndicator size="small" color={c.primary} style={styles.proactiveLoader} />
          ) : proactiveError && !proactiveAlert ? (
            <Text style={[styles.proactiveText, { color: c.textSecondary }]}>{proactiveError}</Text>
          ) : proactiveAlert ? (
            <Text style={[styles.proactiveText, { color: c.text }]}>{proactiveAlert}</Text>
          ) : (
            <Text style={[styles.proactiveText, { color: c.textSecondary }]}>No proactive alerts. Check the Chat tab for full recommendations.</Text>
          )}
        </View>
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={[styles.sectionTitle, { color: c.text }]}>Inventory Management</Text>
          <TouchableOpacity
            style={[styles.addBtn, { backgroundColor: showAddForm ? c.textSecondary : c.primary }]}
            onPress={() => setShowAddForm(!showAddForm)}
            activeOpacity={0.85}
          >
            <Text style={styles.addBtnText}>{showAddForm ? 'Cancel' : '+ Add Item'}</Text>
          </TouchableOpacity>
        </View>

        {showAddForm && (
          <AddItemForm
            newItem={newItem}
            setNewItem={setNewItem}
            categories={categories}
            handleAddItem={handleAddItem}
          />
        )}

        <InventoryTable
          inventory={paginatedInventory}
          editingId={editingId}
          editForm={editForm}
          setEditForm={setEditForm}
          categories={categories}
          getStockStatus={getStockStatus}
          handleEdit={handleEdit}
          handleSaveEdit={handleSaveEdit}
          handleCancelEdit={handleCancelEdit}
          handleDelete={(id) => setInventory(inventory.filter((it) => it.id !== id))}
          onRecommend={sendToAgent}
        />

        {totalPages > 1 && (
          <View style={styles.pagination}>
            <TouchableOpacity
              style={[styles.pageBtn, { backgroundColor: c.card }]}
              onPress={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              <Text style={{ color: c.text }}>Prev</Text>
            </TouchableOpacity>
            <Text style={[styles.pageNum, { color: c.text }]}>
              {currentPage} / {totalPages}
            </Text>
            <TouchableOpacity
              style={[styles.pageBtn, { backgroundColor: c.card }]}
              onPress={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              <Text style={{ color: c.text }}>Next</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      {agentError && (
        <View style={[styles.errorWrap, { backgroundColor: c.danger + '20' }]}>
          <Text style={[styles.errorText, { color: c.danger }]}>{agentError}</Text>
        </View>
      )}

      {showModal && (
        <ItemForecastModal
          item={currentItem}
          parsed={parsedData}
          onClose={() => {
            setShowModal(false);
            setCurrentItem(null);
            setParsedData(null);
          }}
        />
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl * 2 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: spacing.md },
  header: { marginBottom: spacing.xl },
  pageTitle: { ...typography.title, marginBottom: spacing.md },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  searchInput: { flex: 1, padding: spacing.md + 2, borderRadius: radius.lg, borderWidth: 1.5, fontSize: 16 },
  agentBtn: { paddingVertical: spacing.md + 2, paddingHorizontal: spacing.lg, borderRadius: radius.lg },
  agentBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  hint: { fontSize: 12, marginTop: spacing.sm },
  section: { marginTop: spacing.xl },
  proactiveSection: {},
  proactiveCard: {
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    minHeight: 64,
  },
  proactiveLoader: { alignSelf: 'center', marginVertical: spacing.md },
  proactiveText: { fontSize: 14, lineHeight: 22 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.lg },
  sectionTitle: { ...typography.subtitle, fontSize: 18 },
  addBtn: { paddingVertical: spacing.sm + 4, paddingHorizontal: spacing.lg, borderRadius: radius.lg },
  addBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  pagination: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.md, marginTop: spacing.xl },
  pageBtn: { paddingVertical: spacing.sm + 4, paddingHorizontal: spacing.lg, borderRadius: radius.lg },
  pageNum: { fontWeight: '600', fontSize: 15 },
  errorWrap: { padding: spacing.lg, borderRadius: radius.lg, marginTop: spacing.lg },
  errorText: { fontSize: 14 },
});
