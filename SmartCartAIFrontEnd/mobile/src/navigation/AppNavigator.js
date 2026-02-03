import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors } from '../theme';
import Logo from '../components/Logo';

import HomeScreen from '../screens/HomeScreen';
import ChatbotScreen from '../screens/ChatbotScreen';
import DashboardScreen from '../screens/DashboardScreen';
import UploadPurchaseScreen from '../screens/UploadPurchaseScreen';
import ReorderLogScreen from '../screens/ReorderLogScreen';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

function TabIcon({ name, focused, theme }) {
  const c = colors[theme] || colors.dark;
  const icons = {
    Inventory: '📦',
    Chatbot: '💬',
    Dashboard: '📊',
    Upload: '📤',
    ReorderLog: '📋',
  };
  return <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.6 }}>{icons[name] || '•'}</Text>;
}

function HeaderRight({ theme, toggleTheme }) {
  const c = colors[theme] || colors.dark;
  return (
    <TouchableOpacity onPress={toggleTheme} style={[styles.themeBtn, { backgroundColor: c.card }]}>
      <Text style={styles.themeEmoji}>{theme === 'dark' ? '☀️' : '🌙'}</Text>
    </TouchableOpacity>
  );
}

function TabNavigator() {
  const { theme, toggleTheme } = useTheme();
  const c = colors[theme] || colors.dark;

  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: c.bg },
        headerTintColor: c.text,
        headerTitleStyle: { fontWeight: '600' },
        tabBarStyle: { backgroundColor: c.card, borderTopColor: c.border },
        tabBarActiveTintColor: c.tabActive,
        tabBarInactiveTintColor: c.tabInactive,
        headerRight: () => <HeaderRight theme={theme} toggleTheme={toggleTheme} />,
      }}
    >
      <Tab.Screen
        name="Inventory"
        component={HomeScreen}
        options={{
          headerTitle: () => <Logo />,
          tabBarIcon: ({ focused }) => <TabIcon name="Inventory" focused={focused} theme={theme} />,
        }}
      />
      <Tab.Screen
        name="Chatbot"
        component={ChatbotScreen}
        options={{
          title: 'Chatbot',
          tabBarIcon: ({ focused }) => <TabIcon name="Chatbot" focused={focused} theme={theme} />,
        }}
      />
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{
          title: 'Dashboard',
          tabBarIcon: ({ focused }) => <TabIcon name="Dashboard" focused={focused} theme={theme} />,
        }}
      />
      <Tab.Screen
        name="Upload"
        component={UploadPurchaseScreen}
        options={{
          title: 'Upload',
          tabBarIcon: ({ focused }) => <TabIcon name="Upload" focused={focused} theme={theme} />,
        }}
      />
      <Tab.Screen
        name="ReorderLog"
        component={ReorderLogScreen}
        options={{
          title: 'Reorder Log',
          tabBarIcon: ({ focused }) => <TabIcon name="ReorderLog" focused={focused} theme={theme} />,
        }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  themeBtn: { marginRight: 12, padding: 6, borderRadius: 8 },
  themeEmoji: { fontSize: 18 },
});

export default function AppNavigator() {
  const c = colors.dark;
  return (
    <NavigationContainer
      theme={{
        dark: true,
        colors: { primary: c.primary, background: c.bg, card: c.card, text: c.text, border: c.border, notification: c.primary },
      }}
    >
      <TabNavigator />
    </NavigationContainer>
  );
}
