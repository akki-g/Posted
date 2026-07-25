import { request } from './api';
import type {
  InsiderAnalysisResponse,
  MarketPeriod,
  MarketSearchResult,
  PortfolioInsiderWatchResponse,
  StockDetailResponse,
  StockHistoryResponse,
} from './marketTypes';

export const marketApi = {
  search: (query: string) =>
    request<MarketSearchResult[]>(`/market/search?q=${encodeURIComponent(query)}`),
  stock: (symbol: string) =>
    request<StockDetailResponse>(`/market/stocks/${encodeURIComponent(symbol)}`),
  history: (symbol: string, period: MarketPeriod) =>
    request<StockHistoryResponse>(
      `/market/stocks/${encodeURIComponent(symbol)}/history?period=${period}`,
    ),
  insiders: (symbol: string, ai = true) =>
    request<InsiderAnalysisResponse>(
      `/market/stocks/${encodeURIComponent(symbol)}/insiders?ai=${ai}`,
    ),
  portfolioInsiders: (limit = 25) =>
    request<PortfolioInsiderWatchResponse>(
      `/market/insiders/portfolio?limit=${limit}`,
    ),
  refreshNews: () =>
    request<{
      inserted: number;
      providers: string[];
      warnings: string[];
    }>('/feed/refresh', { method: 'POST' }),
};
