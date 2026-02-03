import React, { useState, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TextInput,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing } from '../theme';
import { API, IGENTIC } from '../config';
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

const parseAgentResponse = (text, item) => {
  if (!text) return { currentStock: item.quantity, reorderLevel: item.threshold, lowStock: false, actions: [] };
  let currentStock = item.quantity;
  let reorderLevel = item.threshold;
  let lowStock = item.quantity <= item.threshold;
  let actions = [];
  const stockMatch = text.match(/Current Stock on Hand:\s*(\d+)/i);
  if (stockMatch) currentStock = parseInt(stockMatch[1], 10);
  const reorderMatch = text.match(/Minimum Stock Limit:\s*(\d+)/i);
  if (reorderMatch) reorderLevel = parseInt(reorderMatch[1], 10);
  const lowMatch = text.match(/Low-Stock Warning:\s*(Yes|No)/i);
  lowStock = lowMatch ? lowMatch[1].toLowerCase() === 'yes' : lowStock;
  const actionBlock = text.match(/Recommended Actions:[\s\S]*/i);
  if (actionBlock) {
    actions = actionBlock[0]
      .split('\n')
      .filter((l) => l.trim().startsWith('-'))
      .map((l) => l.replace('-', '').trim());
  }
  return { currentStock, reorderLevel, lowStock, actions };
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

  const itemsPerPage = 20;

  useEffect(() => {
    setLoading(true);
    fetch(API.inventory)
      .then((res) => res.json())
      .then((data) => {
        if (data.success && Array.isArray(data.items)) {
          const formatted = data.items.map((item) => ({
            id: item.inventory_id || generateId(),
            name: item.item_name || 'Unnamed',
            category: item.item_type || item.category || 'Unknown',
            quantity: safeNumber(item.current_stock ?? item.initial_stock ?? 0),
            threshold: safeNumber(item.min_stock ?? item.minimum_required ?? 0),
            raw: item,
          }));
          setInventory(formatted);
        } else setInventory([]);
        setLoading(false);
      })
      .catch(() => {
        setInventory([]);
        setLoading(false);
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

    const payload = {
      UserInput: JSON.stringify({
        item_id: item.id,
        item_name: item.name,
        forecast_output: [],
        threshold_status: {
          flag_below_min: item.quantity <= item.threshold,
          reorder_level: item.threshold,
          reason: item.quantity <= item.threshold ? 'Below minimum' : 'Stock OK',
        },
        stock_info: {
          Closing_Stock: item.quantity,
          Min_Stock_Limit: item.threshold,
          Vendor: { vendor_name: (item.raw && item.raw.vendor_name) || 'Vendor_ABC' },
        },
        prompt: `Generate a detailed forecast report for ${item.name}.`,
      }),
      sessionId: '',
      executionId: generateId(),
      connectionID: 'react-native-frontend',
      isImage: false,
      base64string: '',
      evalId: '',
      userInputType: '',
    };

    try {
      const url = `${IGENTIC.endpointBase}/${IGENTIC.agentIdOrchestrator}`;
      const res = await fetch(url, { method: 'POST', headers: IGENTIC.headers, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();
      const parsed = parseAgentResponse(data.result || '', item);
      setParsedData(parsed);
      setShowModal(true);
    } catch (err) {
      setAgentError(err.message || String(err));
    } finally {
      setAgentLoading(false);
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
            placeholder="Search item..."
            placeholderTextColor={c.textSecondary}
            value={selectedItemSearch}
            onChangeText={setSelectedItemSearch}
          />
          <TouchableOpacity
            style={[styles.agentBtn, { backgroundColor: c.primary }]}
            onPress={() => {
              if (filteredInventory.length > 0) sendToAgent(filteredInventory[0]);
              else Alert.alert('Info', 'No item selected or available.');
            }}
            disabled={agentLoading}
          >
            <Text style={styles.agentBtnText}>{agentLoading ? '...' : 'Send to Agent'}</Text>
          </TouchableOpacity>
        </View>
      </View>

      <StatsGrid stats={stats} />
      <ChartsSection categoryChartData={categoryChartData} statusData={statusData} colors={chartC} />
      <LowStockAlerts lowStockAlerts={lowStockAlerts} />

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={[styles.sectionTitle, { color: c.text }]}>Inventory Management</Text>
          <TouchableOpacity
            style={[styles.addBtn, { backgroundColor: showAddForm ? c.textSecondary : c.primary }]}
            onPress={() => setShowAddForm(!showAddForm)}
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
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 3 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: spacing.md },
  header: { marginBottom: spacing.lg },
  pageTitle: { fontSize: 22, fontWeight: '700', marginBottom: spacing.sm },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  searchInput: { flex: 1, padding: spacing.md, borderRadius: 8, borderWidth: 1 },
  agentBtn: { paddingVertical: spacing.md, paddingHorizontal: spacing.lg, borderRadius: 8 },
  agentBtnText: { color: '#fff', fontWeight: '600' },
  section: { marginTop: spacing.lg },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md },
  sectionTitle: { fontSize: 18, fontWeight: '600' },
  addBtn: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: 8 },
  addBtnText: { color: '#fff', fontWeight: '600' },
  pagination: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.md, marginTop: spacing.lg },
  pageBtn: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: 8 },
  pageNum: { fontWeight: '600' },
  errorWrap: { padding: spacing.md, borderRadius: 8, marginTop: spacing.md },
  errorText: { fontSize: 14 },
});
