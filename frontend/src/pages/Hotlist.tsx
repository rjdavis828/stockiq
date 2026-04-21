import { useState, FormEvent } from 'react';
import { Loader2, X, Plus } from 'lucide-react';
import { useHotlist } from '../api/hooks';
import { apiFetch, queryClient } from '../api/client';

const MAX_SLOTS = 50;

function SlotMeter({ used }: { used: number }) {
  const pct = (used / MAX_SLOTS) * 100;
  const color = pct >= 95 ? 'var(--red)' : pct >= 80 ? 'var(--amber, #f59e0b)' : 'var(--green)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 220 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text2)', fontWeight: 600 }}>
        <span>WS SLOTS</span>
        <span style={{ color }}>{used} / {MAX_SLOTS} used</span>
      </div>
      <div style={{ height: 6, borderRadius: 3, background: 'var(--surface2)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3, transition: 'width 0.3s' }} />
      </div>
    </div>
  );
}

function WsPill({ connected }: { connected: boolean }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '4px 10px',
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
        background: connected ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
        color: connected ? 'var(--green)' : 'var(--red)',
        letterSpacing: '0.04em',
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: connected ? 'var(--green)' : 'var(--red)',
          display: 'inline-block',
        }}
      />
      {connected ? 'Live' : 'Disconnected'}
    </span>
  );
}

const inputStyle: React.CSSProperties = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text)',
  fontSize: 13,
  padding: '7px 10px',
  fontFamily: 'inherit',
  width: 140,
  boxSizing: 'border-box',
};

