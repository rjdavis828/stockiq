import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useState, FormEvent } from 'react';
import { useStore } from '../store';
import { useTickers, useChangePassword, useCurrentUser } from '../api/hooks';
import { logout } from '../api/client';
import { Moon, Sun, LayoutGrid, Filter, Bell, X, Settings, LogOut, KeyRound, Zap } from 'lucide-react';

const INDICES = [
  { name: 'S&P 500',   value: 5248.30,   change:  0.42 },
  { name: 'Nasdaq',    value: 16429.55,  change:  0.81 },
  { name: 'Dow Jones', value: 39215.80,  change:  0.12 },
  { name: 'VIX',       value: 18.42,     change: -3.21 },
  { name: '10Y Yield', value: 4.32,      change:  0.05, suffix: '%' },
];

const BASE_NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutGrid, end: true },
  { to: '/scanner', label: 'Screener', icon: Filter, end: false },
  { to: '/alerts', label: 'Alerts', icon: Bell, end: false },
  { to: '/hotlist', label: 'Hot List', icon: Zap, end: false },
];

const ADMIN_NAV = { to: '/admin', label: 'Admin', icon: Settings, end: false };

export default function Layout() {
  const { watchlist, darkMode, toggleDarkMode, pendingAlerts, clearPendingAlerts } = useStore();
  const { data: currentUser } = useCurrentUser();
  const navItems = currentUser?.is_superuser ? [...BASE_NAV, ADMIN_NAV] : BASE_NAV;
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);
  const changePassword = useChangePassword();

  async function handleChangePw(e: FormEvent) {
    e.preventDefault();
    setPwError(null);
    if (newPw.length < 8) { setPwError('Password must be at least 8 characters'); return; }
    if (newPw !== confirmPw) { setPwError('Passwords do not match'); return; }
    try {
      await changePassword.mutateAsync(newPw);
      setPwSuccess(true);
      setNewPw('');
      setConfirmPw('');
      setTimeout(() => { setPwOpen(false); setPwSuccess(false); }, 1500);
    } catch {
      setPwError('Failed to update password');
    }
  }
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
          <button
            onClick={() => { setPwOpen(true); setPwError(null); setPwSuccess(false); }}
            aria-label="Change password"
            title="Change password"
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
            <KeyRound size={15} />
          </button>
          <button
            onClick={logout}
            aria-label="Sign out"
            title="Sign out"
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
            <LogOut size={15} />
          </button>

          {pwOpen && (
            <div
              style={{
                position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 500,
              }}
              onClick={(e) => { if (e.target === e.currentTarget) setPwOpen(false); }}
            >
              <form
                onSubmit={handleChangePw}
                style={{
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: 10, padding: 24, width: 320, display: 'flex',
                  flexDirection: 'column', gap: 14,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>Change Password</span>
                  <button type="button" onClick={() => setPwOpen(false)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text2)', padding: 0 }}>
                    <X size={14} />
                  </button>
                </div>
                <label style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 600 }}>
                  NEW PASSWORD
                  <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)}
                    required autoFocus style={pwInputStyle} />
                </label>
                <label style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 600 }}>
                  CONFIRM PASSWORD
                  <input type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)}
                    required style={pwInputStyle} />
                </label>
                {pwError && <div style={{ fontSize: 12, color: 'var(--red)' }}>{pwError}</div>}
                {pwSuccess && <div style={{ fontSize: 12, color: 'var(--green)' }}>Password updated!</div>}
                <button type="submit" disabled={changePassword.isPending}
                  style={{
                    padding: '9px 14px', borderRadius: 6, border: 'none',
                    background: 'var(--accent)', color: '#fff', fontWeight: 600,
                    fontSize: 13, cursor: changePassword.isPending ? 'not-allowed' : 'pointer',
                    opacity: changePassword.isPending ? 0.7 : 1,
                  }}>
                  {changePassword.isPending ? 'Saving…' : 'Update Password'}
                </button>
              </form>
            </div>
          )}
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

const pwInputStyle: React.CSSProperties = {
  marginTop: 6,
  width: '100%',
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text)',
  fontSize: 13,
  padding: '8px 10px',
  fontFamily: 'inherit',
  boxSizing: 'border-box',
};
