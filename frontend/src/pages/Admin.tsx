import { useState, useEffect, useRef } from 'react';
import { Play, CheckCircle, XCircle, Loader, Clock, Settings, ChevronDown, StopCircle, Terminal } from 'lucide-react';
import {
  useTriggerTask,
  useTaskStatus,
  useJobConfigs,
  useUpdateJobConfig,
  useActiveTasks,
  useRevokeTask,
  useTaskLogs,
  type AdminTask,
  type TaskEnqueued,
  type JobConfig,
  type ActiveTask,
} from '../api/hooks';

interface JobDef {
  id: AdminTask;
  label: string;
  description: string;
}

const JOBS: JobDef[] = [
  {
    id: 'refresh-tickers',
    label: 'Refresh Tickers',
    description: 'Pull latest ticker reference data from Polygon.',
  },
  {
    id: 'ingest-daily-ohlcv',
    label: 'Ingest Daily OHLCV',
    description: 'Backfill daily OHLCV bars for all active tickers.',
  },
  {
    id: 'ingest-fundamentals',
    label: 'Ingest Fundamentals',
    description: 'Fetch quarterly fundamentals via yfinance for all active tickers.',
  },
  {
    id: 'run-active-scans',
    label: 'Run Active Scans',
    description: 'Re-evaluate all active scanner definitions against latest data.',
  },
  {
    id: 'poll-intraday-bars',
    label: 'Poll Intraday Bars',
    description: 'Fetch latest intraday bars from yfinance for open market session.',
  },
];

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { color: string; icon: React.ReactNode }> = {
    SUCCESS: { color: 'var(--green)', icon: <CheckCircle size={13} /> },
    FAILURE: { color: 'var(--red)', icon: <XCircle size={13} /> },
    PENDING: { color: 'var(--text2)', icon: <Clock size={13} /> },
    STARTED: { color: 'var(--accent)', icon: <Loader size={13} className="spin" /> },
    RETRY: { color: '#f59e0b', icon: <Loader size={13} /> },
  };
  const { color, icon } = cfg[status] ?? { color: 'var(--text2)', icon: <Clock size={13} /> };
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: 11,
        fontWeight: 600,
        color,
        background: `${color}18`,
        border: `1px solid ${color}40`,
        borderRadius: 4,
        padding: '2px 8px',
      }}
    >
      {icon}
      {status}
    </span>
  );
}

function LogViewer({ taskId }: { taskId: string }) {
  const { data } = useTaskLogs(taskId, true);
  const logs = data?.logs ?? [];
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs.length]);

  return (
    <div
      style={{
        background: '#0d1117',
        border: '1px solid var(--border)',
        borderRadius: 6,
        padding: '10px 12px',
        maxHeight: 220,
        overflowY: 'auto',
        fontFamily: 'monospace',
        fontSize: 11,
        color: '#e6edf3',
        marginTop: 10,
        lineHeight: 1.6,
      }}
    >
      {logs.length === 0 ? (
        <span style={{ color: 'var(--text2)' }}>Waiting for logs…</span>
      ) : (
        logs.map((line, i) => (
          <div key={i} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {line}
          </div>
        ))
      )}
      <div ref={endRef} />
    </div>
  );
}

function JobRow({ job }: { job: JobDef }) {
  const [enqueued, setEnqueued] = useState<TaskEnqueued | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const trigger = useTriggerTask(job.id, {
    onSuccess: (data) => { setEnqueued(data); setShowLogs(true); },
  });
  const { data: statusData } = useTaskStatus(enqueued?.task_id ?? null);

  const running =
    statusData?.status && !['SUCCESS', 'FAILURE', 'REVOKED'].includes(statusData.status);

  return (
    <div style={{ borderBottom: '1px solid var(--border)' }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '200px 1fr auto auto auto',
          alignItems: 'center',
          gap: 16,
          padding: '14px 20px',
        }}
      >
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{job.label}</div>
          {enqueued && (
            <div
              className="mono"
              style={{ fontSize: 10, color: 'var(--text2)', marginTop: 2, wordBreak: 'break-all' }}
            >
              {enqueued.task_id.slice(0, 16)}…
            </div>
          )}
        </div>

        <div style={{ fontSize: 12, color: 'var(--text2)' }}>{job.description}</div>

        <div style={{ minWidth: 90, textAlign: 'right' }}>
          {statusData ? (
            <StatusBadge status={statusData.status} />
          ) : (
            <span style={{ fontSize: 11, color: 'var(--text2)' }}>—</span>
          )}
        </div>

        {enqueued ? (
          <button
            onClick={() => setShowLogs((s) => !s)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 10px',
              borderRadius: 5,
              fontSize: 11,
              background: showLogs ? 'var(--accent)18' : 'var(--surface2)',
              color: showLogs ? 'var(--accent)' : 'var(--text2)',
              border: `1px solid ${showLogs ? 'var(--accent)40' : 'var(--border)'}`,
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            <Terminal size={11} />
            Logs
          </button>
        ) : (
          <span />
        )}

        <button
          onClick={() => trigger.mutate()}
          disabled={trigger.isPending || !!running}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 14px',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 600,
            background: trigger.isPending || running ? 'var(--surface2)' : 'var(--accent)',
            color: trigger.isPending || running ? 'var(--text2)' : '#fff',
            border: 'none',
            cursor: trigger.isPending || running ? 'not-allowed' : 'pointer',
            transition: 'background 0.15s',
            flexShrink: 0,
          }}
        >
          {trigger.isPending || running ? (
            <Loader size={12} style={{ animation: 'spin 1s linear infinite' }} />
          ) : (
            <Play size={12} />
          )}
          Run
        </button>
      </div>

      {showLogs && enqueued && (
        <div style={{ padding: '0 20px 14px' }}>
          <LogViewer taskId={enqueued.task_id} />
        </div>
      )}
    </div>
  );
}

