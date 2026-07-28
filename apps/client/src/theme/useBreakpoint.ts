import { useWindowDimensions } from 'react-native';

import { breakpoints } from './tokens';

/**
 * Shared breakpoint derivation. No screen should compute its own
 * `useWindowDimensions().width >= <ad hoc number>` — seven screens
 * previously each declared a slightly different cutoff, producing dead
 * zones where shell chrome and content layout disagreed on "desktop."
 */
export function useBreakpoint() {
  const { width } = useWindowDimensions();
  return {
    width,
    compact: width < breakpoints.compact,
    desktop: width >= breakpoints.mobileNav,
    wide: width >= breakpoints.wide,
    assistantDocked: width >= breakpoints.assistantDock,
  };
}
