import { Plus, Settings2, X } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { ResolutionOption } from '@/lib/chartInteraction';
import { INDICATOR_CATEGORY_LABELS, INDICATOR_DEFS } from '@/lib/indicators/registry';
import type { SignalDirection } from '@/lib/indicators/signals';
import type { IndicatorCategory, IndicatorInstance, IndicatorParams, IndicatorType } from '@/lib/indicators/types';
import { colors, radius } from '@/theme/tokens';

import { ParamPopover } from './ParamPopover';

const CATEGORIES: IndicatorCategory[] = ['trend', 'momentum', 'volume'];

type Props = {
  instances: IndicatorInstance[];
  onAdd: (type: IndicatorType) => void;
  onRemove: (id: string) => void;
  onUpdateParams: (id: string, params: IndicatorParams) => void;
  openSettingsId: string | null;
  onOpenSettings: (id: string) => void;
  onCloseSettings: () => void;
  resolutionOptions: ResolutionOption[];
  activeResolution: ResolutionOption;
  onSelectResolution: (key: ResolutionOption['key']) => void;
  signalRules: string[];
  activeSignalRules: Set<string>;
  onToggleSignalRule: (rule: string) => void;
  activeSignalDirections: Set<SignalDirection>;
  onToggleSignalDirection: (direction: SignalDirection) => void;
};

export function IndicatorToolbar({
  instances,
  onAdd,
  onRemove,
  onUpdateParams,
  openSettingsId,
  onOpenSettings,
  onCloseSettings,
  resolutionOptions,
  activeResolution,
  onSelectResolution,
  signalRules,
  activeSignalRules,
  onToggleSignalRule,
  activeSignalDirections,
  onToggleSignalDirection,
}: Props) {
  return (
    <View style={styles.root}>
      <View style={styles.pickerRow}>
        {CATEGORIES.map((category) => (
          <View style={styles.categoryGroup} key={category}>
            <Text style={styles.categoryLabel}>{INDICATOR_CATEGORY_LABELS[category].toUpperCase()}</Text>
            <View style={styles.categoryOptions}>
              {Object.values(INDICATOR_DEFS)
                .filter((def) => def.category === category)
                .map((def) => (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`Add ${def.label}`}
                    key={def.type}
                    onPress={() => onAdd(def.type)}
                    style={styles.addButton}>
                    <Plus size={11} color={colors.inkMuted} />
                    <Text style={styles.addButtonText}>{def.shortLabel(def.defaultParams)}</Text>
                  </Pressable>
                ))}
            </View>
          </View>
        ))}
        <View style={[styles.categoryGroup, styles.intervalGroup]}>
          <Text style={styles.categoryLabel}>BAR INTERVAL</Text>
          <View style={styles.categoryOptions}>
            {resolutionOptions.map((option) => (
              <Pressable
                accessibilityRole="button"
                accessibilityState={{ selected: activeResolution.key === option.key }}
                key={option.key}
                onPress={() => onSelectResolution(option.key)}
                style={[styles.intervalButton, activeResolution.key === option.key && styles.intervalButtonActive]}>
                <Text style={[styles.intervalText, activeResolution.key === option.key && styles.intervalTextActive]}>
                  {option.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      </View>

      {instances.length ? (
        <View style={styles.activeRow}>
          <Text style={styles.categoryLabel}>ACTIVE</Text>
          <View style={styles.activeChips}>
            {instances.map((instance) => {
              const def = INDICATOR_DEFS[instance.type];
              return (
                <View key={instance.id} style={styles.chipWrap}>
                  <View style={styles.chip}>
                    <View style={[styles.chipSwatch, { backgroundColor: instance.color }]} />
                    <Text style={styles.chipText}>{def.shortLabel(instance.params)}</Text>
                    {def.paramSpecs.length ? (
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={`${def.label} settings`}
                        onPress={() => (openSettingsId === instance.id ? onCloseSettings() : onOpenSettings(instance.id))}
                        style={styles.chipIcon}>
                        <Settings2 size={11} color={colors.inkMuted} />
                      </Pressable>
                    ) : null}
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={`Remove ${def.label}`}
                      onPress={() => onRemove(instance.id)}
                      style={styles.chipIcon}>
                      <X size={11} color={colors.inkMuted} />
                    </Pressable>
                  </View>
                  {openSettingsId === instance.id ? (
                    <ParamPopover
                      params={instance.params}
                      paramSpecs={def.paramSpecs}
                      onApply={(params) => {
                        onUpdateParams(instance.id, params);
                        onCloseSettings();
                      }}
                      onClose={onCloseSettings}
                    />
                  ) : null}
                </View>
              );
            })}
          </View>
        </View>
      ) : null}

      {signalRules.length ? (
        <View style={styles.signalRow}>
          <Text style={styles.categoryLabel}>SIGNALS</Text>
          <View style={styles.categoryOptions}>
            <FilterChip
              active={activeSignalDirections.has('bullish')}
              label="Bullish"
              onPress={() => onToggleSignalDirection('bullish')}
            />
            <FilterChip
              active={activeSignalDirections.has('bearish')}
              label="Bearish"
              onPress={() => onToggleSignalDirection('bearish')}
            />
            {signalRules.map((rule) => (
              <FilterChip active={activeSignalRules.has(rule)} key={rule} label={rule} onPress={() => onToggleSignalRule(rule)} />
            ))}
          </View>
        </View>
      ) : null}
    </View>
  );
}

function FilterChip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={[styles.filterChip, active && styles.filterChipActive]}>
      <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    position: 'relative',
    zIndex: 30,
    gap: 10,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  pickerRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 16 },
  categoryGroup: { gap: 6 },
  intervalGroup: { marginLeft: 'auto', alignItems: 'flex-end' },
  categoryLabel: { color: colors.inkFaint, fontSize: 8, fontWeight: '900', letterSpacing: 1 },
  categoryOptions: { flexDirection: 'row', flexWrap: 'wrap', gap: 5 },
  addButton: {
    minHeight: 28,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
    paddingHorizontal: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  addButtonText: { color: colors.inkMuted, fontSize: 9, fontWeight: '700' },
  intervalButton: {
    height: 28,
    minWidth: 32,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  intervalButtonActive: { borderColor: colors.teal, backgroundColor: colors.tealSoft },
  intervalText: { color: colors.inkMuted, fontSize: 9, fontWeight: '800' },
  intervalTextActive: { color: colors.tealDark },
  activeRow: { gap: 6 },
  activeChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chipWrap: { position: 'relative' },
  chip: {
    minHeight: 28,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    backgroundColor: colors.canvas,
    paddingHorizontal: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  chipSwatch: { width: 7, height: 7, borderRadius: 4 },
  chipText: { color: colors.ink, fontSize: 9, fontWeight: '700' },
  chipIcon: { width: 18, height: 18, alignItems: 'center', justifyContent: 'center' },
  signalRow: { gap: 6 },
  filterChip: {
    height: 26,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterChipActive: { borderColor: colors.lineStrong, backgroundColor: colors.canvas },
  filterChipText: { color: colors.inkFaint, fontSize: 9, fontWeight: '700' },
  filterChipTextActive: { color: colors.ink },
});
