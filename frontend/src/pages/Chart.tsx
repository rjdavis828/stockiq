import { useParams, useNavigate } from 'react-router-dom';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { createChart, ColorType, IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import { useDailyBars, useFundamentals, useIntradayBars, useTickerDetail } from '../api/hooks';
import { useStore } from '../store';
import { useWebSocket } from '../hooks/useWebSocket';

const DAILY_TIMEFRAMES: Record<string, number> = {
  '1M': 21,
  '3M': 63,
  '6M': 126,
  '1Y': 252,
};

const INTRADAY_TIMEFRAMES = ['1m', '5m', '15m'] as const;
type IntradayTF = typeof INTRADAY_TIMEFRAMES[number];
type DailyTF = '1M' | '3M' | '6M' | '1Y';

const fmtCap = (raw?: string) => {
  const n = Number(raw);
  if (!n || Number.isNaN(n)) return '—';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
};

const fmtVol = (v?: number) => {
  if (!v) return '—';
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return v.toLocaleString();
};

export default function Chart() {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const { data: ticker, isLoading: tickerLoading } = useTickerDetail(symbol || '');
  const [timeframe, setTimeframe] = useState<DailyTF>('3M');
  const [intradayTF, setIntradayTF] = useState<IntradayTF | null>(null);
  const [chartType, setChartType] = useState<'line' | 'candle'>('candle');
  const { watchlist, addWatchlist, removeWatchlist, darkMode } = useStore();
  const { data: fundamentals } = useFundamentals(symbol || '');

  const isIntraday = intradayTF !== null;
  const { data: dailyBars, isLoading: dailyLoading } = useDailyBars(
    symbol || '',
    { limit: 300 },
  );
  const { data: intradayBars, isLoading: intradayLoading } = useIntradayBars(
    symbol || '',
    isIntraday ? { timeframe: intradayTF, limit: 390 } : undefined,
  );

  const bars = isIntraday ? intradayBars : dailyBars;
  const barsLoading = isIntraday ? intradayLoading : dailyLoading;

  const inWatch = !!ticker && watchlist.some((w) => w.symbol === ticker.symbol);

  const seriesRef = useRef<ISeriesApi<'Candlestick'> | ISeriesApi<'Line'> | null>(null);
  const chartTypeRef = useRef(chartType);
  chartTypeRef.current = chartType;

  useWebSocket({
    symbol: symbol || '',
    enabled: !!symbol && isIntraday,
    onBar: (msg: { ts: string; open: number; high: number; low: number; close: number }) => {
      const series = seriesRef.current;
      if (!series) return;
      const time = Math.floor(new Date(msg.ts).getTime() / 1000) as UTCTimestamp;
      if (chartTypeRef.current === 'candle') {
        (series as ISeriesApi<'Candlestick'>).update({
          time,
          open: msg.open,
          high: msg.high,
          low: msg.low,
          close: msg.close,
        });
      } else {
        (series as ISeriesApi<'Line'>).update({ time, value: msg.close });
      }
    },
  });

  const sliceData = useMemo(() => {
    if (!bars) return [];
    if (isIntraday) return [...bars].reverse();
    return bars.slice(0, DAILY_TIMEFRAMES[timeframe]).reverse();
  }, [bars, timeframe, isIntraday]);

  const latest = sliceData[sliceData.length - 1];
  const first = sliceData[0];
  const change = latest && first ? latest.close - first.close : 0;
  const changePct = latest && first && first.close ? (change / first.close) * 100 : 0;
  const positive = change >= 0;

  const high52 = dailyBars?.length ? Math.max(...dailyBars.slice(0, 252).map((b) => b.high)) : null;
  const low52 = dailyBars?.length ? Math.min(...dailyBars.slice(0, 252).map((b) => b.low)) : null;
  const rangePos =
    latest && high52 != null && low52 != null && high52 !== low52
      ? ((latest.close - low52) / (high52 - low52)) * 100
      : null;

  const chartContainer = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainer.current || sliceData.length === 0) return;
    const surface = getComputedStyle(document.documentElement).getPropertyValue('--surface').trim();
    const text = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
    const border = getComputedStyle(document.documentElement).getPropertyValue('--border').trim();
    const green = getComputedStyle(document.documentElement).getPropertyValue('--green').trim();
    const red = getComputedStyle(document.documentElement).getPropertyValue('--red').trim();
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();

    const chart = createChart(chartContainer.current, {
      layout: { background: { type: ColorType.Solid, color: surface }, textColor: text },
      grid: { horzLines: { color: border }, vertLines: { color: border } },
      rightPriceScale: { borderColor: border },
      timeScale: { borderColor: border },
      width: chartContainer.current.clientWidth,
      height: 340,
    });
    chartRef.current = chart;

    if (chartType === 'candle') {
      const series = chart.addCandlestickSeries({
        upColor: green,
        downColor: red,
        borderUpColor: green,
        borderDownColor: red,
        wickUpColor: green,
        wickDownColor: red,
      });
      series.setData(
        sliceData.map((b) => ({
          time: isIntraday
            ? (Math.floor(new Date(b.ts!).getTime() / 1000) as UTCTimestamp)
            : (b.date as string),
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
        }))
      );
      seriesRef.current = series;
    } else {
      const series = chart.addLineSeries({ color: accent, lineWidth: 2 });
      series.setData(
        sliceData.map((b) => ({
          time: isIntraday
            ? (Math.floor(new Date(b.ts!).getTime() / 1000) as UTCTimestamp)
            : (b.date as string),
          value: b.close,
        }))
      );
      seriesRef.current = series;
    }
    chart.timeScale().fitContent();

    const onResize = () => {
      if (chartContainer.current) {
        chart.applyOptions({ width: chartContainer.current.clientWidth });
      }
    };
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      seriesRef.current = null;
      chart.remove();
      chartRef.current = null;
    };
  }, [sliceData, chartType, darkMode, isIntraday]);

  if (tickerLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <Loader2 className="animate-spin" color="var(--text2)" />
      </div>
    );
  }

  if (!ticker) {
    return (
      <div style={{ padding: '28px 32px', color: 'var(--text2)' }}>Ticker not found.</div>
    );
  }

  const toggleWatch = () => {
    if (inWatch) removeWatchlist(ticker.symbol);
    else addWatchlist({ symbol: ticker.symbol, name: ticker.name });
  };

  const stats: [string, string][] = [
    ['Market Cap', fmtCap(ticker.market_cap)],
    ['Exchange', ticker.exchange || '—'],
    ['Sector', ticker.sector || '—'],
    ['Industry', ticker.industry || '—'],
    ['52W High', high52 != null ? `$${high52.toFixed(2)}` : '—'],
    ['52W Low', low52 != null ? `$${low52.toFixed(2)}` : '—'],
    ['Volume', fmtVol(latest?.volume)],
    ['Bars Loaded', bars ? String(bars.length) : '—'],
  ];

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button
            onClick={() => navigate(-1)}
            className="nav-btn"
            style={{
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 6,
              color: 'var(--text2)',
              fontSize: 12,
              padding: '6px 12px',
              cursor: 'pointer',
            }}
          >
            ← Back
          </button>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <h1 className="mono" style={{ fontSize: 26, fontWeight: 800, margin: 0 }}>
              {ticker.symbol}
            </h1>
            <span style={{ fontSize: 15, color: 'var(--text2)' }}>{ticker.name}</span>
            {ticker.sector && (
              <span
                style={{
                  fontSize: 11,
                  padding: '3px 8px',
                  borderRadius: 4,
                  background: 'var(--surface2)',
                  color: 'var(--text2)',
                }}
              >
                {ticker.sector}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={toggleWatch}
          style={{
            padding: '8px 18px',
            borderRadius: 6,
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            background: inWatch ? 'var(--accent)' : 'var(--surface2)',
            color: inWatch ? '#fff' : 'var(--text)',
            border: `1px solid ${inWatch ? 'var(--accent)' : 'var(--border)'}`,
          }}
        >
          {inWatch ? '★ Watching' : '☆ Watch'}
        </button>
      </div>

      {latest && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div
            className="mono"
            style={{ fontSize: 38, fontWeight: 700, letterSpacing: '-1px' }}
          >
            ${latest.close.toFixed(2)}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span
              className="mono"
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: positive ? 'var(--green)' : 'var(--red)',
              }}
            >
              {positive ? '+' : ''}
              {change.toFixed(2)} ({positive ? '+' : ''}
              {changePct.toFixed(2)}% · {timeframe})
            </span>
            <span style={{ fontSize: 11, color: 'var(--text2)' }}>
              Latest close · {latest.date || latest.ts}
            </span>
          </div>
        </div>
      )}

      <div className="card" style={{ overflow: 'hidden' }}>
        <div
          style={{
            padding: '14px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', gap: 4 }}>
            {INTRADAY_TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => { setIntradayTF(tf); }}
                style={{
                  padding: '5px 12px',
                  borderRadius: 5,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: intradayTF === tf ? 'var(--accent)' : 'transparent',
                  color: intradayTF === tf ? '#fff' : 'var(--text2)',
                  border: `1px solid ${intradayTF === tf ? 'var(--accent)' : 'transparent'}`,
                }}
              >
                {tf}
              </button>
            ))}
            <div style={{ width: 1, background: 'var(--border)', margin: '4px 4px' }} />
            {(Object.keys(DAILY_TIMEFRAMES) as DailyTF[]).map((tf) => (
              <button
                key={tf}
                onClick={() => { setIntradayTF(null); setTimeframe(tf); }}
                style={{
                  padding: '5px 12px',
                  borderRadius: 5,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: !isIntraday && timeframe === tf ? 'var(--accent)' : 'transparent',
                  color: !isIntraday && timeframe === tf ? '#fff' : 'var(--text2)',
                  border: `1px solid ${!isIntraday && timeframe === tf ? 'var(--accent)' : 'transparent'}`,
                }}
              >
                {tf}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {([['line', 'Line'], ['candle', 'Candle']] as const).map(([type, label]) => (
              <button
                key={type}
                onClick={() => setChartType(type)}
                style={{
                  padding: '5px 12px',
                  borderRadius: 5,
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: 'pointer',
                  background: chartType === type ? 'var(--surface2)' : 'transparent',
                  color: chartType === type ? 'var(--text)' : 'var(--text2)',
                  border: `1px solid ${chartType === type ? 'var(--border)' : 'transparent'}`,
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div style={{ padding: '8px 8px 4px' }}>
          {barsLoading ? (
            <div style={{ height: 340, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Loader2 className="animate-spin" color="var(--text2)" />
            </div>
          ) : sliceData.length === 0 ? (
            <div
              style={{
                height: 340,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text2)',
                fontSize: 13,
              }}
            >
              {isIntraday ? 'No intraday data available for this timeframe.' : 'No price data available.'}
            </div>
          ) : (
            <div ref={chartContainer} style={{ width: '100%', height: 340 }} />
          )}
        </div>
      </div>

      {rangePos != null && high52 != null && low52 != null && (
        <div className="card" style={{ padding: '16px 20px' }}>
          <div
            style={{
              fontSize: 11,
              color: 'var(--text2)',
              marginBottom: 10,
              letterSpacing: '0.05em',
            }}
          >
            52-WEEK RANGE
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="mono" style={{ fontSize: 12, color: 'var(--red)' }}>
              L ${low52.toFixed(2)}
            </span>
            <div
              style={{
                flex: 1,
                height: 4,
                background: 'var(--surface2)',
                borderRadius: 2,
                position: 'relative',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  height: '100%',
                  width: `${rangePos}%`,
                  background: 'linear-gradient(90deg, var(--red), var(--green))',
                  borderRadius: 2,
                }}
              />
              <div
                style={{
                  position: 'absolute',
                  top: -4,
                  left: `${rangePos}%`,
                  transform: 'translateX(-50%)',
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  background: 'var(--accent)',
                  border: '2px solid var(--surface)',
                  boxShadow: '0 0 0 2px var(--accent)',
                }}
              />
            </div>
            <span className="mono" style={{ fontSize: 12, color: 'var(--green)' }}>
              H ${high52.toFixed(2)}
            </span>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {stats.map(([label, value]) => (
          <div key={label} className="card" style={{ padding: '14px 16px' }}>
            <div
              style={{
                fontSize: 11,
                color: 'var(--text2)',
                marginBottom: 6,
                letterSpacing: '0.05em',
              }}
            >
              {label.toUpperCase()}
            </div>
            <div
              className="mono"
              style={{
                fontSize: 16,
                fontWeight: 600,
                color: 'var(--text)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {value}
            </div>
          </div>
        ))}
      </div>

      {fundamentals && fundamentals.length > 0 && (
        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 14, letterSpacing: '0.05em' }}>
            QUARTERLY FUNDAMENTALS (TRAILING 8Q)
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr>
                  {['Period', 'Revenue', 'EPS', 'P/E Ratio', 'Market Cap'].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: 'left',
                        padding: '6px 12px',
                        color: 'var(--text2)',
                        fontWeight: 500,
                        borderBottom: '1px solid var(--border)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fundamentals.map((row) => (
                  <tr key={row.period} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td className="mono" style={{ padding: '8px 12px', fontWeight: 600 }}>{row.period}</td>
                    <td className="mono" style={{ padding: '8px 12px' }}>
                      {row.revenue ? fmtCap(row.revenue) : '—'}
                    </td>
                    <td className="mono" style={{ padding: '8px 12px' }}>
                      {row.eps != null ? `$${Number(row.eps).toFixed(2)}` : '—'}
                    </td>
                    <td className="mono" style={{ padding: '8px 12px' }}>
                      {row.pe_ratio != null ? Number(row.pe_ratio).toFixed(1) : '—'}
                    </td>
                    <td className="mono" style={{ padding: '8px 12px' }}>
                      {row.market_cap ? fmtCap(String(row.market_cap)) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
