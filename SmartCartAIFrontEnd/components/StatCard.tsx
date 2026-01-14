import { View, Text, StyleSheet } from "react-native";

type StatCardProps = {
  label: string;
  value: string | number;
};

export default function StatCard({ label, value }: StatCardProps) {
  return (
    <View style={styles.card}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    padding: 16,
    marginBottom: 12,
    borderRadius: 8,
    backgroundColor: "#f0f4f8",
    shadowColor: "#000",
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2
  },
  label: {
    fontSize: 14,
    color: "#555"
  },
  value: {
    fontSize: 20,
    fontWeight: "bold",
    marginTop: 4
  }
});
