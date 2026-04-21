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
    enabled: !!params,
    refetchInterval: 30_000,
    staleTime: 0,
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

export interface TaskEnqueued {
  task_id: string;
  task_name: string;
}

export interface TaskStatus {
  task_id: string;
  status: string;
  result: unknown;
}

export type AdminTask =
  | 'ingest-daily-ohlcv'
  | 'refresh-tickers'
  | 'run-active-scans'
  | 'poll-intraday-bars'
  | 'ingest-fundamentals';

export function useTriggerTask(task: AdminTask, options?: UseMutationOptions<TaskEnqueued, Error, void>) {
  return useMutation<TaskEnqueued, Error, void>({
    mutationFn: () => apiFetch<TaskEnqueued>(`/admin/tasks/${task}`, { method: 'POST' }),
    ...options,
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (newPassword: string) =>
      apiFetch<void>('/users/me', {
        method: 'PATCH',
        body: JSON.stringify({ password: newPassword }),
      }),
  });
}

export interface CurrentUser {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

export function useCurrentUser() {
  return useQuery({
    queryKey: ['currentUser'],
    queryFn: () => apiFetch<CurrentUser>('/users/me'),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export interface HotlistData {
  suggested: string[];
  manual: string[];
  ws_connected: boolean;
  slots_used: number;
}

export function useHotlist() {
  return useQuery({
    queryKey: ['hotlist'],
    queryFn: () => apiFetch<HotlistData>('/hotlist'),
    refetchInterval: 30_000,
  });
}

export function usePinSymbol() {
  return useMutation({
    mutationFn: (symbol: string) =>
      apiFetch<{ symbol: string }>(`/hotlist/${symbol}`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hotlist'] }),
  });
}

export function useUnpinSymbol() {
  return useMutation({
    mutationFn: (symbol: string) =>
      apiFetch<{ symbol: string }>(`/hotlist/${symbol}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hotlist'] }),
  });
}

export interface JobConfig {
  id: number;
  job_name: string;
  enabled: boolean;
  universe_filter: string;
  cron_schedule: string | null;
  extra_config: Record<string, unknown>;
  updated_at: string;
}

export interface JobConfigUpdate {
  enabled?: boolean;
  universe_filter?: string;
  cron_schedule?: string;
  extra_config?: Record<string, unknown>;
}

export function useJobConfigs() {
  return useQuery({
    queryKey: ['admin', 'job-configs'],
    queryFn: () => apiFetch<JobConfig[]>('/admin/job-configs'),
    staleTime: 30_000,
  });
}

export function useUpdateJobConfig() {
  return useMutation({
    mutationFn: ({ jobName, update }: { jobName: string; update: JobConfigUpdate }) =>
      apiFetch<JobConfig>(`/admin/job-configs/${jobName}`, {
        method: 'PUT',
        body: JSON.stringify(update),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'job-configs'] }),
  });
}

export function useTaskStatus(taskId: string | null) {
  return useQuery({
    queryKey: ['admin', 'task', taskId],
    queryFn: () => apiFetch<TaskStatus>(`/admin/tasks/${taskId}`),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ['SUCCESS', 'FAILURE', 'REVOKED'].includes(status) ? false : 2000;
    },
  });
}

export interface ActiveTask {
  task_id: string;
  task_name: string;
  time_start: number | null;
}

export function useActiveTasks() {
  return useQuery({
    queryKey: ['admin', 'active-tasks'],
    queryFn: () => apiFetch<ActiveTask[]>('/admin/tasks/active'),
    refetchInterval: 5000,
  });
}

export function useRevokeTask() {
  return useMutation({
    mutationFn: (taskId: string) =>
      apiFetch<{ revoked: string }>(`/admin/tasks/${taskId}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'active-tasks'] }),
  });
}

export function useTaskLogs(taskId: string | null, enabled = true) {
  return useQuery({
    queryKey: ['admin', 'task-logs', taskId],
    queryFn: () => apiFetch<{ task_id: string; logs: string[] }>(`/admin/tasks/${taskId}/logs`),
    enabled: !!taskId && enabled,
    refetchInterval: enabled ? 2000 : false,
  });
}
