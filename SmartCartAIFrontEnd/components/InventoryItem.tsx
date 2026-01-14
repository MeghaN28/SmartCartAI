import { View, Text, StyleSheet } from "react-native";
import { InventoryItemType } from "../types/models";

type Props = {
  item: InventoryItemType;
};

export default function InventoryItem({ item }: Props) {
  return (
    <View style={styles.card}>
      <Text style={styles.name}>{item.name}</Text>
      <Text>Stock: {item.stock}</Text>
      <Text>Days to Expiry: {item.expiryDays}</Text>
      <Text>Waste Risk: {item.risk}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { padding: 15, borderBottomWidth: 1 },
  name: { fontWeight: "bold", fontSize: 16 }
});
