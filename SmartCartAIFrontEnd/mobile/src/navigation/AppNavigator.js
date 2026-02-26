import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { useUserMode } from '../contexts/UserModeContext';
import { colors, radius, spacing } from '../theme';
import Logo from '../components/Logo';

import HomeScreen from '../screens/HomeScreen';
import ChatbotScreen from '../screens/ChatbotScreen';
import DashboardScreen from '../screens/DashboardScreen';
import SuggestionLogScreen from '../screens/SuggestionLogScreen';
import RagasScreen from '../screens/RagasScreen';

const Tab = createBottomTabNavigator();

function TabIcon({ name, focused, theme }) {
  const c = colors[theme] || colors.dark;
  const icons = {
    Inventory: '📦',
    Chatbot: '💬',
    Dashboard: '📊',
    SuggestionLog: '💡',
    Ragas: '🧪',
  };
  return (
    <Text style={{ fontSize: 24, opacity: focused ? 1 : 0.55 }}>
      {icons[name] || '•'}
    </Text>
  );
}

function HeaderRight({ theme, toggleTheme, mode, toggleMode }) {
  const c = colors[theme] || colors.dark;
  return (
    <View style={styles.headerRightWrap}>
      <TouchableOpacity
        onPress={toggleMode}
        style={[styles.modeBtn, { backgroundColor: c.card, borderColor: c.border }]}
        activeOpacity={0.8}
      >
        <Text style={[styles.modeText, { color: c.text }]}>{mode === 'admin' ? 'ADMIN' : 'INV'}</Text>
      </TouchableOpacity>
      <TouchableOpacity
        onPress={toggleTheme}
        style={[styles.themeBtn, { backgroundColor: c.card, borderColor: c.border }]}
        activeOpacity={0.8}
      >
        <Text style={styles.themeEmoji}>{theme === 'dark' ? '☀️' : '🌙'}</Text>
      </TouchableOpacity>
    </View>
  );
}

function TabNavigator() {
  const { theme, toggleTheme } = useTheme();
  const { mode, toggleMode } = useUserMode();
  const c = colors[theme] || colors.dark;

  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: c.bg },
        headerTintColor: c.text,
        headerTitleStyle: { fontWeight: '700', fontSize: 18 },
        headerShadowVisible: false,
        tabBarStyle: {
          backgroundColor: c.card,
          borderTopColor: c.border,
          borderTopWidth: 1,
          paddingTop: spacing.sm,
          minHeight: 58,
        },
        tabBarActiveTintColor: c.tabActive,
        tabBarInactiveTintColor: c.tabInactive,
        tabBarLabelStyle: { fontWeight: '600', fontSize: 12 },
        tabBarItemStyle: { paddingVertical: 4 },
        headerRight: () => <HeaderRight theme={theme} toggleTheme={toggleTheme} mode={mode} toggleMode={toggleMode} />,
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
        name="SuggestionLog"
        component={SuggestionLogScreen}
        options={{
          title: 'Suggestions',
          tabBarIcon: ({ focused }) => <TabIcon name="SuggestionLog" focused={focused} theme={theme} />,
        }}
      />
      {mode === 'admin' ? (
        <Tab.Screen
          name="Ragas"
          component={RagasScreen}
          options={{
            title: 'RAGAS',
            tabBarIcon: ({ focused }) => <TabIcon name="Ragas" focused={focused} theme={theme} />,
          }}
        />
      ) : null}
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  headerRightWrap: { flexDirection: 'row', alignItems: 'center', marginRight: 8 },
  modeBtn: { marginRight: 8, paddingVertical: 8, paddingHorizontal: 10, borderRadius: radius.lg, borderWidth: 1 },
  modeText: { fontSize: 11, fontWeight: '700' },
  themeBtn: { marginRight: 14, padding: 10, borderRadius: radius.lg, borderWidth: 1 },
  themeEmoji: { fontSize: 20 },
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
