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
    <View style={styles.panel}>
      <View style={styles.fields}>
        {paramSpecs.map((spec) => (
          <View key={spec.key} style={styles.field}>
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
      </View>
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
  panel: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceMuted,
    paddingVertical: 8,
    paddingHorizontal: 10,
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 14,
  },
  fields: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 14, flexGrow: 1 },
  field: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  label: { color: colors.inkMuted, fontSize: 10, fontWeight: '600' },
  input: {
    width: 60,
    height: 28,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: 8,
    color: colors.ink,
    fontSize: 11,
    textAlign: 'right',
    backgroundColor: colors.surface,
  },
  actions: { flexDirection: 'row', gap: 6 },
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
