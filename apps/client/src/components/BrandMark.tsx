import { StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme/tokens';

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <View style={styles.row}>
      <View style={styles.mark}>
        <View style={styles.markBarWide} />
        <View style={styles.markBarShort} />
      </View>
      {!compact && <Text style={styles.wordmark}>POSTED</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 11 },
  mark: {
    width: 27,
    height: 27,
    borderWidth: 1,
    borderColor: colors.teal,
    backgroundColor: colors.teal,
    justifyContent: 'center',
    paddingHorizontal: 6,
    gap: 4,
  },
  markBarWide: { height: 2, width: 13, backgroundColor: colors.white },
  markBarShort: { height: 2, width: 8, backgroundColor: colors.white },
  wordmark: {
    color: colors.white,
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 2.4,
  },
});