// ---- Running Jobs ----

const TASK_NAME_MAP: Record<string, string> = {
  'app.ingestion.tasks.ingest_daily_ohlcv': 'Ingest Daily OHLCV',
  'app.ingestion.tasks.refresh_tickers': 'Refresh Tickers',
  'app.ingestion.tasks.run_active_scans': 'Run Active Scans',
  'app.ingestion.tasks.poll_yfinance_bars': 'Poll Intraday Bars',
  'app.ingestion.tasks.ingest_fundamentals': 'Ingest Fundamentals',
};

function RunningTaskRow({ task }: { task: ActiveTask }) {
  const [showLogs, setShowLogs] = useState(false);
  const [elapsed, setElapsed] = useState(
    task.time_start ? Math.floor(Date.now() / 1000 - task.time_start) : null
  );
  const revoke = useRevokeTask();

  useEffect(() => {
    if (!task.time_start) return;
    const id = setInterval(() => {
      setElapsed(Math.floor(Date.now() / 1000 - task.time_start!));
    }, 1000);
    return () => clearInterval(id);
  }, [task.time_start]);

  const friendlyName = TASK_NAME_MAP[task.task_name] ?? task.task_name;

  return (
    <div style={{ borderBottom: '1px solid var(--border)' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 20px',
        }}
      >
        <Loader
          size={13}
          style={{ animation: 'spin 1s linear infinite', color: 'var(--accent)', flexShrink: 0 }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{friendlyName}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text2)', marginTop: 2 }}>
            {task.task_id.slice(0, 20)}…{elapsed !== null ? ` · ${elapsed}s` : ''}
          </div>
        </div>
        <button
          onClick={() => setShowLogs((s) => !s)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 11,
            padding: '4px 10px',
            borderRadius: 4,
            background: showLogs ? 'var(--accent)18' : 'var(--surface2)',
            color: showLogs ? 'var(--accent)' : 'var(--text2)',
            border: `1px solid ${showLogs ? 'var(--accent)40' : 'var(--border)'}`,
            cursor: 'pointer',
            flexShrink: 0,
          }}
        >
          <Terminal size={11} />
          Logs
        </button>
        <button
          onClick={() => revoke.mutate(task.task_id)}
          disabled={revoke.isPending}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 11,
            padding: '4px 10px',
            borderRadius: 4,
            background: 'transparent',
            color: 'var(--red)',
            border: '1px solid color-mix(in srgb, var(--red) 40%, transparent)',
            cursor: revoke.isPending ? 'not-allowed' : 'pointer',
            flexShrink: 0,
          }}
        >
          <StopCircle size={11} />
          Cancel
        </button>
      </div>
      {showLogs && (
        <div style={{ padding: '0 20px 14px' }}>
          <LogViewer taskId={task.task_id} />
        </div>
      )}
    </div>
  );
}

function RunningJobsSection() {
  const { data: tasks = [], isLoading, isFetching } = useActiveTasks();

  return (
    <div style={{ marginTop: 32 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 12,
        }}
      >
        <h2 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Running Jobs</h2>
        {(isLoading || isFetching) && (
          <Loader size={11} style={{ animation: 'spin 1s linear infinite', color: 'var(--text2)' }} />
        )}
        <span style={{ fontSize: 11, color: 'var(--text2)', marginLeft: 'auto' }}>
          refreshes every 5s
        </span>
      </div>
      <div
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        {tasks.length === 0 ? (
          <div
            style={{
              padding: '20px',
              fontSize: 13,
              color: 'var(--text2)',
              textAlign: 'center',
            }}
          >
            No jobs currently running
          </div>
        ) : (
          tasks.map((task) => <RunningTaskRow key={task.task_id} task={task} />)
        )}
      </div>
    </div>
  );
}

