import { StyleSheet } from 'react-native';

export const colors = {
  canvas: '#EDF0F4',
  surface: '#FFFFFF',
  surfaceMuted: '#E9EDF1',
  surfaceStrong: '#DDE3E8',
  ink: '#121A26',
  inkMuted: '#5B6675',
  inkFaint: '#7D8794',
  line: '#D6DCE2',
  lineStrong: '#B7C0CA',
  navy: '#101827',
  navyRaised: '#182235',
  teal: '#087E8B',
  tealDark: '#075E68',
  tealSoft: '#DDF2F2',
  blue: '#2764D8',
  blueSoft: '#E6EEFD',
  positive: '#14804A',
  positiveSoft: '#DFF3E8',
  negative: '#C73E4D',
  negativeSoft: '#FBE5E7',
  warning: '#9A5B00',
  warningSoft: '#FFF0D6',
  purple: '#7357B8',
  pink: '#C74B8F',
  orange: '#C15A1F',
  indigo: '#4F5FA8',
  brown: '#B5651D',
  white: '#FFFFFF',
  transparent: 'transparent',

  // On-navy text — consolidates 7 near-duplicate grays previously hand-invented
  // per file (AppShell, money/invest/insiders/news/subscriptions screens).
  inkOnDarkMuted: '#A3AFC0',
  inkOnDarkFaint: '#75839A',

  // On-navy borders — consolidates 4 near-duplicate dark blue-grays.
  hairlineOnDark: '#2B3749',
  hairlineOnDarkStrong: '#526176',

  // Financial state tuned for the navy surface — promotes insiders.tsx's
  // already-shipped signal-pill trio to a shared primitive.
  positiveOnDark: '#8CE1B1',
  positiveOnDarkSoft: '#163B2B',
  positiveOnDarkBorder: '#3B8960',
  negativeOnDark: '#F1A0A9',
  negativeOnDarkSoft: '#44252D',
  negativeOnDarkBorder: '#A95660',

  // Solid status dot on a dark surface (AppShell sidebar) — distinct
  // lightness step from `positive` text-on-white.
  liveDotOnDark: '#32C98C',

  // Named borders that were previously repeated raw hex literals.
  accentSoftBorder: '#A6D9D9',
  negativeBorder: '#E8B9BE',
} as const;

/**
 * Semantic color roles. Components should read from `roles.*`, not `colors.*`
 * directly, so a future re-skin only ever touches this table. Deliberate hue
 * reuse (e.g. `live`/`attentionUrgent` sharing `positive`/`negative`) is not
 * laziness — Posted has five meaningfully different judgments a color can
 * carry (positive, negative, caution, informational/brand, neutral); `stale`/
 * `demo`/`urgent`/`live` are secondary labels for those same five judgments
 * applied to a different subsystem, not new hues.
 */
