# Security Page Chart Redesign: Prominent Chart, More Indicators, Signals

## Goal

Make the price chart on a security's page (`apps/client/src/app/stock/[symbol].tsx`) the visual focus of that page, add four more technical indicators (RSI, MACD, VWAP, Stochastic) alongside the existing SMA/EMA/Bollinger Bands, let users configure each indicator's parameters and add multiple instances of the same indicator, and surface buy/sell signal markers derived from indicator crossovers with a filter for which signal rules are shown.

## Background

`StockPriceChart.tsx` (824 lines) currently renders price, volume, and three fixed overlay indicators (SMA 20, EMA 20, Bollinger 20/2) in one SVG, with a hardcoded `INDICATOR_WINDOW = 20` baked into calculation, display strings, and formula text. Indicators are a flat on/off set (`activeIndicators: IndicatorKey[]`) — one instance per type, no parameters. The chart sits in a two-column page layout alongside quote metrics, earnings, and news, and is capped at a fixed ~292px height. This spec was scoped through a design conversation that settled:

- **Layout**: full-width hero chart at the top of the page; everything else moves below it.
- **New indicators**: RSI, MACD, VWAP, Stochastic Oscillator, in addition to the existing three.
- **Multi-instance**: users can add the same indicator type more than once with different parameters (e.g. SMA 20 and SMA 50 simultaneously).
- **Parameters**: a settings popover per indicator instance (gear icon → number inputs → Apply).
- **Signals**: crossover/threshold-derived buy/sell markers drawn on the price panel, filterable by rule and by bullish/bearish.
- **Filtering**: applies to signal markers (by rule, by direction) and to the indicator picker (grouped into Trend/Momentum/Volume categories).

This redesign also folds in several still-open findings from the prior chart-scrubbing review (`2026-07-25` code review), specifically the ones that live in code this spec rewrites anyway: the shared scrub/PanResponder duplication, the stale/contradictory assistant context on period switches, the length-keyed selection-reset bug, the daily-bar timezone label bug, the iOS `Intl.NumberFormat` compact-notation bug, and the per-scrub full-screen re-render. The count-based (vs. time-bucketed) bar aggregation in `aggregateBars` is explicitly **out of scope** — real issue, unrelated to this redesign, left as a follow-up.

## Design

### 1. Page layout

`stock/[symbol].tsx`'s content grid changes from "two columns side by side, chart in the main column" to "one full-width chart module, then two columns below it":

```
┌──────────────────────────────────────────────────┐
│  AAPL  $232.14  +1.2%          [1D 1W 1M 3M 1Y ▾] │  symbol header + period (existing, unchanged)
├──────────────────────────────────────────────────┤
│  [Trend ▾] [Momentum ▾] [Volume ▾]   [Bar: 1m ▾]  │  indicator picker (grouped) + bar-interval
│  [Signals: ✓Bullish ✓Bearish ✓SMA/EMA ✓MACD ...]  │  signal filter row
├──────────────────────────────────────────────────┤
│  OHLC / VOLUME / active-indicator-values readout  │  inspection row (existing pattern, extended)
├──────────────────────────────────────────────────┤
│              PRICE PANEL (full width, ~420px)     │  price + volume + overlays + signal marks
├──────────────────────────────────────────────────┤
│  RSI (14)                              ⚙  ✕       │  oscillator sub-panel, one per active instance
├──────────────────────────────────────────────────┤
│  MACD (12,26,9)                        ⚙  ✕       │  oscillator sub-panel
└──────────────────────────────────────────────────┘
┌───────────────────┐  ┌───────────────────┐
│  Quote metrics     │  │  Earnings          │        existing two-column content, now below the chart
│  Related news      │  │  Insider activity  │
└───────────────────┘  └───────────────────┘
```

The whole chart module is one full-width panel in `mainColumn`'s place; `mainColumn`/`sideColumn` keep their existing two-column content below it, unchanged except for losing the chart.

### 2. Module layout

`StockPriceChart.tsx` becomes a folder (import path `@/components/StockPriceChart` unchanged via `index.tsx`):

```
apps/client/src/components/StockPriceChart/
  index.tsx            orchestrator: instances, activeSignalFilters, resolution, scrub state;
                        renders IndicatorToolbar, readout, PricePanel, OscillatorPanel × N;
                        builds and exposes assistant context
  PricePanel.tsx        price/volume/overlay SVG + signal markers (today's chart, extended)
  OscillatorPanel.tsx    reusable sub-panel: title, series, y-domain, settings, remove
  IndicatorToolbar.tsx   grouped indicator picker, settings popovers, bar-interval control

apps/client/src/lib/indicators/
  types.ts              IndicatorType, IndicatorInstance, IndicatorDef, ParamSpec
  calculate.ts           one pure fn per type: (bars, params) => series
  registry.ts            INDICATOR_DEFS: single source of truth for label/category/
                          defaults/params/formula/overlay-vs-oscillator/domain
  signals.ts              detectCrossovers, detectThresholdCrosses, rule table
  calculate.test.ts
  signals.test.ts

apps/client/src/lib/
  chartScrub.ts          useChartScrub(pointCount, width) — shared crosshair/pan hook
```