// ---- Job Config Panel ----

const JOB_CONFIG_DEFS: { job_name: string; label: string; description: string; hasUniverse: boolean }[] = [
  { job_name: 'poll-intraday-bars', label: 'Poll Intraday Bars', description: 'Fetches intraday OHLCV bars during market hours via yfinance.', hasUniverse: true },
  { job_name: 'ingest-daily-ohlcv', label: 'Ingest Daily OHLCV', description: 'Backfills previous day OHLCV bars after market close.', hasUniverse: true },
  { job_name: 'ingest-fundamentals', label: 'Ingest Fundamentals', description: 'Fetches quarterly fundamentals via yfinance weekly.', hasUniverse: true },
  { job_name: 'refresh-tickers', label: 'Refresh Tickers', description: 'Syncs ticker reference data from Finnhub.', hasUniverse: false },
  { job_name: 'run-active-scans', label: 'Run Active Scans', description: 'Re-evaluates all active scanner definitions.', hasUniverse: false },
];

function ExtraConfigEditor({
  jobName,
  value,
  onChange,
}: {
  jobName: string;
  value: Record<string, unknown>;
  onChange: (v: Record<string, unknown>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [raw, setRaw] = useState(JSON.stringify(value, null, 2));
  const [error, setError] = useState('');

  const handleBlur = () => {
    try {
      onChange(JSON.parse(raw));
      setError('');
    } catch {
      setError('Invalid JSON');
    }
  };

  if (Object.keys(value).length === 0 && jobName !== 'poll-intraday-bars') return null;

  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 11,
          color: 'var(--text2)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
        }}
      >
        <ChevronDown size={12} style={{ transform: open ? 'rotate(180deg)' : undefined, transition: 'transform 0.15s' }} />
        Extra config
      </button>
      {open && (
        <div style={{ marginTop: 6 }}>
          <textarea
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            onBlur={handleBlur}
            rows={Object.keys(value).length + 2}
            style={{
              width: '100%',
              fontFamily: 'monospace',
              fontSize: 11,
              padding: '6px 8px',
              background: 'var(--surface2)',
              border: `1px solid ${error ? 'var(--red)' : 'var(--border)'}`,
              borderRadius: 4,
              color: 'var(--text)',
              resize: 'vertical',
            }}
          />
          {error && <div style={{ fontSize: 10, color: 'var(--red)', marginTop: 2 }}>{error}</div>}
        </div>
      )}
    </div>
  );
}

function JobConfigRow({ def, config }: { def: typeof JOB_CONFIG_DEFS[0]; config: JobConfig | undefined }) {
  const update = useUpdateJobConfig();
  const [draft, setDraft] = useState<Partial<JobConfig> | null>(null);
  const current = draft ?? config;

  if (!current) {
    return (
      <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', fontSize: 12, color: 'var(--text2)' }}>
        {def.label} — config not found (run migration)
      </div>
    );
  }

  const isDirty = draft !== null;

  const save = () => {
    if (!draft) return;
    update.mutate(
      {
        jobName: def.job_name,
        update: {
          enabled: draft.enabled,
          universe_filter: draft.universe_filter,
          cron_schedule: draft.cron_schedule ?? undefined,
          extra_config: draft.extra_config,
        },
      },
      { onSuccess: () => setDraft(null) }
    );
  };

  return (
    <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr auto', gap: 16, alignItems: 'start' }}>
        {/* Label + toggle */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <label style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={current.enabled}
                onChange={(e) => setDraft({ ...current, enabled: e.target.checked })}
                style={{ width: 0, height: 0, opacity: 0, position: 'absolute' }}
              />
              <span
                style={{
                  width: 32,
                  height: 18,
                  borderRadius: 9,
                  background: current.enabled ? 'var(--accent)' : 'var(--border)',
                  position: 'relative',
                  display: 'inline-block',
                  transition: 'background 0.2s',
                  flexShrink: 0,
                }}
              >
                <span
                  style={{
                    position: 'absolute',
                    top: 2,
                    left: current.enabled ? 16 : 2,
                    width: 14,
                    height: 14,
                    borderRadius: '50%',
                    background: '#fff',
                    transition: 'left 0.2s',
                  }}
                />
              </span>
            </label>
            <span style={{ fontWeight: 600, fontSize: 13 }}>{def.label}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text2)' }}>{def.description}</div>
        </div>

        {/* Fields */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {def.hasUniverse && (
            <div>
              <label style={{ fontSize: 11, color: 'var(--text2)', display: 'block', marginBottom: 3 }}>
                Universe filter
                <span style={{ marginLeft: 6, color: 'var(--text2)', fontWeight: 400 }}>
                  (comma-separated exchange codes, e.g. XNAS,XNYS — or ALL)
                </span>
              </label>
              <input
                type="text"
                value={current.universe_filter}
                onChange={(e) => setDraft({ ...current, universe_filter: e.target.value })}
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  fontSize: 12,
                  background: 'var(--surface2)',
                  border: '1px solid var(--border)',
                  borderRadius: 4,
                  color: 'var(--text)',
                  fontFamily: 'monospace',
                }}
              />
            </div>
          )}
          <div>
            <label style={{ fontSize: 11, color: 'var(--text2)', display: 'block', marginBottom: 3 }}>
              Schedule (cron)
              <span style={{ marginLeft: 6, color: 'var(--text2)', fontWeight: 400 }}>
                — display only, restart worker to apply
              </span>
            </label>
            <input
              type="text"
              value={current.cron_schedule ?? ''}
              onChange={(e) => setDraft({ ...current, cron_schedule: e.target.value })}
              style={{
                width: '100%',
                padding: '5px 8px',
                fontSize: 12,
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                color: 'var(--text)',
                fontFamily: 'monospace',
              }}
            />
          </div>
          <ExtraConfigEditor
            jobName={def.job_name}
            value={current.extra_config}
            onChange={(v) => setDraft({ ...current, extra_config: v })}
          />
        </div>

        {/* Save */}
        <div style={{ paddingTop: 2 }}>
          <button
            onClick={save}
            disabled={!isDirty || update.isPending}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              background: isDirty && !update.isPending ? 'var(--accent)' : 'var(--surface2)',
              color: isDirty && !update.isPending ? '#fff' : 'var(--text2)',
              border: 'none',
              cursor: isDirty && !update.isPending ? 'pointer' : 'not-allowed',
              transition: 'background 0.15s',
              whiteSpace: 'nowrap',
            }}
          >
            {update.isPending ? <Loader size={12} style={{ animation: 'spin 1s linear infinite' }} /> : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}

