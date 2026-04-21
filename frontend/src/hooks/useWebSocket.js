import { useEffect, useRef } from 'react';
const WS_BASE = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';
export function useWebSocket({ symbol, onBar, onAlert, enabled = true }) {
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const reconnectDelayRef = useRef(1000);
    const mountedRef = useRef(true);
    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);
    useEffect(() => {
        if (!enabled || !symbol)
            return;
        const connect = () => {
            if (!mountedRef.current)
                return;
            const token = localStorage.getItem('access_token');
            if (!token)
                return;
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
                        onBar?.(msg);
                    }
                    else if (msg.type === 'alert') {
                        onAlert?.(msg);
                    }
                }
                catch {
                    // ignore malformed messages
                }
            };
            ws.onclose = (event) => {
                wsRef.current = null;
                if (!mountedRef.current || event.code === 1000)
                    return;
                const delay = reconnectDelayRef.current;
                reconnectDelayRef.current = Math.min(delay * 2, 30000);
                reconnectTimerRef.current = setTimeout(connect, delay);
            };
        };
        connect();
        return () => {
            mountedRef.current = false;
            if (reconnectTimerRef.current)
                clearTimeout(reconnectTimerRef.current);
            wsRef.current?.close(1000);
            wsRef.current = null;
        };
    }, [symbol, enabled]);
}
