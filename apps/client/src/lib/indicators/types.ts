import type { PriceBar } from '@/lib/marketTypes';

export type IndicatorType = 'sma' | 'ema' | 'bollinger' | 'vwap' | 'rsi' | 'macd' | 'stochastic';
export type IndicatorCategory = 'trend' | 'momentum' | 'volume';
export type IndicatorKind = 'overlay' | 'oscillator';
export type IndicatorParams = Record<string, number>;
export type IndicatorSeries = Record<string, (number | null)[]>;

export type IndicatorInstance = {
  id: string;
  type: IndicatorType;
  params: IndicatorParams;
  color: string;
};

export type ParamSpec = {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
};

export type IndicatorDef = {
  type: IndicatorType;
  label: string;
  category: IndicatorCategory;
  kind: IndicatorKind;
  domain: 'price' | 'zeroToHundred' | 'auto';
  defaultParams: IndicatorParams;
  paramSpecs: ParamSpec[];
  shortLabel: (params: IndicatorParams) => string;
  formula: (params: IndicatorParams) => string;
  calculate: (bars: PriceBar[], params: IndicatorParams) => IndicatorSeries;
};
