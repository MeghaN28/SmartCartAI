import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { colors, spacing, radius } from '../theme';
import { API } from '../config';
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
      text: "Hello! I'm your SmartCartAI assistant. I can analyze your inventory, check stock levels, and generate suggestions. Loading proactive alerts...",
      sender: 'bot',
      timestamp: new Date(),
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [agentError, setAgentError] = useState(null);
  const [mode, setMode] = useState('text');
  const [sessionId] = useState(() => generateId()); // Persistent session ID
  const [proactiveFetched, setProactiveFetched] = useState(false);

  // Proactive alerts: fetch waste/expired/out of stock/overstock and show before user asks
  useEffect(() => {
    if (proactiveFetched || messages.length > 1) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(API.agents.proactive, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId }),
        });
        if (cancelled) return;
        const data = await res.json().catch(() => ({}));
        const answer = data.answer || data.error || '';
        const suggestionNote = data.suggestions_count > 0
          ? `\n\n💡 ${data.suggestions_count} suggestion(s) saved. Check the Suggestions tab.`
          : '';
        setMessages((prev) => {
          if (prev.length !== 1) return prev;
          const welcome = prev[0];
          const welcomeText = "Hello! I'm your SmartCartAI assistant. I can analyze your inventory, check stock levels, and generate suggestions. Try asking: 'Check inventory and suggest actions' or 'What items need reordering?'";
          return [
            { ...welcome, text: welcomeText },
            { id: generateId(), text: (answer || 'No alerts right now.') + suggestionNote, sender: 'bot', timestamp: new Date() },
          ];
        });
      } catch (_) {
        if (!cancelled) {
          setMessages((prev) => {
            if (prev.length !== 1) return prev;
            return [{ ...prev[0], text: "Hello! I'm your SmartCartAI assistant. I can analyze your inventory, check stock levels, and generate suggestions. Try asking: 'Check inventory and suggest actions' or 'What items need reordering?'" }];
          });
        }
      } finally {
        if (!cancelled) setProactiveFetched(true);
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId, proactiveFetched, messages.length]);

  const sendToAgent = async (text) => {
    if (!text?.trim()) return;
    setIsProcessing(true);
    setAgentError(null);

    setMessages((prev) => [...prev, { id: generateId(), text, sender: 'user', timestamp: new Date() }]);

    const payload = {
      query: text,
      session_id: sessionId,
    };

    try {
      const res = await fetch(API.agents.chat, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `Server error: ${res.status}`);
      }

      const data = await res.json();
      let botMessageText = data.answer || data.error || 'No response from agent.';
      
      // Add suggestion count info if suggestions were generated
      if (data.suggestions_count > 0) {
        botMessageText += `\n\n💡 ${data.suggestions_count} suggestion(s) have been saved. Check the Suggestions tab to view them.`;
      }

      setMessages((prev) => [...prev, { id: generateId(), text: botMessageText, sender: 'bot', timestamp: new Date() }]);
    } catch (err) {
      setAgentError(err.message);
      const errorMessage = err.message.includes('fetch') 
        ? 'Unable to connect to the chat service. Please make sure the backend and chat agent are running.'
        : `Error: ${err.message}`;
      
      setMessages((prev) => [
        ...prev,
        { id: generateId(), text: errorMessage, sender: 'bot', timestamp: new Date() },
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
    'Check inventory and suggest actions',
    "What's going to waste?",
    'What items need reordering?',
    'Analyze low stock items',
    'Generate suggestions for inventory',
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
        <View style={[styles.errorWrap, { backgroundColor: c.danger + '18', borderColor: c.danger + '40' }]}>
          <Text style={[styles.errorText, { color: c.danger }]}>Agent Error: {agentError}</Text>
        </View>
      ) : null}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  errorWrap: { padding: spacing.md, marginHorizontal: spacing.lg, marginBottom: spacing.md, borderRadius: radius.lg, borderWidth: 1 },
  errorText: { fontSize: 13 },
});
