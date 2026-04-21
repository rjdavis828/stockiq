import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useTickers, useDailyBars, Ticker } from '../api/hooks';
import { useStore } from '../store';
import { Sparkline } from '../components/Sparkline';

const INDICES = [
  { name: 'S&P 500',   value: 5248.30,   change:  0.42 },
  { name: 'Nasdaq',    value: 16429.55,  change:  0.81 },
  { name: 'Dow Jones', value: 39215.80,  change:  0.12 },
  { name: 'VIX',       value: 18.42,     change: -3.21 },
  { name: '10Y Yield', value: 4.32,      change:  0.05, suffix: '%' },
];

const fmtCap = (raw: string) => {
  const n = Number(raw);
  if (!n || Number.isNaN(n)) return '—';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  return `$${(n / 1e6).toFixed(0)}M`;
};

function WatchlistSparkline({ symbol }: { symbol: string }) {
  const { data } = useDailyBars(symbol, { limit: 30 });
  const prices = data?.map((b) => b.close) ?? [];
  const positive = prices.length >= 2 ? prices[prices.length - 1] >= prices[0] : true;
  return <Sparkline data={prices} color={positive ? 'var(--green)' : 'var(--red)'} />;
}

export default function Dashboard() {
  const { data, isLoading } = useTickers({ limit: 50 });
  const { watchlist, addWatchlist, removeWatchlist } = useStore();
  const watchSet = new Set(watchlist.map((w) => w.symbol));

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <Loader2 className="animate-spin" color="var(--text2)" />
      </div>
    );
  }

  const items = data?.items ?? [];
  const watchTickers = items.filter((t) => watchSet.has(t.symbol));
  const byCapDesc = [...items].sort((a, b) => Number(b.market_cap) - Number(a.market_cap));
  const topCap = byCapDesc.slice(0, 4);
  const smallCap = [...items]
    .filter((t) => Number(t.market_cap) > 0)
    .sort((a, b) => Number(a.market_cap) - Number(b.market_cap))
    .slice(0, 4);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '28px 32px', minHeight: '100%' }}>

      {/* Market indices cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
        {INDICES.map((idx) => (
          <div key={idx.name} className="card" style={{ padding: '14px 16px' }}>
            <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 6, letterSpacing: '0.05em' }}>{idx.name}</div>
            <div className="mono" style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 3 }}>
              {idx.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}{idx.suffix || ''}
            </div>
            <div className="mono" style={{ fontSize: 12, color: idx.change >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {idx.change >= 0 ? '+' : ''}{idx.change.toFixed(2)}%
            </div>
          </div>
        ))}
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
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>{items.length} companies</span>
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
