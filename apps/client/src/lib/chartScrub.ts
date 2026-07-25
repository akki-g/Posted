import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  PanResponder,
  type LayoutChangeEvent,
  type PanResponderGestureState,
  type PointerEvent,
} from 'react-native';

import { barIndexForX, pointIndexForX } from '@/lib/chartInteraction';

export type ChartScrubMode = 'point' | 'bar';

export type ChartScrub = {
  selectedIndex: number;
  onLayout: (event: LayoutChangeEvent) => void;
  panHandlers: ReturnType<typeof PanResponder.create>['panHandlers'];
  onPointerDown: (event: PointerEvent) => void;
  onPointerMove: (event: PointerEvent) => void;
  accessibilityValue: { min: number; max: number; now: number };
  onAccessibilityAction: (event: { nativeEvent: { actionName: string } }) => void;
};

export function useChartScrub(
  count: number,
  mode: ChartScrubMode,
  resetKey?: string | number,
): ChartScrub {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [chartWidth, setChartWidth] = useState(1);
  const lastIndex = Math.max(count - 1, 0);
  const selectedIndex = activeIndex == null ? lastIndex : Math.min(activeIndex, lastIndex);

  useEffect(() => {
    setActiveIndex(null);
  }, [resetKey]);

  const selectAt = useCallback(
    (x: number) => {
      if (count <= 0) return;
      const index =
        mode === 'bar' ? barIndexForX(x, chartWidth, count) : pointIndexForX(x, chartWidth, count);
      setActiveIndex(index);
    },
    [chartWidth, count, mode],
  );

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, gesture: PanResponderGestureState) =>
          Math.abs(gesture.dx) > Math.abs(gesture.dy),
        onShouldBlockNativeResponder: () => false,
        onPanResponderGrant: (event) => selectAt(event.nativeEvent.locationX),
        onPanResponderMove: (event) => selectAt(event.nativeEvent.locationX),
      }),
    [selectAt],
  );

  const onLayout = useCallback((event: LayoutChangeEvent) => {
    setChartWidth(Math.max(event.nativeEvent.layout.width, 1));
  }, []);

  const onPointerMove = useCallback(
    (event: PointerEvent) => {
      selectAt(event.nativeEvent.offsetX);
    },
    [selectAt],
  );

  const onAccessibilityAction = useCallback(
    (event: { nativeEvent: { actionName: string } }) => {
      const delta = event.nativeEvent.actionName === 'increment' ? 1 : -1;
      setActiveIndex((current) => Math.max(0, Math.min((current ?? lastIndex) + delta, lastIndex)));
    },
    [lastIndex],
  );

  return {
    selectedIndex,
    onLayout,
    panHandlers: panResponder.panHandlers,
    onPointerDown: onPointerMove,
    onPointerMove,
    accessibilityValue: { min: 0, max: lastIndex, now: selectedIndex },
    onAccessibilityAction,
  };
}