export const roles = {
  canvas: colors.canvas,
  surface: colors.surface,
  surfaceSunken: colors.surfaceMuted,
  surfaceSelected: colors.surfaceStrong,
  surfaceInverted: colors.navy,
  surfaceInvertedRaised: colors.navyRaised,

  textPrimary: colors.ink,
  textSecondary: colors.inkMuted,
  textTertiary: colors.inkFaint,
  textOnInvertedPrimary: colors.white,
  textOnInvertedSecondary: colors.inkOnDarkMuted,
  textOnInvertedTertiary: colors.inkOnDarkFaint,

  borderHairline: colors.line,
  borderHairlineStrong: colors.lineStrong,
  borderOnInverted: colors.hairlineOnDark,
  borderOnInvertedStrong: colors.hairlineOnDarkStrong,

  accent: colors.teal,
  accentPressed: colors.tealDark,
  accentSoft: colors.tealSoft,
  accentSoftBorder: colors.accentSoftBorder,

  positive: colors.positive,
  positiveSoft: colors.positiveSoft,
  positiveOnInverted: colors.positiveOnDark,
  positiveOnInvertedSoft: colors.positiveOnDarkSoft,
  positiveOnInvertedBorder: colors.positiveOnDarkBorder,

  negative: colors.negative,
  negativeSoft: colors.negativeSoft,
  negativeBorder: colors.negativeBorder,
  negativeOnInverted: colors.negativeOnDark,
  negativeOnInvertedSoft: colors.negativeOnDarkSoft,
  negativeOnInvertedBorder: colors.negativeOnDarkBorder,

  // Impact-feed priority tiers — `urgent` intentionally reuses `negative`
  // (a loss-coded red), not a new hue.
  attentionUrgent: colors.negative,
  attentionImportant: colors.warning,
  attentionNotable: colors.blue,
  attentionRoutine: colors.inkMuted,

  // Sync-freshness — a connection is `live` (no visual noise, unmarked
  // default) or `stale` (data older than its provider's sync SLA).
  live: colors.positive,
  liveDot: colors.liveDotOnDark,
  stale: colors.warning,

  // Sample vs. real data — reuses the accent hue so "demo" reads as
  // informational, never alarming.
  demo: colors.teal,
  demoSoft: colors.tealSoft,

  focusRing: colors.teal,
} as const;

/**
 * Categorical/chart-identity color, deliberately separate from `roles` — a
 * data-identity color must never collide with a state color (e.g. a chart
 * line tinted `warning` amber could be misread as "something's wrong").
 * `colors.teal`/`colors.blue`/`colors.warning` are excluded on purpose: teal
 * reads as gray in a categorical role (fails the chroma floor validated via
 * the dataviz skill's palette checker) and blue/warning are claimed semantic
 * roles that must never double as a decorative, hash-assigned color.
 */
export const chartCategorical = [
  colors.purple,
  colors.pink,
  colors.orange,
  colors.indigo,
  colors.brown,
] as const;

export const spacing = {
  xxs: 4,
  xs: 8,
  sm: 12,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
  /** A border simulated as a grid gap (the metric-row hairline-rule pattern) — not a spacing value to hand-pick. */
  hairlineGap: StyleSheet.hairlineWidth,
} as const;

export const radius = {
  sm: 4,
  /** 8, not 7 — a clean 2x of `spacing.xxs` instead of an unexplainable prime. */
  md: 8,
  lg: 12,
  /** Hero/inverted panels specifically — closes the 12-vs-16 drift already shipping across screens. */
  xl: 16,
  pill: 999,
} as const;

/** Control/icon sizing — pair a compact visual size with RN `hitSlop` to reach `touchMin` without inflating chrome. */
export const size = {
  touchMin: 44,
  controlSm: 32,
  controlMd: 44,
  controlLg: 52,
  iconSm: 16,
  iconMd: 20,
  iconLg: 24,
  avatar: 36,
} as const;

/** Soft elevation for card-style surfaces. Spread into a StyleSheet entry alongside borderRadius. */
export const cardShadow = {
  shadowColor: '#0B1420',
  shadowOpacity: 0.06,
  shadowRadius: 18,
  shadowOffset: { width: 0, height: 8 },
  elevation: 2,
} as const;