### 3. Data model

```ts
type IndicatorType = 'sma' | 'ema' | 'bollinger' | 'vwap' | 'rsi' | 'macd' | 'stochastic';

type IndicatorInstance = {
  id: string;           // crypto.randomUUID() at creation
  type: IndicatorType;
  params: Record<string, number>;   // e.g. { period: 20 } or { fast: 12, slow: 26, signal: 9 }
  color: string;         // assigned from a rotating palette at creation
};

type IndicatorDef = {
  type: IndicatorType;
  label: string;
  category: 'trend' | 'momentum' | 'volume';
  kind: 'overlay' | 'oscillator';
  domain: 'price' | [number, number] | 'auto';   // 'price' = shares price scale, [0,100] = fixed, 'auto' = fit to data
  defaultParams: Record<string, number>;
  paramSpecs: { key: string; label: string; min: number; max: number; step: number }[];
  formula: (params: Record<string, number>) => string;
  calculate: (bars: PriceBar[], params: Record<string, number>) => IndicatorSeries;
};
```

`IndicatorSeries` is one or more named `(number | null)[]` arrays (e.g. `{ main: [...] }` for SMA/EMA/RSI/VWAP, `{ upper, lower, middle }` for Bollinger, `{ k, d }` for Stochastic, `{ line, signal, histogram }` for MACD) — each named series carries its own color/style so `PricePanel`/`OscillatorPanel` can render multi-line indicators generically.

