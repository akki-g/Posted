import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import type { IndicatorParams, ParamSpec } from '@/lib/indicators/types';
import { colors, radius } from '@/theme/tokens';

type Props = {
  params: IndicatorParams;
  paramSpecs: ParamSpec[];
  onApply: (params: IndicatorParams) => void;
  onClose: () => void;
};

export function ParamPopover({ params, paramSpecs, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<Record<string, string>>(
    Object.fromEntries(paramSpecs.map((spec) => [spec.key, String(params[spec.key])])),
  );

  const apply = () => {
    const next: IndicatorParams = { ...params };
    for (const spec of paramSpecs) {
      const parsed = Number(draft[spec.key]);
      if (Number.isFinite(parsed)) {
        next[spec.key] = Math.min(spec.max, Math.max(spec.min, parsed));
      }
    }
    onApply(next);
  };

  return (
    <View style={styles.popover}>
      {paramSpecs.map((spec) => (
        <View key={spec.key} style={styles.row}>
          <Text style={styles.label}>{spec.label}</Text>
          <TextInput
            accessibilityLabel={spec.label}
            keyboardType="numeric"
            onChangeText={(text) => setDraft((current) => ({ ...current, [spec.key]: text }))}
            style={styles.input}
            value={draft[spec.key]}
          />
        </View>
      ))}
      <View style={styles.actions}>
        <Pressable accessibilityRole="button" onPress={onClose} style={styles.button}>
          <Text style={styles.buttonText}>Cancel</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={apply} style={[styles.button, styles.buttonPrimary]}>
          <Text style={[styles.buttonText, styles.buttonTextPrimary]}>Apply</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  popover: {
    position: 'absolute',
    top: 26,
    right: 0,
    zIndex: 20,
    width: 200,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
    padding: 10,
    gap: 8,
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  label: { color: colors.inkMuted, fontSize: 10, fontWeight: '600' },
  input: {
    width: 64,
    height: 28,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: 8,
    color: colors.ink,
    fontSize: 11,
    textAlign: 'right',
  },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 6, marginTop: 2 },
  button: {
    height: 28,
    paddingHorizontal: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.line,
  },
  buttonPrimary: { backgroundColor: colors.teal, borderColor: colors.teal },
  buttonText: { color: colors.inkMuted, fontSize: 10, fontWeight: '700' },
  buttonTextPrimary: { color: colors.white },
});
