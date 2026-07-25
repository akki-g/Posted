import { useCallback, useMemo, useRef, useState } from 'react';
import { PanResponder, StyleSheet, View, type PointerEvent } from 'react-native';
import Svg, { Path, Rect } from 'react-native-svg';

import { pointIndexForX } from '@/lib/chartInteraction';
import type { PriceBar } from '@/lib/marketTypes';
import { colors, radius } from '@/theme/tokens';

const WIDTH = 900;
const HEIGHT = 32;
const HANDLE_HIT_PX = 14;

function sparkPath(points: PriceBar[]): string {
  if (points.length < 2) return '';
  const values = points.map((point) => point.close);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * WIDTH;
      const y = HEIGHT - 5 - ((value - min) / range) * (HEIGHT - 10);
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');
}

type DragMode = 'move' | 'left' | 'right';

type Props = {
  points: PriceBar[];
  start: number;
  end: number;
  lastIndex: number;
  onChange: (start: number, end: number) => void;
};

export function RangeBrush({ points, start, end, lastIndex, onChange }: Props) {
  const [trackWidth, setTrackWidth] = useState(1);
  const drag = useRef<{ mode: DragMode; originIndex: number; startAtDown: number; endAtDown: number } | null>(
    null,
  );
  const count = points.length;
  const path = useMemo(() => sparkPath(points), [points]);

  const indexToX = useCallback(
    (index: number) => (lastIndex <= 0 ? 0 : (index / lastIndex) * WIDTH),
    [lastIndex],
  );
  const startX = indexToX(start);
  const endX = indexToX(end);

  const modeForOffset = useCallback(
    (offsetX: number): DragMode => {
      const pxPerUnit = trackWidth / WIDTH;
      const px = offsetX * pxPerUnit;
      const startPx = startX * pxPerUnit;
      const endPx = endX * pxPerUnit;
      if (Math.abs(px - startPx) <= HANDLE_HIT_PX) return 'left';
      if (Math.abs(px - endPx) <= HANDLE_HIT_PX) return 'right';
      return 'move';
    },
    [trackWidth, startX, endX],
  );

  const beginDrag = useCallback(
    (offsetX: number) => {
      const mode = modeForOffset(offsetX);
      const originIndex = pointIndexForX(offsetX, trackWidth, count);
      drag.current = { mode, originIndex, startAtDown: start, endAtDown: end };
    },
    [modeForOffset, trackWidth, count, start, end],
  );

  const continueDrag = useCallback(
    (offsetX: number) => {
      const active = drag.current;
      if (!active) return;
      const currentIndex = pointIndexForX(offsetX, trackWidth, count);
      const deltaIndex = currentIndex - active.originIndex;
      if (active.mode === 'left') {
        onChange(active.startAtDown + deltaIndex, active.endAtDown);
      } else if (active.mode === 'right') {
        onChange(active.startAtDown, active.endAtDown + deltaIndex);
      } else {
        onChange(active.startAtDown + deltaIndex, active.endAtDown + deltaIndex);
      }
    },
    [trackWidth, count, onChange],
  );

  const endDrag = useCallback(() => {
    drag.current = null;
  }, []);

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onShouldBlockNativeResponder: () => false,
        onPanResponderGrant: (event) => beginDrag(event.nativeEvent.locationX),
        onPanResponderMove: (event) => continueDrag(event.nativeEvent.locationX),
        onPanResponderRelease: endDrag,
        onPanResponderTerminate: endDrag,
      }),
    [beginDrag, continueDrag, endDrag],
  );

  const onPointerDown = useCallback(
    (event: PointerEvent) => beginDrag(event.nativeEvent.offsetX),
    [beginDrag],
  );
  const onPointerMove = useCallback(
    (event: PointerEvent) => continueDrag(event.nativeEvent.offsetX),
    [continueDrag],
  );

  return (
    <View
      {...panResponder.panHandlers}
      onLayout={(event) => setTrackWidth(Math.max(event.nativeEvent.layout.width, 1))}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      accessibilityRole="adjustable"
      accessibilityLabel="Chart zoom range"
      style={styles.track}>
      <Svg width="100%" height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none">
        <Path d={path} fill="none" stroke={colors.lineStrong} strokeWidth="1.1" />
        <Rect x={0} y={0} width={startX} height={HEIGHT} fill={colors.surfaceMuted} opacity={0.75} />
        <Rect
          x={endX}
          y={0}
          width={Math.max(WIDTH - endX, 0)}
          height={HEIGHT}
          fill={colors.surfaceMuted}
          opacity={0.75}
        />
        <Rect
          x={startX}
          y={0}
          width={Math.max(endX - startX, 2)}
          height={HEIGHT}
          fill={colors.teal}
          opacity={0.12}
          stroke={colors.teal}
          strokeWidth="1.4"
        />
        <Rect x={Math.max(startX - 1.4, 0)} y={0} width={2.8} height={HEIGHT} fill={colors.teal} />
        <Rect x={Math.min(endX - 1.4, WIDTH - 2.8)} y={0} width={2.8} height={HEIGHT} fill={colors.teal} />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    height: HEIGHT,
    borderRadius: radius.sm,
    overflow: 'hidden',
    cursor: 'grab',
  } as never,
});
