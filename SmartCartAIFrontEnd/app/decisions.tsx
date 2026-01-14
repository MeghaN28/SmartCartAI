import { FlatList, Text } from "react-native";
import DecisionCard from "../components/DecisionCard";
import { DecisionType } from "../types/models";

const decisions: DecisionType[] = [
  {
    id: "D01",
    product: "Milk",
    action: "Apply 20% Discount",
    reason: "High spoilage risk and low demand velocity"
  },
  {
    id: "D02",
    product: "Bread",
    action: "Bundle with Eggs",
    reason: "Near expiry with moderate demand"
  }
];

export default function AgentDecisionScreen() {
  return (
    <>
      <Text style={{ fontSize: 20, margin: 15 }}>
        Autonomous Agent Decisions
      </Text>
      <FlatList
        data={decisions}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <DecisionCard decision={item} />}
      />
    </>
  );
}
