import { View, Text, StyleSheet } from "react-native";
import StatCard from "../../components/StatCard";

export default function DashboardScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>SmartCart AI Dashboard</Text>

      <StatCard label="Total Inventory Items" value="1,240" />
      <StatCard label="At-Risk Items" value="186" />
      <StatCard label="Agent Actions Today" value="42" />
      <StatCard label="Estimated Waste Reduction" value="18%" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20 },
  title: { fontSize: 22, fontWeight: "bold", marginBottom: 15 }
});
