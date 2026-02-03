import React, { useState, useEffect, useMemo } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing } from '../theme';
import { API } from '../config';
import HeroSection from '../components/HeroSection';
import SearchBar from '../components/SearchBar';
import FilterSection from '../components/FilterSection';
import InventoryGrid from '../components/InventoryGrid';

const getStockStatus = (item) => {
  if (item.quantity === 0) return 'out-of-stock';
  if (item.quantity > 0 && item.quantity <= item.threshold) return 'low-stock';
  return 'in-stock';
};

const statusLabels = { 'in-stock': 'In Stock', 'low-stock': 'Low Stock', 'out-of-stock': 'Out of Stock' };
const statusColors = { 'in-stock': '#10b981', 'low-stock': '#f59e0b', 'out-of-stock': '#ef4444' };

export default function HomeScreen() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStockStatus, setSelectedStockStatus] = useState('All');
  const [sortBy, setSortBy] = useState('name');
  const stockStatusOptions = ['All', 'In Stock', 'Low Stock', 'Out of Stock'];

  useEffect(() => {
    fetch(API.inventory)
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          const formatted = (data.items || []).map((item) => ({
            id: item.inventory_id,
            name: item.item_name,
            category: item.item_type || 'Unknown',
            quantity: item.current_stock || 0,
            threshold: item.min_stock || 0,
          }));
          setInventory(formatted);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filteredAndSortedInventory = useMemo(() => {
    let filtered = inventory.filter((item) => {
      const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase());
      const status = getStockStatus(item);
      const statusLabel = statusLabels[status];
      const matchesStockStatus = selectedStockStatus === 'All' || statusLabel === selectedStockStatus;
      return matchesSearch && matchesStockStatus;
    });
    if (selectedStockStatus !== 'All') {
      const seen = new Set();
      filtered = filtered.filter((item) => {
        const key = item.name.toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    }
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name': return a.name.localeCompare(b.name);
        case 'quantity': return b.quantity - a.quantity;
        case 'category': return a.category.localeCompare(b.category);
        case 'status':
          const order = { 'out-of-stock': 0, 'low-stock': 1, 'in-stock': 2 };
          return order[getStockStatus(a)] - order[getStockStatus(b)];
        default: return 0;
      }
    });
    return filtered;
  }, [inventory, searchTerm, selectedStockStatus, sortBy]);

  const stats = {
    total: inventory.length,
    inStock: inventory.filter((i) => getStockStatus(i) === 'in-stock').length,
    lowStock: inventory.filter((i) => getStockStatus(i) === 'low-stock').length,
    outOfStock: inventory.filter((i) => getStockStatus(i) === 'out-of-stock').length,
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
      <HeroSection stats={stats} />
      <View style={styles.searchFilter}>
        <SearchBar searchTerm={searchTerm} setSearchTerm={setSearchTerm} />
        <FilterSection
          sortBy={sortBy}
          setSortBy={setSortBy}
          selectedStockStatus={selectedStockStatus}
          setSelectedStockStatus={setSelectedStockStatus}
          stockStatusOptions={stockStatusOptions}
        />
      </View>
      <InventoryGrid
        filteredAndSortedInventory={filteredAndSortedInventory}
        getStockStatus={getStockStatus}
        statusLabels={statusLabels}
        statusColors={statusColors}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 2 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: spacing.md },
  searchFilter: { marginBottom: spacing.lg },
});