/** Elevation ladder — one depth strategy (shadow), not shadow + a second competing language. */
export const elevation = {
  /** = `cardShadow`, unchanged. Panels, cards, metric tiles. */
  raised: cardShadow,
  /** Dropdown menus, popovers — promotes AppShell's one-off user-menu shadow to a named token. */
  floating: {
    shadowColor: '#0B1420',
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  /** The assistant drawer's floating panel — one step past `floating`. */
  overlay: {
    shadowColor: '#0B1420',
    shadowOpacity: 0.18,
    shadowRadius: 28,
    shadowOffset: { width: 0, height: 12 },
    elevation: 10,
  },
} as const;

export const breakpoints = {
  /** Below this width, stack to one column and hide secondary columns/metrics. */
  compact: 720,
  /** Below this width AppShell swaps the sidebar for the bottom tab bar. */
  mobileNav: 920,
  /** At or above this width, a screen may use a 3rd column / extra density. */
  wide: 1280,
  /** At or above this width the assistant docks as a fixed right column. */
  assistantDock: 1600,
} as const;

/**
 * Legacy bare-number type scale. Kept unchanged (not replaced) because
 * `login.tsx` is the only current consumer and migrates to `textStyle` when
 * its own screen is redesigned (migration plan Phase D.1) — changing this
 * shape now would break that screen ahead of schedule for no visual benefit.
 */
export const type = {
  micro: 10,
  caption: 12,
  body: 14,
  bodyLarge: 16,
  title: 20,
  heading: 28,
  display: 38,
} as const;

/**
 * Replacement type scale, sized from what's already shipping across the app
 * (not invented) rather than the unused `type` scale above. Each step is a
 * full object so weight/line-height/tracking move together — today, e.g.,
 * "stat value" ships at 22/23/24/25px with drifting `marginTop` depending on
 * the file. New components (Phase A's `Panel`/`StatTile`/etc.) and screens
 * consume this as they migrate; `type` above is not removed until nothing
 * references it.
 */
export const textStyle = {
  label: { fontSize: 9, lineHeight: 12, fontWeight: '800', letterSpacing: 0.8 },
  labelWide: { fontSize: 10, lineHeight: 13, fontWeight: '700', letterSpacing: 1.4 },

  caption: { fontSize: 11, lineHeight: 15, fontWeight: '500', letterSpacing: 0 },
  body: { fontSize: 13, lineHeight: 18, fontWeight: '500', letterSpacing: 0 },
  bodyLarge: { fontSize: 15, lineHeight: 21, fontWeight: '500', letterSpacing: 0 },

  statValue: { fontSize: 22, lineHeight: 26, fontWeight: '700', letterSpacing: -0.2 },
  statValueLarge: { fontSize: 30, lineHeight: 35, fontWeight: '700', letterSpacing: -0.4 },

  panelTitle: { fontSize: 15, lineHeight: 20, fontWeight: '700', letterSpacing: -0.1 },
  pageTitle: { fontSize: 30, lineHeight: 36, fontWeight: '600', letterSpacing: -0.7 },
  pageTitleMobile: { fontSize: 25, lineHeight: 31, fontWeight: '600', letterSpacing: -0.5 },

  /** Login-only hero moment — the one screen the skill explicitly allows a bolder register. */
  display: { fontSize: 40, lineHeight: 46, fontWeight: '600', letterSpacing: -0.8 },
  displayDesktop: { fontSize: 56, lineHeight: 60, fontWeight: '600', letterSpacing: -1.2 },
} as const;

/**
 * Font family policy: system font stack for every role above (legibility,
 * zero load cost, matches how `textStyle` is consumed by default). These two
 * Google Fonts are the one deliberate exception, reserved for Direction B's
 * signature typographic distinction — "measured fact" (every number) vs.
 * "narrated context" (labels/prose) — not decoration. Loaded once in
 * `app/_layout.tsx`; nothing should reach for a third face.
 */
export const fontFamily = {
  numeric: 'SpaceMono_400Regular',
  narrative: 'Manrope_500Medium',
  narrativeBold: 'Manrope_700Bold',
} as const;

export const motion = {
  duration: {
    /** `prefers-reduced-motion` / `AccessibilityInfo.isReduceMotionEnabled()` fallback for everything below. */
    instant: 0,
    /** Micro-interactions: press, hover-in/out, toggle flip. */
    fast: 150,
    /** Panel/tab transitions, assistant drawer open/close, menu open/close. */
    base: 200,
  },
  easing: 'cubic-bezier(0.25, 1, 0.5, 1)',
  /** Digit-column settle on a real synced value change — spring, not a duration; never on first paint. */
  spring: { stiffness: 280, damping: 18, mass: 0.3 },
} as const;
