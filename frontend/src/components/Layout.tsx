import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useStore } from '../store';
import { useTickers } from '../api/hooks';
import { Moon, Sun, LayoutGrid, Filter, Bell, X } from 'lucide-react';

const INDICES = [
  { name: 'S&P 500',   value: 5248.30,   change:  0.42 },
  { name: 'Nasdaq',    value: 16429.55,  change:  0.81 },
  { name: 'Dow Jones', value: 39215.80,  change:  0.12 },
  { name: 'VIX',       value: 18.42,     change: -3.21 },
  { name: '10Y Yield', value: 4.32,      change:  0.05, suffix: '%' },
];

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutGrid, end: true },
  { to: '/scanner', label: 'Screener', icon: Filter, end: false },
  { to: '/alerts', label: 'Alerts', icon: Bell, end: false },
];

export default function Layout() {
  const { watchlist, darkMode, toggleDarkMode, pendingAlerts, clearPendingAlerts } = useStore();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const { data: searchData } = useTickers({ limit: 500 });
  const q = search.trim().toLowerCase();
  const searchResults =
    q.length > 0
      ? (searchData?.items ?? [])
          .filter(
            (t) =>
              t.symbol.toLowerCase().includes(q) || t.name.toLowerCase().includes(q)
          )
          .slice(0, 6)
      : [];

  const today = new Date().toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  const go = (symbol: string) => {
    setSearch('');
    setSearchOpen(false);
    navigate(`/chart/${symbol}`);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <aside
        style={{
          width: 220,
          flexShrink: 0,
          background: 'var(--surface)',
          borderRight: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid var(--border)' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontWeight: 800,
              fontSize: 15,
              letterSpacing: '-0.3px',
            }}
          >
            <span
              style={{
                width: 24,
                height: 24,
                borderRadius: 5,
                background: 'var(--accent)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              S
            </span>
            StockIQ
          </div>
          <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 3 }}>
            Research Platform
          </div>
        </div>

        <nav style={{ padding: '12px 10px', flex: 1, overflowY: 'auto' }}>
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className="nav-btn"
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '9px 10px',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--accent)' : 'var(--text2)',
                background: isActive ? 'var(--accent-soft)' : 'transparent',
                textDecoration: 'none',
                marginBottom: 2,
              })}
            >
              <Icon size={14} />
              {label}
            </NavLink>
          ))}

          {watchlist.length > 0 && (
            <>
              <div
                style={{
                  marginTop: 16,
                  marginBottom: 6,
                  padding: '0 10px',
                  fontSize: 10,
                  color: 'var(--text2)',
                  letterSpacing: '0.08em',
                  fontWeight: 600,
                }}
              >
                WATCHLIST
              </div>
              {watchlist.map((w) => (
                <NavLink
                  key={w.symbol}
                  to={`/chart/${w.symbol}`}
                  className="nav-btn"
                  style={({ isActive }) => ({
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '7px 10px',
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 500,
                    color: isActive ? 'var(--accent)' : 'var(--text)',
                    background: isActive ? 'var(--accent-soft)' : 'transparent',
                    textDecoration: 'none',
                    marginBottom: 1,
                  })}
                >
                  <span className="mono" style={{ fontWeight: 600, fontSize: 11 }}>
                    {w.symbol}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      color: 'var(--text2)',
                      maxWidth: 110,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {w.name}
                  </span>
                </NavLink>
              ))}
            </>
          )}
        </nav>

        <div
          style={{
            padding: 12,
            borderTop: '1px solid var(--border)',
            fontSize: 10,
            color: 'var(--text2)',
            textAlign: 'center',
          }}
        >
          {today} · US Markets
        </div>
      </aside>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <header
          style={{
            height: 52,
            borderBottom: '1px solid var(--border)',
            background: 'var(--surface)',
            display: 'flex',
            alignItems: 'center',
            padding: '0 24px',
            gap: 16,
            flexShrink: 0,
          }}
        >
          <div style={{ position: 'relative', flex: '0 0 280px' }}>
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              onBlur={() => setTimeout(() => setSearchOpen(false), 150)}
              placeholder="Search tickers…"
              style={{
                width: '100%',
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                color: 'var(--text)',
                fontSize: 13,
                padding: '7px 10px 7px 30px',
                fontFamily: 'inherit',
                boxSizing: 'border-box',
              }}
            />
            <span
              style={{
                position: 'absolute',
                left: 9,
                top: '50%',
                transform: 'translateY(-50%)',
                fontSize: 13,
                color: 'var(--text2)',
                pointerEvents: 'none',
              }}
            >
              ⌕
            </span>
            {searchOpen && searchResults.length > 0 && (
              <div
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 4px)',
                  left: 0,
                  right: 0,
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                  zIndex: 100,
                  overflow: 'hidden',
                }}
              >
                {searchResults.map((s) => (
                  <div
                    key={s.symbol}
                    onMouseDown={() => go(s.symbol)}
                    className="table-row"
                    style={{
                      padding: '10px 14px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <span className="mono" style={{ fontWeight: 700, fontSize: 13 }}>
                        {s.symbol}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--text2)', marginLeft: 8 }}>
                        {s.name}
                      </span>
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--text2)' }}>{s.exchange}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ flex: 1, display: 'flex', gap: 20, overflow: 'hidden' }}>
            {INDICES.map((idx) => (
              <div key={idx.name} style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                <span style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500 }}>{idx.name}</span>
                <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>
                  {idx.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}{idx.suffix || ''}
                </span>
                <span className="mono" style={{ fontSize: 11, color: idx.change >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {idx.change >= 0 ? '+' : ''}{idx.change.toFixed(2)}%
                </span>
              </div>
            ))}
          </div>

          <button
            onClick={toggleDarkMode}
            aria-label="Toggle theme"
            style={{
              background: 'var(--surface2)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              padding: 7,
              color: 'var(--text2)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              flexShrink: 0,
            }}
          >
            {darkMode ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </header>

        <main style={{ flex: 1, overflowY: 'auto', position: 'relative' }}>
          <Outlet />
          {pendingAlerts.length > 0 && (
            <div
              style={{
                position: 'fixed',
                bottom: 24,
                right: 24,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                zIndex: 200,
              }}
            >
              {pendingAlerts.map((a, i) => (
                <div
                  key={i}
                  style={{
                    background: 'var(--surface)',
                    border: '1px solid var(--accent)',
                    borderRadius: 8,
                    padding: '12px 16px',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    minWidth: 240,
                    maxWidth: 320,
                  }}
                >
                  <Bell size={14} color="var(--accent)" style={{ flexShrink: 0, marginTop: 2 }} />
                  <div style={{ flex: 1, fontSize: 13 }}>
                    <div style={{ fontWeight: 700, marginBottom: 2 }}>{a.symbol} Alert Triggered</div>
                    <div style={{ fontSize: 11, color: 'var(--text2)' }}>{a.message}</div>
                  </div>
                  <button
                    onClick={clearPendingAlerts}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text2)', padding: 0 }}
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