`StockPriceChart/index.tsx` holds `instances: IndicatorInstance[]` (default: one SMA(20) instance, matching today's default-on behavior) and `activeSignalFilters: Set<string>` (default: all rules + both directions on). Adding an indicator from the toolbar appends a new instance with `INDICATOR_DEFS[type].defaultParams` and the next color from a palette not currently in use; the gear icon opens a popover editing one instance's `params`; the ✕ removes that instance. Two SMA instances are just two list entries with `type: 'sma'` and different `params.period`. The palette (theme tokens, see §8) needs at least 8–10 visually distinct colors so several same-type instances plus several different types stay distinguishable at once; once exhausted, colors repeat.

### 4. Indicator calculations

All four new indicators follow the existing null-until-warm-up pattern (`SMA`/`EMA`/`Bollinger` already do this):

- **RSI(period)**: Wilder's smoothing of average gains/losses over `period` bars; `null` until `period + 1` closes are available.
- **MACD(fast, slow, signal)**: `line = EMA(fast) − EMA(slow)`; `signal = EMA(signal) of line`; `histogram = line − signal`. `null` until `slow` bars are available for the line, `slow + signal` for signal/histogram.
- **VWAP**: cumulative `Σ(typical price × volume) / Σ volume` from the start of the visible range. Session resets (re-anchoring daily) are out of scope — see "Out of scope" below. No warm-up period — defined from the first bar.
- **Stochastic(%K period, %D period)**: `%K = 100 × (close − lowest low) / (highest high − lowest low)` over the %K period; `%D = SMA(%K, %D period)`. `null` until the %K period is available.

Existing SMA/EMA/Bollinger move into this same module unchanged in math, just parameterized instead of hardcoded to 20/2.

### 5. Panel rendering

`useChartScrub(pointCount, width)` (new, in `lib/chartScrub.ts`) owns: `selectedIndex` (defaulting to the latest point when nothing is selected — fixing the current length-keyed reset-effect bug by keying the "follow latest" behavior off data identity rather than `.length`), the `onLayout` width measurement, the `PanResponder` (with the Android scroll fix already applied: `onShouldBlockNativeResponder: () => false`, horizontal-intent gating on move), pointer handlers, and the accessibility increment/decrement wiring. `StockPriceChart/index.tsx` calls it once and passes `selectedIndex` down to every panel, so price and all oscillator panels stay crosshair-aligned; any panel's pan/pointer handlers call the same `selectAt`.

`useChartScrub` reuses `pointIndexForX` from `lib/chartInteraction.ts` (already unit-tested, already fixed for `preserveAspectRatio="none"` letterboxing) for its `selectAt` logic — no new pointer-mapping math.

`PricePanel.tsx` is today's SVG (price line/area, volume bars, gridlines, axis labels) plus: one path per overlay instance, and signal markers — small triangle glyphs at `(x, y)` of the bar where a filtered-in signal fired, bullish pointing up in `colors.positive`, bearish down in `colors.negative`.

`OscillatorPanel.tsx` is new and generic: given `{ title, instance, series, selectedIndex, onSettings, onRemove }`, it renders its own small SVG with either a fixed `[0, 100]` domain (RSI, Stochastic — with reference lines at 30/70 or 20/80) or an auto-fit domain around zero (MACD — histogram bars plus line/signal, zero line always drawn). One `OscillatorPanel` per oscillator-kind instance in `instances`, stacked in insertion order.

`IndicatorToolbar.tsx` reads `INDICATOR_DEFS`, groups by `category` into three collapsible sections (Trend, Momentum, Volume), each entry has an "Add" action; active instances show as removable chips with their gear icon. The bar-interval control is today's `availableResolutions` logic, moved into this file unchanged.

### 6. Signals

`lib/indicators/signals.ts` exposes:

- `detectCrossovers(seriesA, seriesB, meta)` → signals wherever A crosses above/below B (used for SMA×EMA/any two overlay instances' `main` series, and MACD's `line`×`signal`).
- `detectThresholdCrosses(series, threshold, meta)` → signals wherever a series crosses a fixed level from a given side (RSI crossing 70 downward = bearish/"exiting overbought", crossing 30 upward = bullish; Stochastic %K crossing 80/20 the same way).

`StockPriceChart/index.tsx` computes `signals = useMemo(() => [...detectCrossovers(...), ...detectThresholdCrosses(...)], [instances, displayPoints])` over the currently active instances (only pairs/instances that exist produce signals — no MACD signals if no MACD instance is active). Each signal carries a human-readable `rule` string (e.g. `"MACD signal cross"`, `"RSI overbought exit"`) used both as the filter-chip label and in the formula rail / assistant context.

`activeSignalFilters: Set<string>` starts as "all rule names currently present, both directions" and updates when the rule set changes (a rule chip appears/disappears as its generating instance is added/removed, defaulting new rules to on).

### 7. Assistant context & performance

The `onContextChange` string sent to `AssistantDrawer` is rewritten to describe: active bar interval, the inspected bar's OHLCV, every active indicator instance with its live value (id'd by type+params so "SMA 50" and "SMA 20" are distinguishable), and any signals at or near the inspected bar. Per the last review's finding, this is **not** pushed into `stock/[symbol].tsx` screen state on every pointer move — the orchestrator holds the latest context string in a `ref`, and `AppShell`'s `assistantContext` prop widens from `string` to `string | (() => string)`, resolved lazily at send-time when it's a function. `index.tsx` and `insiders.tsx` keep passing plain strings unchanged; only the stock page switches to the lazy form. This eliminates the full-screen re-render per scrub frame on the stock page (the other two pages' equivalent re-render-per-scrub finding from the last review is out of scope here — same fix pattern would apply if picked up later).

`formatVolume` drops `Intl.NumberFormat({ notation: 'compact' })` (unsupported by Hermes on iOS) for a small hand-rolled K/M/B formatter. `formatTrackingDate` omits time-of-day when the active resolution is a daily/weekly bar (`1D`/`1W`), fixing the fabricated-midnight-in-the-wrong-timezone bug.

### 8. Theming

Bollinger's hardcoded `'#7357B8'` becomes a token; add a small rotating chart-series palette to `theme/tokens.ts` (`colors.purple`, plus 2–3 more) so multi-instance indicators of different types get visually distinct, consistent colors instead of ad hoc hex literals.

### 9. Testing

- `lib/indicators/calculate.test.ts`: hand-computed expected values (Node test runner, same pattern as `chartInteraction.test.ts`) for RSI, MACD, VWAP, and Stochastic against a small synthetic bar sequence, at both default and custom params; existing SMA/EMA/Bollinger math re-verified against the parameterized versions.
- `lib/indicators/signals.test.ts`: `detectCrossovers` fed two synthetic series with one known cross point; `detectThresholdCrosses` fed a series with one known threshold cross in each direction.
- No new RN component-test harness — consistent with the prior review pass, verified via `tsc --noEmit`, the unit tests above, and a manual pass per the repo's `verify` skill (scrub across price + oscillator panels and confirm crosshair alignment; add two instances of the same indicator; edit params and confirm the line updates; toggle signal filters and confirm markers show/hide; confirm Android/iOS scroll and volume-formatting fixes hold).

### Out of scope

- Time-bucketed bar aggregation (replacing the current count-based `aggregateBars`) — real issue, unrelated to this redesign, left as a follow-up.
- Persisting indicator selections/params across sessions (localStorage) — resets per page load, matching today's behavior.
- VWAP session resets (daily anchor) — defined cumulatively from the first loaded bar for now.
