import { useState } from 'react';
import { Loader2, Trash2, Plus, X } from 'lucide-react';
import { useAlerts, useCreateAlert, useDeleteAlert, useTickers } from '../api/hooks';

const INDICATORS = ['RSI', 'SMA', 'EMA', 'MACD', 'CCI', 'ATR', 'OBV', 'MFI'];
const OPERATORS = [
  { value: 'gt', label: '>' },
  { value: 'lt', label: '<' },
  { value: 'crosses_above', label: 'Crosses Above' },
  { value: 'crosses_below', label: 'Crosses Below' },
];

const statusColor: Record<string, string> = {
  active: 'var(--green)',
  triggered: 'var(--accent)',
  paused: 'var(--text2)',
};

function conditionSummary(cond: Record<string, unknown>): string {
  const ind = String(cond.indicator || '');
  const period = cond.period ? `(${cond.period})` : '';
  const op = OPERATORS.find((o) => o.value === cond.operator)?.label ?? String(cond.operator || '');
  const val = cond.value != null ? String(cond.value) : '';
  return `${ind}${period} ${op} ${val}`.trim();
}

interface FormState {
  ticker_id: string;
  indicator: string;
  period: string;
  operator: string;
  value: string;
}

const defaultForm: FormState = {
  ticker_id: '',
  indicator: 'RSI',
  period: '14',
  operator: 'lt',
  value: '30',
};

export default function Alerts() {
  const { data: alerts, isLoading } = useAlerts();
  const createAlert = useCreateAlert();
  const deleteAlert = useDeleteAlert();
  const { data: tickersData } = useTickers({ limit: 500 });
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(defaultForm);

  const field = (key: keyof FormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const condition: Record<string, unknown> = {
      indicator: form.indicator,
      period: Number(form.period) || undefined,
      operator: form.operator,
      value: Number(form.value),
    };
    await createAlert.mutateAsync({
      ticker_id: form.ticker_id ? Number(form.ticker_id) : undefined,
      condition,
    });
    setForm(defaultForm);
    setShowForm(false);
  };

  const inputStyle: React.CSSProperties = {
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 6,
    color: 'var(--text)',
    fontSize: 13,
    padding: '7px 10px',
    fontFamily: 'inherit',
    width: '100%',
    boxSizing: 'border-box',
  };

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Alerts</h2>
          <div style={{ fontSize: 13, color: 'var(--text2)', marginTop: 4 }}>
            Manage price and indicator alerts
          </div>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 16px',
            borderRadius: 6,
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            background: showForm ? 'var(--surface2)' : 'var(--accent)',
            color: showForm ? 'var(--text)' : '#fff',
            border: `1px solid ${showForm ? 'var(--border)' : 'var(--accent)'}`,
          }}
        >
          {showForm ? <X size={14} /> : <Plus size={14} />}
          {showForm ? 'Cancel' : 'New Alert'}
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ padding: '20px 24px' }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 5, letterSpacing: '0.05em' }}>
                  SYMBOL
                </div>
                <select style={inputStyle} value={form.ticker_id} onChange={field('ticker_id')} required>
                  <option value="">Select…</option>
                  {tickersData?.items.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.symbol}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 5, letterSpacing: '0.05em' }}>
                  INDICATOR
                </div>
                <select style={inputStyle} value={form.indicator} onChange={field('indicator')}>
                  {INDICATORS.map((i) => (
                    <option key={i} value={i}>{i}</option>
                  ))}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 5, letterSpacing: '0.05em' }}>
                  PERIOD
                </div>
                <input
                  type="number"
                  min={1}
                  style={inputStyle}
                  value={form.period}
                  onChange={field('period')}
                  placeholder="14"
                />
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 5, letterSpacing: '0.05em' }}>
                  OPERATOR
                </div>
                <select style={inputStyle} value={form.operator} onChange={field('operator')}>
                  {OPERATORS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 5, letterSpacing: '0.05em' }}>
                  VALUE
                </div>
                <input
                  type="number"
                  step="any"
                  style={inputStyle}
                  value={form.value}
                  onChange={field('value')}
                  placeholder="30"
                  required
                />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="submit"
                disabled={createAlert.isPending}
                style={{
                  padding: '8px 20px',
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: createAlert.isPending ? 'not-allowed' : 'pointer',
                  background: 'var(--accent)',
                  color: '#fff',
                  border: '1px solid var(--accent)',
                  opacity: createAlert.isPending ? 0.7 : 1,
                }}
              >
                {createAlert.isPending ? 'Creating…' : 'Create Alert'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="card" style={{ overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <Loader2 className="animate-spin" color="var(--text2)" />
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Symbol', 'Condition', 'Status', 'Last Triggered', ''].map((h, i) => (
                  <th
                    key={i}
                    style={{
                      padding: '10px 16px',
                      textAlign: i === 4 ? 'right' : 'left',
                      fontSize: 11,
                      fontWeight: 500,
                      color: 'var(--text2)',
                      letterSpacing: '0.05em',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!alerts || alerts.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text2)', fontSize: 14 }}>
                    No alerts yet.
                  </td>
                </tr>
              ) : (
                alerts.map((alert) => {
                  const ticker = tickersData?.items.find((t) => t.id === alert.ticker_id);
                  return (
                    <tr
                      key={alert.id}
                      className="table-row"
                      style={{ borderBottom: '1px solid var(--border)' }}
                    >
                      <td style={{ padding: '12px 16px' }}>
                        <span className="mono" style={{ fontWeight: 700, fontSize: 13 }}>
                          {ticker?.symbol ?? `#${alert.ticker_id}`}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text2)' }}>
                        {conditionSummary(alert.condition)}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            padding: '3px 8px',
                            borderRadius: 4,
                            background: 'var(--surface2)',
                            color: statusColor[alert.status] ?? 'var(--text2)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                          }}
                        >
                          {alert.status}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text2)' }}>
                        {alert.notified_at
                          ? new Date(alert.notified_at).toLocaleString()
                          : '—'}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <button
                          onClick={() => deleteAlert.mutate(alert.id)}
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
                          title="Delete alert"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
