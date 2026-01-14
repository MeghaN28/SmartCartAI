import { View, Text, StyleSheet } from "react-native";

export default function SustainabilityScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Sustainability Impact</Text>

      <Text>Waste Avoided: 312 units</Text>
      <Text>Cost Savings: $4,850</Text>
      <Text>Estimated CO₂ Reduction: 1.2 tons</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20 },
  title: { fontSize: 22, fontWeight: "bold", marginBottom: 10 }
});
