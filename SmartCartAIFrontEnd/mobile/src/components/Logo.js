import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import Svg, { Path, Rect, Line, Circle } from 'react-native-svg';
import { colors } from '../theme';

export default function Logo() {
  const { theme } = useTheme();
  const c = colors[theme] || colors.dark;
  const stroke = c.primary;

  return (
    <View style={styles.container}>
      <Svg width={28} height={28} viewBox="0 0 60 60">
        <Path
          d="M30 10L40 15L45 25L40 35L30 40L20 35L15 25L20 15L30 10Z"
          stroke={stroke}
          strokeWidth={2}
          fill="none"
        />
        <Rect
          x={25}
          y={25}
          width={10}
          height={10}
          stroke={stroke}
          strokeWidth={1.5}
          fill="none"
        />
        <Line
          x1={30}
          y1={10}
          x2={30}
          y2={5}
          stroke={stroke}
          strokeWidth={1.5}
          strokeLinecap="round"
        />
        <Circle cx={30} cy={5} r={2} fill={stroke} />
        <Line
          x1={30}
          y1={40}
          x2={30}
          y2={45}
          stroke={stroke}
          strokeWidth={1.5}
          strokeLinecap="round"
        />
        <Circle cx={30} cy={45} r={2} fill={stroke} />
        <Line
          x1={20}
          y1={25}
          x2={15}
          y2={25}
          stroke={stroke}
          strokeWidth={1.5}
          strokeLinecap="round"
        />
        <Circle cx={15} cy={25} r={2} fill={stroke} />
        <Line
          x1={40}
          y1={25}
          x2={45}
          y2={25}
          stroke={stroke}
          strokeWidth={1.5}
          strokeLinecap="round"
        />
        <Circle cx={45} cy={25} r={2} fill={stroke} />
      </Svg>
      <Text style={[styles.text, { color: c.text }]}>
        <Text style={[styles.accent, { color: c.primary }]}>SmartCart</Text>
        <Text style={styles.suffix}>AI</Text>
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  text: { fontSize: 15, fontWeight: '700' },
  accent: {},
  suffix: { opacity: 0.9 },
});
