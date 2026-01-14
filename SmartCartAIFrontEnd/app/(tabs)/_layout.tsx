import { Tabs } from "expo-router";

export default function Layout() {
  return (
    <Tabs screenOptions={{ headerShown: true }}>
      <Tabs.Screen name="index" options={{ title: "Dashboard" }} />
      <Tabs.Screen name="inventory" options={{ title: "Inventory" }} />
      <Tabs.Screen name="decisions" options={{ title: "Decisions" }} />
      <Tabs.Screen name="impact" options={{ title: "Impact" }} />
    </Tabs>
  );
}
