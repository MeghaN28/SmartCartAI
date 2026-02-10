import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, radius } from '../theme';
import Logo from '../components/Logo';

import HomeScreen from '../screens/HomeScreen';
import ChatbotScreen from '../screens/ChatbotScreen';
import DashboardScreen from '../screens/DashboardScreen';
import UploadPurchaseScreen from '../screens/UploadPurchaseScreen';
import SuggestionLogScreen from '../screens/SuggestionLogScreen';

const Tab = createBottomTabNavigator();

function TabIcon({ name, focused, theme }) {
  const c = colors[theme] || colors.dark;
  const icons = {
    Inventory: '📦',
    Chatbot: '💬',
    Dashboard: '📊',
    Upload: '📤',
    SuggestionLog: '💡',
  };
  return (
    <Text style={{ fontSize: 22, opacity: focused ? 1 : 0.5 }}>
      {icons[name] || '•'}
    </Text>
  );
}

function HeaderRight({ theme, toggleTheme }) {
  const c = colors[theme] || colors.dark;
  return (
    <TouchableOpacity
      onPress={toggleTheme}
      style={[styles.themeBtn, { backgroundColor: c.card, borderColor: c.border }]}
      activeOpacity={0.8}
    >
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
        headerTitleStyle: { fontWeight: '700', fontSize: 17 },
        headerShadowVisible: false,
        tabBarStyle: {
          backgroundColor: c.card,
          borderTopColor: c.border,
          borderTopWidth: 1,
        },
        tabBarActiveTintColor: c.tabActive,
        tabBarInactiveTintColor: c.tabInactive,
        tabBarLabelStyle: { fontWeight: '600', fontSize: 11 },
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
        name="SuggestionLog"
        component={SuggestionLogScreen}
        options={{
          title: 'Suggestions',
          tabBarIcon: ({ focused }) => <TabIcon name="SuggestionLog" focused={focused} theme={theme} />,
        }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  themeBtn: { marginRight: 12, padding: 8, borderRadius: radius.md, borderWidth: 1 },
  themeEmoji: { fontSize: 18 },
});

export default function AppNavigator() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const isDark = theme === 'dark';

  return (
    <NavigationContainer
      theme={{
        dark: isDark,
        colors: {
          primary: c.primary,
          background: c.bg,
          card: c.card,
          text: c.text,
          border: c.border,
          notification: c.primary,
        },
      }}
    >
      <TabNavigator />
    </NavigationContainer>
  );
}
