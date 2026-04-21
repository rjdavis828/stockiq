import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useTickers, useDailyBars, Ticker } from '../api/hooks';
import { useStore } from '../store';
import { Sparkline } from '../components/Sparkline';
import { useDashboardSummary, IndexSummary } from '../hooks/useDashboardSummary';

const fmtCap = (raw: string) => {
  const n = Number(raw);
  if (!n || Number.isNaN(n)) return '—';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  return `$${(n / 1e6).toFixed(0)}M`;
};

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true });
}

function WatchlistSparkline({ symbol }: { symbol: string }) {
  const { data } = useDailyBars(symbol, { limit: 30 });
  const prices = data?.map((b) => b.close) ?? [];
  const positive = prices.length >= 2 ? prices[prices.length - 1] >= prices[0] : true;
  return <Sparkline data={prices} color={positive ? 'var(--green)' : 'var(--red)'} />;
}

// Skeleton card for loading state
function IndexSkeleton() {
  return (
    <div className="card" style={{ padding: '14px 16px' }}>
      <style>{`
        @keyframes skeletonPulse {
          0%, 100% { background-color: var(--surface2); }
          50%       { background-color: var(--border); }
        }
        .skeleton-line { border-radius: 3px; animation: skeletonPulse 1.4s ease-in-out infinite; }
      `}</style>
      <div className="skeleton-line" style={{ height: 11, width: '60%', marginBottom: 10 }} />
      <div className="skeleton-line" style={{ height: 16, width: '80%', marginBottom: 7 }} />
      <div className="skeleton-line" style={{ height: 12, width: '40%' }} />
    </div>
  );
}

// Index card with flash-on-change
function IndexCard({ idx }: { idx: IndexSummary }) {
  const prevValueRef = useRef<number | null>(null);
  const [flashColor, setFlashColor] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (prevValueRef.current !== null && prevValueRef.current !== idx.value) {
      const color = idx.value > prevValueRef.current ? 'var(--green)' : 'var(--red)';
      setFlashColor(color);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setFlashColor(null), 600);
    }
    prevValueRef.current = idx.value;
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [idx.value]);

  return (
    <div className="card" style={{ padding: '14px 16px' }}>
      <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 6, letterSpacing: '0.05em' }}>{idx.name}</div>
      <div
        className="mono"
        style={{
          fontSize: 16,
          fontWeight: 600,
          color: flashColor ?? 'var(--text)',
          marginBottom: 3,
          transition: 'color 0.6s ease',
        }}
      >
        {idx.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
      </div>
      <div className="mono" style={{ fontSize: 12, color: idx.change >= 0 ? 'var(--green)' : 'var(--red)' }}>
        {idx.change >= 0 ? '+' : ''}{idx.change.toFixed(2)}%
      </div>
    </div>
  );
}

// Status bar live indicator
function LiveIndicator({ loading, error }: { loading: boolean; error: Error | null }) {
  const [showLive, setShowLive] = useState(false);
  const prevLoadingRef = useRef(loading);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (prevLoadingRef.current && !loading && !error) {
      setShowLive(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setShowLive(false), 2000);
    }
    prevLoadingRef.current = loading;
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [loading, error]);

  if (error) return <span style={{ color: 'var(--red)', fontSize: 12 }}>⚠ Stale</span>;
  if (loading) return <span style={{ fontSize: 12, color: 'var(--text2)' }}>↻ refreshing…</span>;
  return (
    <span
      style={{
        fontSize: 12,
        color: showLive ? 'var(--green)' : 'var(--text2)',
        transition: 'color 2s ease',
      }}
    >
      ✓ Live
    </span>
  );
}

const STATUS_CONFIG = {
  open:   { dot: 'var(--green)',  label: 'Market Open'  },
  closed: { dot: 'var(--text2)', label: 'Market Closed' },
  pre:    { dot: '#f59e0b',       label: 'Pre-Market'   },
  post:   { dot: '#f59e0b',       label: 'After Hours'  },
};

