export type MarketPeriod = '1D' | '5D' | '1M' | '6M' | '1Y' | '5Y';

export type MarketSearchResult = {
  symbol: string;
  name: string;
  exchange: string | null;
  asset_type: string;
  source: string;
  in_portfolio: boolean;
};

export type MarketQuote = {
  price: number;
  change: number;
  change_percent: number;
  open: number | null;
  high: number | null;
  low: number | null;
  previous_close: number | null;
  bid: number | null;
  ask: number | null;
  volume: number | null;
  timestamp: string;
  source: string;
  freshness: string;
};

export type CompanyProfile = {
  description: string | null;
  sector: string | null;
  industry: string | null;
  exchange: string | null;
  website: string | null;
  logo_url: string | null;
  market_cap: number | null;
  pe_ratio: number | null;
  dividend_yield: number | null;
  beta: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
};

export type EarningsResult = {
  date: string;
  fiscal_quarter: string | null;
  timing: string | null;
  eps_estimate: number | null;
  eps_actual: number | null;
  revenue_estimate: number | null;
  revenue_actual: number | null;
};

export type InsiderTransaction = {
  id: string;
  name: string;
  filing_date: string;
  transaction_date: string;
  transaction_code: string;
  shares_owned: number | null;
  shares_changed: number | null;
  transaction_price: number | null;
  currency: string;
  is_derivative: boolean;
};

export type InsiderSentimentPoint = {
  year: number;
  month: number;
  change: number;
  mspr: number;
};

export type InsiderActivitySummary = {
  latest_mspr: number | null;
  three_month_average_mspr: number | null;
  prior_three_month_average_mspr: number | null;
  mspr_trend: string;
  three_month_net_shares: number | null;
  open_market_purchases: number;
  open_market_sales: number;
  purchase_shares: number;
  sale_shares: number;
  purchase_value: number;
  sale_value: number;
  non_directional_transactions: number;
  signal: string;
  confidence: string;
};

export type InsiderInterpretation = {
  headline: string;
  summary: string;
  factors: string[];
  caveats: string[];
};

export type RelatedMarketNews = {
  id: string;
  headline: string;
  summary: string | null;
  source_name: string;
  source_url: string | null;
  occurred_at: string;
  event_type: string;
};

export type PortfolioPosition = {
  quantity: number;
  average_price: number | null;
  market_value: number;
  total_gain: number;
  total_gain_percent: number;
  portfolio_weight: number;
  account_count: number;
};

export type MarketProviderStatus = {
  name: string;
  role: string;
  status: string;
  detail: string;
};

export type StockDetailResponse = {
  symbol: string;
  name: string;
  asset_type: string;
  exchange: string | null;
  currency: string;
  quote: MarketQuote;
  company: CompanyProfile;
  earnings: EarningsResult[];
  insider_transactions: InsiderTransaction[];
  insider_sentiment: InsiderSentimentPoint[];
  related_news: RelatedMarketNews[];
  position: PortfolioPosition | null;
  providers: MarketProviderStatus[];
  is_demo: boolean;
  disclaimer: string;
};

export type InsiderAnalysisResponse = {
  symbol: string;
  name: string;
  quote: MarketQuote;
  position: PortfolioPosition | null;
  transactions: InsiderTransaction[];
  sentiment: InsiderSentimentPoint[];
  summary: InsiderActivitySummary;
  interpretation: InsiderInterpretation;
  one_month_price_change_percent: number | null;
  recent_news: RelatedMarketNews[];
  ai_insight: string | null;
  ai_available: boolean;
  source: string;
  updated_at: string;
  is_demo: boolean;
  disclaimer: string;
};

export type PortfolioInsiderWatchItem = {
  symbol: string;
  name: string;
  market_value: number;
  portfolio_weight: number;
  latest_mspr: number | null;
  three_month_average_mspr: number | null;
  three_month_net_shares: number | null;
  mspr_trend: string;
  signal: string;
  confidence: string;
};

export type PortfolioInsiderWatchResponse = {
  items: PortfolioInsiderWatchItem[];
  source: string;
  updated_at: string;
  is_demo: boolean;
};

export type PriceBar = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type StockHistoryResponse = {
  symbol: string;
  period: MarketPeriod;
  interval: '1Min' | '1Day';
  points: PriceBar[];
  source: string;
  freshness: string;
  last_updated: string;
  coverage_note: string;
  is_demo: boolean;
};
