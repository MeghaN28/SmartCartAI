import React, { createContext, useContext, useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const UserModeContext = createContext();
const STORAGE_KEY = 'user_mode';

export const useUserMode = () => {
  const context = useContext(UserModeContext);
  if (!context) throw new Error('useUserMode must be used within UserModeProvider');
  return context;
};

export const UserModeProvider = ({ children }) => {
  const [mode, setMode] = useState('inv_manager');

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY).then((saved) => {
      if (saved === 'admin' || saved === 'inv_manager') {
        setMode(saved);
      } else {
        setMode('inv_manager');
      }
    });
  }, []);

  useEffect(() => {
    AsyncStorage.setItem(STORAGE_KEY, mode);
  }, [mode]);

  const toggleMode = () => {
    setMode((prev) => (prev === 'admin' ? 'inv_manager' : 'admin'));
  };

  return (
    <UserModeContext.Provider value={{ mode, setMode, toggleMode }}>
      {children}
    </UserModeContext.Provider>
  );
};