function JobConfigPanel() {
  const { data: configs, isLoading, isError } = useJobConfigs();

  if (isLoading) {
    return <div style={{ padding: 32, fontSize: 13, color: 'var(--text2)' }}>Loading job configs…</div>;
  }
  if (isError) {
    return <div style={{ padding: 32, fontSize: 13, color: 'var(--red)' }}>Failed to load job configs.</div>;
  }

  const byName = Object.fromEntries((configs ?? []).map((c) => [c.job_name, c]));

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--text2)', marginTop: 0, marginBottom: 20 }}>
        Configure universe filters, schedules, and extra parameters per job. Universe filter accepts
        comma-separated exchange codes (e.g. <code>XNAS,XNYS</code>) or <code>ALL</code>. Schedule
        changes are saved to the database but require a worker restart to take effect.
      </p>
      <div
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        {JOB_CONFIG_DEFS.map((def) => (
          <JobConfigRow key={def.job_name} def={def} config={byName[def.job_name]} />
        ))}
      </div>
    </div>
  );
}

// ---- Main Admin Page ----

type Tab = 'runner' | 'config';

export default function Admin() {
  const [tab, setTab] = useState<Tab>('runner');

  return (
    <div style={{ padding: 32, maxWidth: 960 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Admin</h1>
      </div>

      {/* Tab bar */}
      <div
        style={{
          display: 'flex',
          gap: 2,
          marginBottom: 24,
          borderBottom: '1px solid var(--border)',
        }}
      >
        {(
          [
            { id: 'runner' as Tab, label: 'Job Runner', icon: <Play size={13} /> },
            { id: 'config' as Tab, label: 'Job Config', icon: <Settings size={13} /> },
          ] as const
        ).map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 16px',
              fontSize: 13,
              fontWeight: tab === id ? 600 : 400,
              color: tab === id ? 'var(--accent)' : 'var(--text2)',
              background: 'none',
              border: 'none',
              borderBottom: tab === id ? '2px solid var(--accent)' : '2px solid transparent',
              cursor: 'pointer',
              marginBottom: -1,
              transition: 'color 0.15s',
            }}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {tab === 'runner' && (
        <>
          <p style={{ fontSize: 13, color: 'var(--text2)', marginTop: 0, marginBottom: 20 }}>
            Manually trigger Celery background tasks. Status auto-refreshes every 2 seconds until
            completion.
          </p>
          <div
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '200px 1fr auto auto auto',
                gap: 16,
                padding: '10px 20px',
                background: 'var(--surface2)',
                borderBottom: '1px solid var(--border)',
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--text2)',
                letterSpacing: '0.06em',
              }}
            >
              <span>JOB</span>
              <span>DESCRIPTION</span>
              <span style={{ textAlign: 'right' }}>STATUS</span>
              <span />
              <span />
            </div>
            {JOBS.map((job) => (
              <JobRow key={job.id} job={job} />
            ))}
          </div>
          <RunningJobsSection />
        </>
      )}

      {tab === 'config' && <JobConfigPanel />}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
