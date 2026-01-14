import { View, Text, StyleSheet } from "react-native";
import { DecisionType } from "../types/models";

type Props = {
  decision: DecisionType;
};

export default function DecisionCard({ decision }: Props) {
  return (
    <View style={styles.card}>
      <Text style={styles.product}>{decision.product}</Text>
      <Text>Action: {decision.action}</Text>
      <Text>Reason: {decision.reason}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { padding: 15, margin: 10, backgroundColor: "#f5f5f5" },
  product: { fontWeight: "bold" }
});
