import { FlatList, Text } from "react-native";
import InventoryItem from "../components/InventoryItem";
import { InventoryItemType } from "../types/models";

const inventoryData: InventoryItemType[] = [
  { id: "P101", name: "Milk", stock: 120, expiryDays: 3, risk: "High" },
  { id: "P102", name: "Yogurt", stock: 85, expiryDays: 6, risk: "Medium" },
  { id: "P103", name: "Bread", stock: 200, expiryDays: 2, risk: "High" }
];

export default function InventoryScreen() {
  return (
    <>
      <Text style={{ fontSize: 20, margin: 15 }}>Inventory Overview</Text>
      <FlatList
        data={inventoryData}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <InventoryItem item={item} />}
      />
    </>
  );
}
