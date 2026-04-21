import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useTickers, Ticker } from '../api/hooks';

type SortKey = 'symbol' | 'name' | 'exchange' | 'sector' | 'industry' | 'market_cap';

// Note: maxPE and minChange/maxChange are UI-only placeholders until the API exposes
// per-ticker price change and P/E ratio fields.

const inputStyle: React.CSSProperties = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text)',
  fontSize: 13,
  padding: '8px 10px',
  width: '100%',
  fontFamily: 'inherit',
  boxSizing: 'border-box',
};

const fmtCap = (raw: string) => {
  const n = Number(raw);
  if (!n || Number.isNaN(n)) return '—';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
};

export default function Scanner() {
  const { data, isLoading } = useTickers({ limit: 500 });
  const rows: Ticker[] = data?.items ?? [];

  const sectors = useMemo(
    () => ['All', ...Array.from(new Set(rows.map((r) => r.sector).filter(Boolean))).sort()],
    [rows]
  );

  const [sector, setSector] = useState('All');
  const [maxPE, setMaxPE] = useState('');
  const [minChange, setMinChange] = useState('');
  const [maxChange, setMaxChange] = useState('');
  const [minCap, setMinCap] = useState('');
  const [sortBy, setSortBy] = useState<SortKey>('market_cap');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const filtered = useMemo(() => {
    const min = minCap ? parseFloat(minCap) * 1e9 : null;
    return rows
      .filter((r) => {
        if (sector !== 'All' && r.sector !== sector) return false;
        if (min != null && Number(r.market_cap) < min) return false;
        return true;
      })
      .sort((a, b) => {
        const dir = sortDir === 'asc' ? 1 : -1;
        const av = sortBy === 'market_cap' ? Number(a.market_cap) || 0 : (a[sortBy] || '') as string | number;
        const bv = sortBy === 'market_cap' ? Number(b.market_cap) || 0 : (b[sortBy] || '') as string | number;
        if (av === bv) return 0;
        return av > bv ? dir : -dir;
      });
  }, [rows, sector, minCap, sortBy, sortDir]);

  const handleSort = (col: SortKey) => {
    if (sortBy === col) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortBy(col);
      setSortDir('desc');
    }
  };

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortBy !== col) return <span style={{ color: 'var(--border)', marginLeft: 3 }}>↕</span>;
    return (
      <span style={{ color: 'var(--accent)', marginLeft: 3 }}>{sortDir === 'asc' ? '↑' : '↓'}</span>
    );
  };

  const reset = () => {
    setSector('All');
    setMaxPE('');
    setMinChange('');
    setMaxChange('');
    setMinCap('');
  };

  const activeChips = [
    sector !== 'All' && { label: sector, clear: () => setSector('All') },
    maxPE && { label: `P/E ≤ ${maxPE}`, clear: () => setMaxPE('') },
    minChange && { label: `Change ≥ ${minChange}%`, clear: () => setMinChange('') },
    maxChange && { label: `Change ≤ ${maxChange}%`, clear: () => setMaxChange('') },
    minCap && { label: `Cap ≥ $${minCap}B`, clear: () => setMinCap('') },
  ].filter(Boolean) as { label: string; clear: () => void }[];

  const colHdr = (label: string, col: SortKey, align: 'left' | 'right' = 'right') => (
    <th
      onClick={() => handleSort(col)}
      style={{
        padding: '10px 16px',
        textAlign: align,
        fontSize: 11,
        fontWeight: 500,
        color: sortBy === col ? 'var(--accent)' : 'var(--text2)',
        letterSpacing: '0.05em',
        cursor: 'pointer',
        userSelect: 'none',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
      <SortIcon col={col} />
    </th>
  );

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Screener</h2>
          <div style={{ fontSize: 13, color: 'var(--text2)', marginTop: 4 }}>
            {isLoading ? 'Loading…' : `${filtered.length} results`}
          </div>
        </div>
        <button
          onClick={reset}
          style={{
            fontSize: 12,
            padding: '7px 14px',
            borderRadius: 6,
            border: '1px solid var(--border)',
            background: 'none',
            color: 'var(--text2)',
            cursor: 'pointer',
          }}
        >
          Reset Filters
        </button>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--text2)',
            letterSpacing: '0.08em',
            marginBottom: 14,
          }}
        >
          FILTERS
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr 1fr', gap: 16, alignItems: 'end' }}>
          <Field label="SECTOR">
            <select value={sector} onChange={(e) => setSector(e.target.value)} style={{ ...inputStyle, cursor: 'pointer' }}>
              {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="MAX P/E">
            <input type="number" placeholder="e.g. 40" value={maxPE} onChange={(e) => setMaxPE(e.target.value)} style={inputStyle} />
          </Field>
          <Field label="MIN CHANGE %">
            <input type="number" placeholder="e.g. -2" value={minChange} onChange={(e) => setMinChange(e.target.value)} style={inputStyle} />
          </Field>
          <Field label="MAX CHANGE %">
            <input type="number" placeholder="e.g. 5" value={maxChange} onChange={(e) => setMaxChange(e.target.value)} style={inputStyle} />
          </Field>
          <Field label="MIN MARKET CAP ($B)">
            <input type="number" placeholder="e.g. 100" value={minCap} onChange={(e) => setMinCap(e.target.value)} style={inputStyle} />
          </Field>
        </div>

        {activeChips.length > 0 && (
          <div style={{ marginTop: 12, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {activeChips.map((f, i) => (
              <span key={i} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 20, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', gap: 5 }}>
                {f.label}
                <span onClick={f.clear} style={{ cursor: 'pointer', opacity: 0.7, fontSize: 10 }}>✕</span>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="card" style={{ overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {colHdr('Symbol', 'symbol', 'left')}
              {colHdr('Name', 'name', 'left')}
              {colHdr('Exchange', 'exchange')}
              {colHdr('Sector', 'sector')}
              {colHdr('Industry', 'industry')}
              {colHdr('Mkt Cap', 'market_cap')}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} style={{ padding: 32, textAlign: 'center' }}>
                  <Loader2 className="animate-spin" color="var(--text2)" />
                </td>
              </tr>
            )}
            {!isLoading && filtered.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  style={{ padding: 32, textAlign: 'center', color: 'var(--text2)', fontSize: 14 }}
                >
                  No tickers match your filters.
                </td>
              </tr>
            )}
            {filtered.map((t) => (
              <tr
                key={t.id}
                className="table-row"
                style={{ borderBottom: '1px solid var(--border)' }}
              >
                <td style={{ padding: '12px 16px' }}>
                  <Link
                    to={`/chart/${t.symbol}`}
                    className="mono"
                    style={{
                      fontWeight: 700,
                      fontSize: 13,
                      color: 'var(--text)',
                      textDecoration: 'none',
                    }}
                  >
                    {t.symbol}
                  </Link>
                </td>
                <td
                  style={{
                    padding: '12px 16px',
                    fontSize: 13,
                    color: 'var(--text2)',
                    maxWidth: 220,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {t.name}
                </td>
                <td
                  style={{
                    padding: '12px 16px',
                    textAlign: 'right',
                    fontSize: 12,
                    color: 'var(--text2)',
                  }}
                >
                  {t.exchange || '—'}
                </td>
                <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                  {t.sector ? (
                    <span
                      style={{
                        fontSize: 11,
                        padding: '3px 8px',
                        borderRadius: 4,
                        background: 'var(--surface2)',
                        color: 'var(--text2)',
                      }}
                    >
                      {t.sector}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text2)', fontSize: 12 }}>—</span>
                  )}
                </td>
                <td
                  style={{
                    padding: '12px 16px',
                    textAlign: 'right',
                    fontSize: 12,
                    color: 'var(--text2)',
                    maxWidth: 180,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {t.industry || '—'}
                </td>
                <td
                  className="mono"
                  style={{
                    padding: '12px 16px',
                    textAlign: 'right',
                    fontSize: 12,
                    color: 'var(--text2)',
                  }}
                >
                  {fmtCap(t.market_cap)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label
        style={{
          fontSize: 11,
          color: 'var(--text2)',
          display: 'block',
          marginBottom: 6,
          letterSpacing: '0.04em',
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}
