import { useEffect, useRef } from 'react';

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';

export interface LiveBar {
  type: 'bar';
  symbol: string;
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number | null;
  trade_count: number;
}

export interface AlertNotification {
  type: 'alert';
  alert_id: number;
  symbol: string;
  triggered_at: string;
  condition: Record<string, unknown>;
  bar: LiveBar;
}

interface UseWebSocketOptions {
  symbol: string;
  onBar?: (bar: LiveBar) => void;
  onAlert?: (alert: AlertNotification) => void;
  enabled?: boolean;
}

export function useWebSocket({ symbol, onBar, onAlert, enabled = true }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(1000);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled || !symbol) return;

    const connect = () => {
      if (!mountedRef.current) return;

      const token = localStorage.getItem('access_token');
      if (!token) return;

      const url = `${WS_BASE}/ws/bars/${symbol}?token=${token}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectDelayRef.current = 1000;
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'bar') {
            onBar?.(msg as LiveBar);
          } else if (msg.type === 'alert') {
            onAlert?.(msg as AlertNotification);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = (event) => {
        wsRef.current = null;
        if (!mountedRef.current || event.code === 1000) return;
        const delay = reconnectDelayRef.current;
        reconnectDelayRef.current = Math.min(delay * 2, 30000);
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close(1000);
      wsRef.current = null;
    };
  }, [symbol, enabled]);
}
