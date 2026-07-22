export type MoneyMovement = { amount: string; percent: string };

export type PortfolioSummary = {
  total_value: string;
  day_change: MoneyMovement;
  total_gain: MoneyMovement;
  last_synced_at: string | null;
  connection_status: string;
  demo_mode: boolean;
};

export type ChartPoint = { timestamp: string; value: string };

export type AccountSummary = {
  id: string;
  name: string;
  account_type: string;
  balance: string;
  day_change: string;
  total_gain: string;
};

export type HoldingSummary = {
  security_id: string;
  symbol: string;
  name: string;
  asset_type: string;
  sector: string | null;
  quantity: string;
  average_price: string | null;
  last_price: string | null;
  market_value: string;
  day_change: string;
  day_change_percent: string;
  total_gain: string;
  total_gain_percent: string;
  portfolio_weight: string;
  account_count: number;
};

export type EventReason = { code: string; message: string; value?: number | string | null };

export type EventSecurity = {
  security_id: string;
  symbol: string;
  name: string;
  match_confidence: string;
  effective_weight: string;
};

export type EventSummary = {
  id: string;
  event_type: string;
  headline: string;
  summary: string | null;
  occurred_at: string;
  source_name: string;
  source_url: string | null;
  score: string;
  level: 'urgent' | 'important' | 'notable' | 'informational';
  confidence: string;
  unread: boolean;
  is_demo: boolean;
  reasons: EventReason[];
  securities: EventSecurity[];
};

export type DashboardResponse = {
  portfolio: PortfolioSummary;
  history: ChartPoint[];
  accounts: AccountSummary[];
  top_holdings: HoldingSummary[];
  important_events: EventSummary[];
  unread_event_count: number;
};

export type FeedResponse = { items: EventSummary[]; unread_count: number; total: number };

export type ConnectionStatus = {
  id: string;
  provider: string;
  display_name: string;
  status: string;
  last_synced_at: string | null;
  account_count: number;
  demo_mode: boolean;
};

export type UserPreferences = {
  immediate_alert_level: string;
  push_enabled: boolean;
  email_digest_enabled: boolean;
  daily_briefing_time: string;
};

export type MoneyAccountSummary = {
  id: string;
  name: string;
  provider: string;
  account_type: string;
  mask: string | null;
  currency: string;
  current_balance: string;
  available_balance: string | null;
  credit_limit: string | null;
  is_liability: boolean;
};

export type MoneyTransactionSummary = {
  id: string;
  account_id: string;
  account_name: string;
  merchant_name: string;
  description: string;
  status: 'pending' | 'posted';
  direction: 'inflow' | 'outflow';
  amount: string;
  currency: string;
  occurred_at: string;
  category: string;
  payment_channel: string | null;
  is_transfer: boolean;
  is_recurring: boolean;
};

export type SpendingCategorySummary = {
  category: string;
  label: string;
  amount: string;
  percent: string;
};

export type DailySpendingPoint = { date: string; amount: string };

export type RecurringStreamSummary = {
  id: string;
  merchant_name: string;
  frequency: string;
  average_amount: string;
  last_amount: string;
  currency: string;
  last_charged_at: string;
  next_expected_date: string;
  confidence: string;
  status: string;
};

export type MoneyConnectionStatus = {
  id: string;
  provider: string;
  display_name: string;
  status: string;
  last_synced_at: string | null;
  account_count: number;
  is_demo: boolean;
};

export type MoneyTransactionsResponse = {
  items: MoneyTransactionSummary[];
  total: number;
};

export type MoneyOverviewResponse = {
  cash_balance: string;
  card_balance: string;
  net_cash_position: string;
  weekly_spending: string;
  weekly_income: string;
  monthly_recurring: string;
  annualized_recurring: string;
  last_synced_at: string | null;
  demo_mode: boolean;
  spending_by_category: SpendingCategorySummary[];
  daily_spending: DailySpendingPoint[];
  accounts: MoneyAccountSummary[];
  recent_transactions: MoneyTransactionSummary[];
  subscriptions: RecurringStreamSummary[];
};