export default function Hotlist() {
  const { data, isLoading } = useHotlist();
  const [pinInput, setPinInput] = useState('');
  const [pinError, setPinError] = useState<string | null>(null);
  const [pinPending, setPinPending] = useState(false);
  const [pinningSuggested, setPinningSuggested] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  async function pinSymbol(symbol: string): Promise<boolean> {
    try {
      await apiFetch(`/hotlist/${symbol}`, { method: 'POST' });
      queryClient.invalidateQueries({ queryKey: ['hotlist'] });
      return true;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409') || msg.toLowerCase().includes('conflict')) {
        setPinError('Symbol is already in the hotlist.');
      } else if (msg.includes('400')) {
        setPinError('Hotlist is at capacity (50 slots).');
      } else {
        setPinError('Failed to pin symbol.');
      }
      return false;
    }
  }

  async function handlePin(e: FormEvent) {
    e.preventDefault();
    const symbol = pinInput.trim().toUpperCase();
    if (!symbol) return;
    setPinError(null);
    setPinPending(true);
    const ok = await pinSymbol(symbol);
    if (ok) setPinInput('');
    setPinPending(false);
  }

  async function handlePinSuggested(symbol: string) {
    setPinError(null);
    setPinningSuggested(symbol);
    await pinSymbol(symbol);
    setPinningSuggested(null);
  }

  async function handleRemove(symbol: string) {
    setRemoveError(null);
    try {
      await apiFetch(`/hotlist/${symbol}`, { method: 'DELETE' });
      queryClient.invalidateQueries({ queryKey: ['hotlist'] });
    } catch {
      setRemoveError(`Failed to remove ${symbol}.`);
    }
  }

  const thStyle: React.CSSProperties = {
    padding: '10px 16px',
    textAlign: 'left',
    fontSize: 11,
    fontWeight: 500,
    color: 'var(--text2)',
    letterSpacing: '0.05em',
  };

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Hot List</h2>
          <div style={{ fontSize: 13, color: 'var(--text2)', marginTop: 4 }}>
            Symbols streamed live via Finnhub WebSocket
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          {data && <SlotMeter used={data.slots_used} />}
          {data && <WsPill connected={data.ws_connected} />}
        </div>
      </div>

      {isLoading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
          <Loader2 className="animate-spin" color="var(--text2)" />
        </div>
      )}

      {!isLoading && data && (
        <>
          {/* Suggested section */}
          <div className="card" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 700 }}>Suggested from Alerts</span>
              <span style={{ fontSize: 11, color: 'var(--text2)', background: 'var(--surface2)', padding: '2px 7px', borderRadius: 4, fontWeight: 600 }}>
                not streaming
              </span>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={thStyle}>SYMBOL</th>
                  <th style={thStyle}>SOURCE</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {data.suggested.length === 0 ? (
                  <tr>
                    <td colSpan={3} style={{ padding: 32, textAlign: 'center', fontSize: 13, color: 'var(--text2)' }}>
                      No alert symbols outside the hotlist.
                    </td>
                  </tr>
                ) : (
                  data.suggested.map((sym) => (
                    <tr key={sym} className="table-row" style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '12px 16px' }}>
                        <span className="mono" style={{ fontWeight: 700, fontSize: 13 }}>{sym}</span>
                        <span style={{ marginLeft: 8, fontSize: 12 }}>🔔</span>
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text2)' }}>
                        Active alert
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <button
                          onClick={() => handlePinSuggested(sym)}
                          disabled={pinningSuggested === sym}
                          title={`Pin ${sym} to hotlist`}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            padding: '4px 10px',
                            borderRadius: 5,
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: pinningSuggested === sym ? 'not-allowed' : 'pointer',
                            background: 'var(--accent)',
                            color: '#fff',
                            border: 'none',
                            opacity: pinningSuggested === sym ? 0.6 : 1,
                          }}
                        >
                          <Plus size={12} />
                          {pinningSuggested === sym ? 'Pinning…' : 'Pin'}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Manual section */}
          <div className="card" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700 }}>Manually Pinned</span>
                <span style={{ fontSize: 11, color: 'var(--text2)', background: 'var(--surface2)', padding: '2px 7px', borderRadius: 4, fontWeight: 600 }}>
                  manual
                </span>
              </div>
              <form onSubmit={handlePin} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      value={pinInput}
                      onChange={(e) => { setPinInput(e.target.value); setPinError(null); }}
                      placeholder="Ticker symbol…"
                      style={inputStyle}
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <button
                      type="submit"
                      disabled={pinPending || !pinInput.trim()}
                      style={{
                        padding: '7px 16px',
                        borderRadius: 6,
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: pinPending || !pinInput.trim() ? 'not-allowed' : 'pointer',
                        background: 'var(--accent)',
                        color: '#fff',
                        border: '1px solid var(--accent)',
                        opacity: pinPending || !pinInput.trim() ? 0.6 : 1,
                      }}
                    >
                      {pinPending ? 'Pinning…' : 'Pin'}
                    </button>
                  </div>
                  {pinError && (
                    <span style={{ fontSize: 11, color: 'var(--red)' }}>{pinError}</span>
                  )}
                </div>
              </form>
            </div>

            {removeError && (
              <div style={{ padding: '8px 16px', background: 'rgba(239,68,68,0.08)', fontSize: 12, color: 'var(--red)', borderBottom: '1px solid var(--border)' }}>
                {removeError}
              </div>
            )}

            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={thStyle}>SYMBOL</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}></th>
                </tr>
              </thead>
              <tbody>
                {data.manual.length === 0 ? (
                  <tr>
                    <td colSpan={2} style={{ padding: 32, textAlign: 'center', fontSize: 13, color: 'var(--text2)' }}>
                      No manually pinned symbols.
                    </td>
                  </tr>
                ) : (
                  data.manual.map((sym) => (
                    <tr key={sym} className="table-row" style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '12px 16px' }}>
                        <span className="mono" style={{ fontWeight: 700, fontSize: 13 }}>{sym}</span>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <button
                          onClick={() => handleRemove(sym)}
                          title={`Remove ${sym}`}
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            color: 'var(--text2)',
                            padding: 4,
                            borderRadius: 4,
                            display: 'inline-flex',
                            alignItems: 'center',
                          }}
                        >
                          <X size={14} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
