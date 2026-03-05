import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { ThemeProvider, useTheme } from './src/contexts/ThemeContext';
import { UserModeProvider } from './src/contexts/UserModeContext';
import AppNavigator from './src/navigation/AppNavigator';
import { installGlobalAuthFetch } from './src/config';

// Install auth-aware fetch immediately so first screen requests include Bearer token.
installGlobalAuthFetch();

function AppContent() {
  const { theme } = useTheme();
  return (
    <>
      <StatusBar style={theme === 'dark' ? 'light' : 'dark'} />
      <AppNavigator />
    </>
  );
}

export default function App() {
  return (
    <UserModeProvider>
      <ThemeProvider>
        <AppContent />
      </ThemeProvider>
    </UserModeProvider>
  );
}
