import { useQuery, useMutation, UseMutationOptions } from '@tanstack/react-query';
import { apiFetch, queryClient } from './client';

export interface Ticker {
  id: number;
  symbol: string;
  name: string;
  exchange: string;
  sector: string;
  industry: string;
  market_cap: string;
  active: boolean;
  updated_at: string;
}

export interface OHLCVBar {
  ticker_id: number;
  date?: string;
  ts?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap?: number;
  adj_close?: number;
}

export function useTickers(params?: Record<string, string | number>) {
  const queryStr = new URLSearchParams(
    params ? Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])) : {}
  ).toString();

  return useQuery({
    queryKey: ['tickers', queryStr],
    queryFn: () =>
      apiFetch<{ items: Ticker[]; total: number }>(
        `/tickers${queryStr ? `?${queryStr}` : ''}`
      ),
  });
}

export function useTickerDetail(symbol: string) {
  return useQuery({
    queryKey: ['ticker', symbol],
    queryFn: () => apiFetch<Ticker>(`/tickers/${symbol}`),
  });
}

export function useDailyBars(symbol: string, params?: Record<string, string | number>) {
  const queryStr = new URLSearchParams(
    params ? Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])) : {}
  ).toString();

  return useQuery({
    queryKey: ['ohlcv', symbol, 'daily', queryStr],
    queryFn: () =>
      apiFetch<OHLCVBar[]>(`/ohlcv/${symbol}/daily${queryStr ? `?${queryStr}` : ''}`),
  });
}

export function useIntradayBars(
  symbol: string,
  params?: Record<string, string | number>
) {
  const queryStr = new URLSearchParams(
    params ? Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])) : {}
  ).toString();

  return useQuery({
    queryKey: ['ohlcv', symbol, 'intraday', queryStr],
    queryFn: () =>
      apiFetch<OHLCVBar[]>(`/ohlcv/${symbol}/intraday${queryStr ? `?${queryStr}` : ''}`),
  });
}

export function useLatestBar(symbol: string, timeframe: string) {
  return useQuery({
    queryKey: ['ohlcv', symbol, 'latest', timeframe],
    queryFn: () => apiFetch<OHLCVBar>(`/ohlcv/${symbol}/latest?timeframe=${timeframe}`),
  });
}

export interface Alert {
  id: number;
  user_id: string;
  ticker_id: number | null;
  scan_id: number | null;
  condition: Record<string, unknown>;
  status: string;
  notified_at: string | null;
  created_at: string;
}

export interface AlertCreate {
  ticker_id?: number;
  condition: Record<string, unknown>;
}

export function useAlerts() {
  return useQuery({
    queryKey: ['alerts'],
    queryFn: () => apiFetch<Alert[]>('/alerts'),
  });
}

export function useCreateAlert() {
  return useMutation({
    mutationFn: (body: AlertCreate) =>
      apiFetch<Alert>('/alerts', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });
}

export function useDeleteAlert() {
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<void>(`/alerts/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });
}

export interface FundamentalsRow {
  id: number;
  ticker_id: number;
  period: string;
  revenue: string | null;
  eps: string | null;
  pe_ratio: string | null;
  market_cap: number | null;
  reported_at: string | null;
}

export function useFundamentals(symbol: string) {
  return useQuery({
    queryKey: ['fundamentals', symbol],
    queryFn: () => apiFetch<FundamentalsRow[]>(`/fundamentals/${symbol}`),
    enabled: !!symbol,
    staleTime: 6 * 60 * 60 * 1000,
  });
}
