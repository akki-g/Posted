import { Platform } from 'react-native';

import { getToken } from './auth';
import type {
  AssistantConversationResponse,
  AssistantMessageSummary,
  AuthUser,
  ConnectionStatus,
  DashboardResponse,
  EventSummary,
  FeedResponse,
  HoldingSummary,
  MoneyConnectionStatus,
  MoneyOverviewResponse,
  MoneyTransactionsResponse,
  MoneySyncResponse,
  MorningDebriefResponse,
  NewsRefreshResponse,
  PlaidLinkTokenResponse,
  RecurringStreamSummary,
  SchwabStatus,
  UserPreferences,
} from './types';

const configuredUrl = process.env.EXPO_PUBLIC_API_URL;

export const API_URL =
  configuredUrl ??
  (Platform.OS === 'android'
    ? 'http://10.0.2.2:8000/api/v1'
    : 'http://127.0.0.1:8000/api/v1');

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.text();
    let message = body;
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      message = parsed.detail ?? body;
    } catch {
      // Keep non-JSON provider and proxy errors readable.
    }
    throw new Error(message || `Posted API returned ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<DashboardResponse>('/dashboard'),
  holdings: () => request<HoldingSummary[]>('/holdings'),
  feed: (query = '') => request<FeedResponse>(`/feed${query}`),
  refreshNews: () => request<NewsRefreshResponse>('/feed/refresh', { method: 'POST' }),
  morningDebrief: () => request<MorningDebriefResponse>('/feed/debrief'),
  event: (id: string) => request<EventSummary>(`/feed/${id}`),
  markRead: (id: string) => request<void>(`/feed/${id}/read`, { method: 'POST' }),
  connections: () => request<ConnectionStatus[]>('/connections'),
  schwabStatus: () => request<SchwabStatus>('/connections/schwab/status'),
  authorizeSchwab: () =>
    request<{ authorization_url: string }>('/connections/schwab/authorize'),
  authorizeGoogle: () =>
    request<{ authorization_url: string }>('/auth/google/authorize'),
  me: () => request<AuthUser>('/auth/me'),
  preferences: () => request<UserPreferences>('/settings'),
  updatePreferences: (preferences: UserPreferences) =>
    request<UserPreferences>('/settings', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    }),
  sync: (connectionId: string) =>
    request<{ sync_run_id: string; status: string; message: string }>(
      `/connections/${connectionId}/sync`,
      {
        method: 'POST',
        body: JSON.stringify({ idempotency_key: `manual-${Date.now()}` }),
      },
    ),
  moneyOverview: () => request<MoneyOverviewResponse>('/money/overview'),
  moneyTransactions: (query = '') =>
    request<MoneyTransactionsResponse>(`/money/transactions${query}`),
  subscriptions: () => request<RecurringStreamSummary[]>('/money/subscriptions'),
  moneyConnections: () => request<MoneyConnectionStatus[]>('/money/connections'),
  plaidStatus: () =>
    request<{ configured: boolean; environment: string; demo_mode: boolean; message: string }>(
      '/money/connections/plaid/status',
    ),
  plaidLinkToken: () =>
    request<PlaidLinkTokenResponse>('/money/connections/plaid/link-token', { method: 'POST' }),
  exchangePlaidToken: (publicToken: string) =>
    request<MoneyConnectionStatus>('/money/connections/plaid/exchange', {
      method: 'POST',
      body: JSON.stringify({ public_token: publicToken }),
    }),
  syncMoneyConnection: (connectionId: string) =>
    request<MoneySyncResponse>(`/money/connections/plaid/${connectionId}/sync`, {
      method: 'POST',
    }),
  assistantConversation: () => request<AssistantConversationResponse>('/assistant/messages'),
  sendAssistantMessage: (message: string, section: string) =>
    request<AssistantMessageSummary>('/assistant/messages', {
      method: 'POST',
      body: JSON.stringify({ message, section }),
    }),
  clearAssistantConversation: () =>
    request<void>('/assistant/messages', { method: 'DELETE' }),
};
