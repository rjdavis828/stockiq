import { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../api/client';

export interface IndexSummary {
  name: string;
  value: number;
  change: number;
}

export interface DashboardSummary {
  indices: IndexSummary[];
  market_status: 'open' | 'closed' | 'pre' | 'post';
  last_updated: string;
  watchlist_count: number;
  total_stocks: number;
}

export interface UseDashboardSummaryResult {
  data: DashboardSummary | null;
  loading: boolean;
  error: Error | null;
}

export function useDashboardSummary(): UseDashboardSummaryResult {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetch() {
      setLoading(true);
      try {
        const result = await apiFetch<DashboardSummary>('/dashboard/summary');
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetch();
    intervalRef.current = setInterval(fetch, 30_000);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return { data, loading, error };
}
