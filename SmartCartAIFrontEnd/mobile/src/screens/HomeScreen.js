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

/** Days until expiry; negative if past. Null if no expiry set. */
const getDaysUntilExpiry = (expiryDate) => {
  if (!expiryDate) return null;
  const d = typeof expiryDate === 'string' ? new Date(expiryDate) : expiryDate;
  if (isNaN(d.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  d.setHours(0, 0, 0, 0);
  return Math.ceil((d - today) / (1000 * 60 * 60 * 24));
};

const isExpirySoon = (item, withinDays = 14) => {
  const days = getDaysUntilExpiry(item.expiryDate);
  return days != null && days >= 0 && days <= withinDays;
};

const statusLabels = { 'in-stock': 'In Stock', 'low-stock': 'Low Stock', 'out-of-stock': 'Out of Stock', 'expiry-soon': 'Expiry Soon' };

export default function HomeScreen() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const statusColors = { 'in-stock': c.success, 'low-stock': c.warning, 'out-of-stock': c.danger, 'expiry-soon': '#f97316' };
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStockStatus, setSelectedStockStatus] = useState('All');
  const [sortBy, setSortBy] = useState('name');
  const stockStatusOptions = ['All', 'In Stock', 'Low Stock', 'Out of Stock', 'Expiry Soon'];

  useEffect(() => {
    fetch(API.inventory)
      .then((res) => res.json())
      .then((data) => {
        const rawList = Array.isArray(data) ? data : (data.items || []);
        const formatted = rawList.map((item, index) => ({
          id: item.inventoryId || item.itemName || `item-${index}`,
          name: item.itemName || 'Unnamed',
          category: item.itemType || item.category || 'Unknown',
          quantity: item.openingStock ?? item.current_stock ?? 0,
          threshold: item.minStock ?? item.min_stock ?? 0,
          expiryDate: item.expiryDate || item.expiry_date || null,
          sellingPrice: item.sellingPrice ?? item.selling_price ?? null,
        }));
        setInventory(formatted);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filteredAndSortedInventory = useMemo(() => {
    let filtered = inventory.filter((item) => {
      const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase());
      const status = getStockStatus(item);
      const statusLabel = statusLabels[status];
      const expirySoon = isExpirySoon(item);
      const matchesStockStatus =
        selectedStockStatus === 'All' ||
        statusLabel === selectedStockStatus ||
        (selectedStockStatus === 'Expiry Soon' && expirySoon);
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
    expirySoon: inventory.filter((i) => isExpirySoon(i)).length,
  };

  if (loading) {
    return (
      <View style={[styles.centered, { backgroundColor: c.bg }]}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={[styles.loadingText, { color: c.textSecondary }]}>Loading inventory…</Text>
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
        getDaysUntilExpiry={getDaysUntilExpiry}
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
