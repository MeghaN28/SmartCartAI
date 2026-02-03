import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing } from '../theme';
import { IGENTIC } from '../config';
import WelcomeScreen from '../components/WelcomeScreen';
import MessageList from '../components/MessageList';
import ChatInput from '../components/ChatInput';

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

export default function ChatbotScreen() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;

  const [messages, setMessages] = useState([
    {
      id: generateId(),
      text: "Hello! I'm your SmartCartAI assistant. Ask me about stock levels, item details, or search for specific items.",
      sender: 'bot',
      timestamp: new Date(),
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [agentError, setAgentError] = useState(null);
  const [mode, setMode] = useState('text');

  const sendToAgent = async (text) => {
    if (!text?.trim()) return;
    setIsProcessing(true);
    setAgentError(null);

    setMessages((prev) => [...prev, { id: generateId(), text, sender: 'user', timestamp: new Date() }]);

    const payload = {
      UserInput: text,
      sessionId: generateId(),
      executionId: generateId(),
      connectionID: 'react-native-chatbot',
      isImage: false,
      base64string: '',
      evalId: '',
      userInputType: 'text',
    };

    try {
      const url = `${IGENTIC.endpointBase}/${IGENTIC.agentIdChat}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: IGENTIC.headers,
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Agent error: ${res.status}`);

      const data = await res.json();
      const botMessageText = data.result || 'No response from agent.';

      setMessages((prev) => [...prev, { id: generateId(), text: botMessageText, sender: 'bot', timestamp: new Date() }]);
    } catch (err) {
      setAgentError(err.message);
      setMessages((prev) => [
        ...prev,
        { id: generateId(), text: `Error: ${err.message}`, sender: 'bot', timestamp: new Date() },
      ]);
    }
    setIsProcessing(false);
  };

  const handleSendMessage = (text) => {
    const t = (text || inputText || '').trim();
    if (!t || isProcessing) return;
    setInputText('');
    sendToAgent(t);
  };

  const quickQuestions = [
    'What items are low in stock?',
    'Show me all pain relief items',
    'How many items are out of stock?',
    "What's the total inventory count?",
  ];

  const handleQuickQuestion = (q) => {
    setInputText(q);
    setTimeout(() => handleSendMessage(q), 100);
  };

  return (
    <KeyboardAvoidingView style={[styles.container, { backgroundColor: c.bg }]} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
      {messages.length === 1 && (
        <WelcomeScreen quickQuestions={quickQuestions} handleQuickQuestion={handleQuickQuestion} />
      )}
      <MessageList messages={messages} isProcessing={isProcessing} />
      {mode === 'text' && (
        <ChatInput
          inputText={inputText}
          setInputText={setInputText}
          handleSendMessage={handleSendMessage}
          isProcessing={isProcessing}
        />
      )}
      {agentError ? (
        <View style={[styles.errorWrap, { backgroundColor: c.danger + '20' }]}>
          <Text style={[styles.errorText, { color: c.danger }]}>Agent Error: {agentError}</Text>
        </View>
      ) : null}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  errorWrap: { padding: spacing.sm, marginHorizontal: spacing.md, marginBottom: spacing.sm, borderRadius: 8 },
  errorText: { fontSize: 12 },
});