export default function Dashboard() {
  const { data: tickerData, isLoading } = useTickers({ limit: 50 });
  const { watchlist, addWatchlist, removeWatchlist } = useStore();
  const watchSet = new Set(watchlist.map((w) => w.symbol));
  const { data: summary, loading: summaryLoading, error: summaryError } = useDashboardSummary();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <Loader2 className="animate-spin" color="var(--text2)" />
      </div>
    );
  }

  const items = tickerData?.items ?? [];
  const watchTickers = items.filter((t) => watchSet.has(t.symbol));
  const byCapDesc = [...items].sort((a, b) => Number(b.market_cap) - Number(a.market_cap));
  const topCap = byCapDesc.slice(0, 4);
  const smallCap = [...items]
    .filter((t) => Number(t.market_cap) > 0)
    .sort((a, b) => Number(a.market_cap) - Number(b.market_cap))
    .slice(0, 4);

  const statusCfg = STATUS_CONFIG[summary?.market_status ?? 'closed'];
  const totalStocks = summary?.total_stocks ?? items.length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '28px 32px', minHeight: '100%' }}>

      {/* Status bar */}
      <div style={{ height: 28, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 2px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: statusCfg.dot, display: 'inline-block', flexShrink: 0 }} />
          <span style={{ fontSize: 13, color: 'var(--text2)', fontWeight: 500 }}>{statusCfg.label}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {summary?.last_updated && (
            <span style={{ fontSize: 12, color: 'var(--text2)' }}>
              Last updated&nbsp;&nbsp;{fmtTime(summary.last_updated)}
            </span>
          )}
          <LiveIndicator loading={summaryLoading} error={summaryError} />
        </div>
      </div>

      {/* Market indices cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
        {summaryLoading && !summary
          ? Array.from({ length: 5 }).map((_, i) => <IndexSkeleton key={i} />)
          : (summary?.indices ?? []).map((idx) => <IndexCard key={idx.name} idx={idx} />)
        }
      </div>

      {/* Watchlist + Movers */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 20, alignItems: 'start' }}>

        {/* Watchlist */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>Watchlist</span>
            <span style={{ fontSize: 12, color: 'var(--text2)' }}>{watchlist.length} stocks</span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Symbol', 'Mkt Cap', 'Sector', '30D', ''].map((h, i) => (
                  <th key={i} style={{ padding: '10px 20px', textAlign: i === 0 ? 'left' : i === 4 ? 'center' : 'right', fontSize: 11, fontWeight: 500, color: 'var(--text2)', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {watchTickers.map((t) => (
                <tr key={t.symbol} className="table-row" style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}>
                  <td style={{ padding: '12px 20px' }}>
                    <Link to={`/chart/${t.symbol}`} style={{ textDecoration: 'none' }}>
                      <div className="mono" style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>{t.symbol}</div>
                      <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 1, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</div>
                    </Link>
                  </td>
                  <td className="mono" style={{ padding: '12px 20px', textAlign: 'right', fontSize: 12, color: 'var(--text2)' }}>{fmtCap(t.market_cap)}</td>
                  <td style={{ padding: '12px 20px', textAlign: 'right' }}>
                    {t.sector
                      ? <span style={{ fontSize: 11, padding: '2px 6px', borderRadius: 3, background: 'var(--surface2)', color: 'var(--text2)', whiteSpace: 'nowrap' }}>{t.sector}</span>
                      : <span style={{ fontSize: 12, color: 'var(--text2)' }}>—</span>
                    }
                  </td>
                  <td style={{ padding: '12px 20px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <WatchlistSparkline symbol={t.symbol} />
                    </div>
                  </td>
                  <td style={{ padding: '12px 20px', textAlign: 'center' }}>
                    <button
                      onClick={() => removeWatchlist(t.symbol)}
                      className="remove-btn"
                      style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text2)', fontSize: 11, padding: '3px 8px', cursor: 'pointer', transition: 'all 0.12s' }}
                    >✕</button>
                  </td>
                </tr>
              ))}
              {watchTickers.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: '24px 20px', textAlign: 'center', fontSize: 13, color: 'var(--text2)' }}>
                    No stocks in watchlist. Add from below.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {items.filter((t) => !watchSet.has(t.symbol)).map((t) => (
              <button
                key={t.symbol}
                onClick={() => addWatchlist({ symbol: t.symbol, name: t.name })}
                className="chip"
                style={{ fontSize: 11, padding: '4px 9px', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text2)', cursor: 'pointer', transition: 'all 0.12s' }}
              >
                + {t.symbol}
              </button>
            ))}
          </div>
        </div>

        {/* Sidebar movers */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <MoverCard title="Largest Cap" items={topCap} />
          <MoverCard title="Smallest Cap" items={smallCap} />
        </div>
      </div>

      {/* All Stocks */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>All Stocks</span>
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>{totalStocks} companies</span>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Symbol', 'Name', 'Mkt Cap', 'Exchange', 'Sector', 'Industry'].map((h, i) => (
                <th key={i} style={{ padding: '10px 16px', textAlign: i <= 1 ? 'left' : 'right', fontSize: 11, fontWeight: 500, color: 'var(--text2)', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id} className="table-row" style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '11px 16px' }}>
                  <Link to={`/chart/${t.symbol}`} className="mono" style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)', textDecoration: 'none' }}>{t.symbol}</Link>
                </td>
                <td style={{ padding: '11px 16px', fontSize: 13, color: 'var(--text2)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</td>
                <td className="mono" style={{ padding: '11px 16px', textAlign: 'right', fontSize: 12, color: 'var(--text2)' }}>{fmtCap(t.market_cap)}</td>
                <td style={{ padding: '11px 16px', textAlign: 'right', fontSize: 12, color: 'var(--text2)' }}>{t.exchange || '—'}</td>
                <td style={{ padding: '11px 16px', textAlign: 'right' }}>
                  {t.sector
                    ? <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, background: 'var(--surface2)', color: 'var(--text2)', whiteSpace: 'nowrap' }}>{t.sector}</span>
                    : <span style={{ fontSize: 12, color: 'var(--text2)' }}>—</span>
                  }
                </td>
                <td style={{ padding: '11px 16px', textAlign: 'right', fontSize: 12, color: 'var(--text2)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.industry || '—'}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={6} style={{ padding: 32, textAlign: 'center', color: 'var(--text2)', fontSize: 13 }}>No tickers.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MoverCard({ title, items }: { title: string; items: Ticker[] }) {
  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontSize: 13, fontWeight: 600 }}>{title}</div>
      {items.map((t, i) => (
        <Link key={t.symbol} to={`/chart/${t.symbol}`} style={{ textDecoration: 'none' }}>
          <div
            className="mover-row"
            style={{ padding: '10px 16px', borderBottom: i < items.length - 1 ? '1px solid var(--border)' : 'none', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', transition: 'background 0.12s' }}
          >
            <div>
              <div className="mono" style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)' }}>{t.symbol}</div>
              <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 1 }}>{t.name.split(' ').slice(0, 2).join(' ')}</div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: 'var(--text2)' }}>{fmtCap(t.market_cap)}</div>
          </div>
        </Link>
      ))}
      {items.length === 0 && (
        <div style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text2)' }}>No data.</div>
      )}
    </div>
  );
}
