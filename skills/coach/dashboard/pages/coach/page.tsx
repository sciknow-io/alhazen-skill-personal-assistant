'use client';

import { useEffect, useState, useCallback, CSSProperties } from 'react';
import Link from 'next/link';
import { T, trendColor, trendArrow, fmtMetric, fmtNum, fmtDate } from '@/components/coach/tokens';
import MarkdownContent from '@/components/agentic-memory/markdown';

/* ================================================================
   TYPES
   ================================================================ */

interface Trend {
  metric_type: string;
  latest_value: number;
  latest_date: string;
  avg_7d: number;
  avg_30d: number;
  delta_7d: number;
  delta_30d: number;
  direction: string;
}

interface Goal {
  id: string;
  name: string;
  metric: string;
  target: number;
  direction: string;
  status: string;
}

interface Appointment {
  id: string;
  name: string;
  type: string;
  date: string;
  status: string;
  provider: string | null;
  prep: string | null;
}

interface Recommendation {
  id: string;
  name: string;
  content: string;
  priority: string;
  status: string;
}

interface PipelineStatus {
  last_ingest_date: string | null;
  records_count: number | null;
  health: string | null;
}

interface SleepNight {
  id: string;
  date: string;
  asleep_hrs: number | null;
  deep_hrs: number | null;
  core_hrs: number | null;
  rem_hrs: number | null;
  awake_hrs: number | null;
  in_bed_hrs: number | null;
}

interface Workout {
  id: string;
  name: string;
  type: string;
  date: string;
  duration_min: number | null;
  distance_mi: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  active_energy_kcal: number | null;
}

interface Provider {
  id: string;
  name: string;
  type: string;
  cadence_months: number | null;
}

interface NutritionDay {
  id: string;
  date: string;
  calories: number | null;
  protein: number | null;
  carbs: number | null;
  fat: number | null;
  fiber: number | null;
  sugar: number | null;
}

interface Profile {
  id: string;
  name: string;
  timezone: string | null;
  baseline_rhr: number | null;
  baseline_hrv: number | null;
  sleep_target_hrs: number | null;
  step_goal: number | null;
}

interface Assessment {
  id: string;
  name: string;
  date: string;
  content?: string;
}

interface TeamMember {
  person_id: string;
  person_name: string;
  role_type: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  status: string;
}

/* ================================================================
   TABS
   ================================================================ */

type TabKey = 'overview' | 'trends' | 'sleep' | 'workouts' | 'nutrition' | 'appointments' | 'about';

const TAB_ITEMS: { key: TabKey; label: string }[] = [
  { key: 'overview',     label: 'Overview' },
  { key: 'trends',       label: 'Trends' },
  { key: 'sleep',        label: 'Sleep' },
  { key: 'workouts',     label: 'Workouts' },
  { key: 'nutrition',    label: 'Nutrition' },
  { key: 'appointments', label: 'Appointments' },
  { key: 'about',        label: 'About Me' },
];

/* ================================================================
   METRIC CATEGORIES (for Trends tab grouping)
   ================================================================ */

const VITALS = new Set([
  'heart_rate', 'heart_rate_variability', 'blood_oxygen_saturation',
  'respiratory_rate', 'resting_heart_rate',
]);
const ACTIVITY = new Set([
  'step_count', 'active_energy', 'walking_running_distance',
  'apple_exercise_time', 'flights_climbed', 'apple_stand_time',
]);

function metricCategory(type: string): string {
  if (VITALS.has(type)) return 'Vitals';
  if (ACTIVITY.has(type)) return 'Activity';
  return 'Other';
}

/* ================================================================
   SLEEP STAGE COLORS
   ================================================================ */

const STAGE_COLORS: Record<string, string> = {
  deep: T.blue,
  core: T.teal,
  rem:  T.olive,
  awake: T.rust,
};

/* ================================================================
   MAIN COMPONENT
   ================================================================ */

export default function CoachPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');

  // Overview data
  const [trends, setTrends] = useState<Trend[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);

  // Tab-specific data (lazy loaded)
  const [sleepData, setSleepData] = useState<{ nights: SleepNight[]; averages: Record<string, number> } | null>(null);
  const [workouts, setWorkouts] = useState<Workout[] | null>(null);
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [allTrends, setAllTrends] = useState<Trend[] | null>(null);
  const [nutritionData, setNutritionData] = useState<{ days: NutritionDay[]; averages: Record<string, number> } | null>(null);
  const [assessments, setAssessments] = useState<Assessment[] | null>(null);
  const [supportTeam, setSupportTeam] = useState<TeamMember[] | null>(null);

  const [loading, setLoading] = useState(true);

  // Load overview data on mount
  useEffect(() => {
    Promise.all([
      fetch('/api/coach/trends').then(r => r.json()),
      fetch('/api/coach/goals').then(r => r.json()),
      fetch('/api/coach/appointments').then(r => r.json()),
      fetch('/api/coach/recommendations').then(r => r.json()),
      fetch('/api/coach/pipeline').then(r => r.json()),
      fetch('/api/coach/profile').then(r => r.json()),
      fetch('/api/coach/assessments').then(r => r.json()),
    ]).then(([t, g, a, r, p, prof, assess]) => {
      setTrends(t.trends || []);
      setGoals(g.goals || []);
      setAppointments(a.appointments || []);
      setRecommendations(r.recommendations || []);
      setPipeline(p.pipeline || null);
      setProfile(prof.profile || null);
      setAssessments(assess.assessments || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  // Lazy-load tab data
  useEffect(() => {
    if (activeTab === 'sleep' && !sleepData) {
      fetch('/api/coach/sleep?days=30').then(r => r.json()).then(d => {
        setSleepData({ nights: d.nights || [], averages: d.averages || {} });
      });
    }
    if (activeTab === 'workouts' && !workouts) {
      fetch('/api/coach/workouts?limit=30').then(r => r.json()).then(d => {
        setWorkouts(d.workouts || []);
      });
    }
    if (activeTab === 'appointments' && !providers) {
      fetch('/api/coach/pipeline').then(r => r.json()); // already loaded
      // Load providers
      // Note: no dedicated providers API yet, reuse appointments
    }
    if (activeTab === 'trends' && !allTrends) {
      fetch('/api/coach/trends').then(r => r.json()).then(d => {
        setAllTrends(d.trends || []);
      });
    }
    if (activeTab === 'about' && !supportTeam) {
      fetch('/api/coach/support-team').then(r => r.json()).then(d => {
        setSupportTeam(d.team || []);
      });
    }
    if (activeTab === 'nutrition' && !nutritionData) {
      fetch('/api/coach/nutrition?days=30').then(r => r.json()).then(d => {
        setNutritionData({ days: d.days || [], averages: d.averages || {} });
      });
    }
  }, [activeTab, sleepData, workouts, providers, allTrends, nutritionData, supportTeam]);

  /* ── Styles ── */

  const pageStyle: CSSProperties = {
    height: '100vh',
    background: T.bg,
    color: T.fg,
    fontFamily: T.sans,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  };

  const headerStyle: CSSProperties = {
    padding: '12px 16px 0 16px',
    flexShrink: 0,
  };

  const tabBarStyle: CSSProperties = {
    display: 'flex',
    gap: 0,
    borderBottom: `1px solid ${T.border}`,
    marginTop: 8,
  };

  const contentStyle: CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: '20px 24px',
  };

  if (loading) {
    return (
      <div style={{ ...pageStyle, alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: T.fgDim, fontFamily: T.mono, fontSize: 11 }}>loading health data...</span>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      {/* ── Header ── */}
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Link href="/" style={{
              fontFamily: T.mono, fontSize: 11, color: T.fgFaint,
              textDecoration: 'none', transition: 'color 0.15s',
            }}
              onMouseEnter={e => { e.currentTarget.style.color = T.teal; }}
              onMouseLeave={e => { e.currentTarget.style.color = T.fgFaint; }}
            >
              &larr; hub
            </Link>
            <h1 style={{
              fontFamily: T.serif, fontSize: 24, color: T.fg,
              margin: 0, lineHeight: 1.2, fontWeight: 400,
            }}>
              Health Coach
            </h1>
            {pipeline && (
              <span style={{
                fontFamily: T.mono, fontSize: 10, letterSpacing: 0.8,
                padding: '2px 8px', borderRadius: 3,
                background: pipeline.health === 'healthy' ? 'rgba(98,196,188,0.15)' : T.rustDim,
                color: pipeline.health === 'healthy' ? T.mint : T.rust,
                textTransform: 'uppercase',
              }}>
                {pipeline.health || 'unknown'}
              </span>
            )}
          </div>

          {/* Profile selector — top right */}
          {profile && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: T.tealDim, border: `1px solid ${T.border}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: T.mono, fontSize: 11, color: T.teal, fontWeight: 600,
              }}>
                {profile.name?.charAt(0).toUpperCase() || '?'}
              </div>
              <div>
                <div style={{ fontFamily: T.sans, fontSize: 13, color: T.fg, lineHeight: 1.2 }}>
                  {profile.name}
                </div>
                <div style={{ fontFamily: T.mono, fontSize: 9.5, color: T.fgFaint, letterSpacing: 0.4 }}>
                  {profile.timezone || 'no timezone'}
                  {profile.baseline_rhr && ` · RHR ${profile.baseline_rhr}`}
                  {profile.step_goal && ` · ${(profile.step_goal / 1000).toFixed(0)}K steps`}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Tab bar ── */}
        <div style={tabBarStyle}>
          {TAB_ITEMS.map(tab => {
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  fontFamily: T.mono, fontSize: 11, letterSpacing: 0.6,
                  color: active ? T.teal : T.fgDim,
                  background: 'none', border: 'none', cursor: 'pointer',
                  padding: '10px 16px 8px',
                  borderBottom: active ? `2px solid ${T.teal}` : '2px solid transparent',
                  transition: 'color 0.15s, border-color 0.15s',
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.color = T.fg; }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.color = T.fgDim; }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Tab content ── */}
      <div style={contentStyle}>
        {activeTab === 'overview'     && <OverviewTab trends={trends} assessments={assessments || []} appointments={appointments} recommendations={recommendations} pipeline={pipeline} />}
        {activeTab === 'trends'       && <TrendsTab trends={allTrends || trends} />}
        {activeTab === 'sleep'        && <SleepTab data={sleepData} />}
        {activeTab === 'workouts'     && <WorkoutsTab workouts={workouts} />}
        {activeTab === 'nutrition'    && <NutritionTab data={nutritionData} />}
        {activeTab === 'appointments' && <AppointmentsTab appointments={appointments} />}
        {activeTab === 'about'        && <AboutMeTab profile={profile} goals={goals} team={supportTeam} />}
      </div>
    </div>
  );
}

/* ================================================================
   PANEL — reusable section container
   ================================================================ */

function Panel({ title, children, tint }: { title: string; children: React.ReactNode; tint?: string }) {
  return (
    <div style={{
      background: tint || T.panel,
      border: `1px solid ${T.border}`,
      borderRadius: 4,
      padding: '14px 16px',
      display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <div style={{
        fontFamily: T.mono, fontSize: 10.5, fontWeight: 600,
        letterSpacing: 1.2, textTransform: 'uppercase', color: T.fgDim,
      }}>
        {title}
      </div>
      {children}
    </div>
  );
}

/* ================================================================
   OVERVIEW TAB
   ================================================================ */

function OverviewTab({ trends, assessments, appointments, recommendations, pipeline }: {
  trends: Trend[];
  assessments: Assessment[];
  appointments: Appointment[];
  recommendations: Recommendation[];
  pipeline: PipelineStatus | null;
}) {
  const [selectedAssessment, setSelectedAssessment] = useState<Assessment | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [autoLoaded, setAutoLoaded] = useState(false);

  const loadAssessment = useCallback((a: Assessment) => {
    if (a.content) {
      setSelectedAssessment(a);
      return;
    }
    setLoadingContent(true);
    fetch(`/api/coach/assessment?id=${encodeURIComponent(a.id)}`)
      .then(r => r.json())
      .then(d => {
        const full = { ...a, content: d.assessment?.content || 'No content' };
        setSelectedAssessment(full);
        setLoadingContent(false);
      })
      .catch(() => setLoadingContent(false));
  }, []);

  // Auto-load the latest assessment on first render
  useEffect(() => {
    if (!autoLoaded && assessments.length > 0) {
      setAutoLoaded(true);
      loadAssessment(assessments[0]);
    }
  }, [assessments, autoLoaded, loadAssessment]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
        {trends.map(t => (
          <MetricCard key={t.metric_type} trend={t} />
        ))}
      </div>

      {/* Assessments — list on left, content on right */}
      <Panel title="Health Assessments">
        <div style={{ display: 'flex', gap: 16, minHeight: 200 }}>
          {/* Assessment list (left) */}
          <div style={{
            width: 200, flexShrink: 0,
            borderRight: `1px solid ${T.borderDim}`,
            paddingRight: 12,
            overflowY: 'auto',
          }}>
            {assessments.length === 0 ? (
              <span style={{ color: T.fgFaint, fontSize: 12 }}>No assessments yet</span>
            ) : assessments.map(a => {
              const isActive = selectedAssessment?.id === a.id;
              return (
                <div
                  key={a.id}
                  onClick={() => loadAssessment(a)}
                  style={{
                    padding: '8px 10px',
                    cursor: 'pointer',
                    borderRadius: 3,
                    borderLeft: isActive ? `2px solid ${T.teal}` : '2px solid transparent',
                    background: isActive ? T.tealDim : 'transparent',
                    marginBottom: 2,
                    transition: 'background 0.12s',
                  }}
                >
                  <div style={{ fontFamily: T.mono, fontSize: 11, color: isActive ? T.teal : T.fgDim }}>
                    {fmtDate(a.date)}
                  </div>
                  <div style={{ fontSize: 12, color: T.fg, marginTop: 2 }}>
                    {a.name.replace('Health Assessment ', '')}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Assessment content (right) */}
          <div style={{ flex: 1, overflowY: 'auto', paddingLeft: 4 }}>
            {loadingContent ? (
              <span style={{ color: T.fgDim, fontFamily: T.mono, fontSize: 11 }}>loading...</span>
            ) : selectedAssessment?.content ? (
              <MarkdownContent fontSize={13}>
                {selectedAssessment.content}
              </MarkdownContent>
            ) : (
              <span style={{ color: T.fgFaint, fontSize: 13 }}>
                {assessments.length > 0 ? 'Select an assessment to view' : 'No assessments yet. Ask Claude to write a health assessment.'}
              </span>
            )}
          </div>
        </div>
      </Panel>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <Panel title="Recommendations" tint="rgba(184,200,74,0.04)">
          {recommendations.map(r => {
            const prioColor = r.priority === 'high' ? T.rust : r.priority === 'medium' ? T.olive : T.fgDim;
            return (
              <div key={r.id} style={{
                padding: '10px 12px',
                borderLeft: `3px solid ${prioColor}`,
                background: T.bgRaised,
                borderRadius: '0 4px 4px 0',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: T.fg, fontSize: 13.5, fontWeight: 600 }}>{r.name}</span>
                  <span style={{ fontFamily: T.mono, fontSize: 9, textTransform: 'uppercase', color: prioColor }}>
                    {r.priority}
                  </span>
                </div>
                <div style={{ color: T.fgDim, fontSize: 13, marginTop: 4, lineHeight: 1.5 }}>{r.content}</div>
              </div>
            );
          })}
        </Panel>
      )}

      {/* Upcoming appointments */}
      {appointments.filter(a => a.status === 'upcoming').length > 0 && (
        <Panel title="Upcoming Appointments">
          {appointments.filter(a => a.status === 'upcoming').slice(0, 5).map(a => (
            <div key={a.id} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 0',
              borderBottom: `1px solid ${T.borderDim}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{
                  fontFamily: T.mono, fontSize: 9.5, textTransform: 'uppercase',
                  padding: '2px 6px', borderRadius: 3,
                  border: `1px solid ${T.borderDim}`, color: T.fgDim,
                }}>
                  {a.type}
                </span>
                <span style={{ color: T.fg, fontSize: 13.5 }}>{a.name}</span>
                {a.provider && <span style={{ color: T.fgFaint, fontSize: 12 }}>with {a.provider}</span>}
              </div>
              <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgDim }}>{fmtDate(a.date)}</span>
            </div>
          ))}
        </Panel>
      )}
    </div>
  );
}

/* ================================================================
   METRIC CARD
   ================================================================ */

function MetricCard({ trend }: { trend: Trend }) {
  const dirColor = trendColor(trend.direction);
  return (
    <div style={{
      background: T.bgRaised,
      border: `1px solid ${T.border}`,
      borderRadius: 4,
      padding: '14px 16px',
    }}>
      <div style={{
        fontFamily: T.mono, fontSize: 10, textTransform: 'uppercase',
        letterSpacing: 0.8, color: T.fgDim, marginBottom: 8,
      }}>
        {fmtMetric(trend.metric_type)}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontSize: 28, fontFamily: T.serif, fontWeight: 400, color: T.fg }}>
          {fmtNum(trend.latest_value)}
        </span>
        <span style={{ fontFamily: T.mono, fontSize: 11, color: dirColor }}>
          {trendArrow(trend.direction)} {trend.delta_7d >= 0 ? '+' : ''}{trend.delta_7d.toFixed(1)}
        </span>
      </div>
      <div style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginTop: 6 }}>
        7d avg {fmtNum(trend.avg_7d)} · 30d avg {fmtNum(trend.avg_30d)}
      </div>
    </div>
  );
}

/* ================================================================
   TRENDS TAB
   ================================================================ */

function TrendsTab({ trends }: { trends: Trend[] }) {
  // Group by category
  const groups: Record<string, Trend[]> = {};
  for (const t of trends) {
    const cat = metricCategory(t.metric_type);
    (groups[cat] ??= []).push(t);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {['Vitals', 'Activity', 'Other'].map(cat => {
        const items = groups[cat];
        if (!items?.length) return null;
        return (
          <Panel key={cat} title={cat}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
              {items.map(t => <MetricCard key={t.metric_type} trend={t} />)}
            </div>
          </Panel>
        );
      })}
    </div>
  );
}

/* ================================================================
   SLEEP TAB
   ================================================================ */

function SleepTab({ data }: { data: { nights: SleepNight[]; averages: Record<string, number> } | null }) {
  if (!data) {
    return <span style={{ color: T.fgDim, fontFamily: T.mono, fontSize: 11 }}>loading sleep data...</span>;
  }

  const { nights, averages } = data;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Summary */}
      <div style={{ display: 'flex', gap: 24 }}>
        {[
          { label: 'Avg Sleep', value: averages.sleep_hrs, unit: 'h' },
          { label: 'Avg Deep', value: averages.deep_hrs, unit: 'h' },
          { label: 'Avg REM', value: averages.rem_hrs, unit: 'h' },
        ].map(s => (
          <div key={s.label} style={{
            background: T.bgRaised, border: `1px solid ${T.border}`,
            borderRadius: 4, padding: '14px 20px', minWidth: 120,
          }}>
            <div style={{ fontFamily: T.mono, fontSize: 10, color: T.fgDim, textTransform: 'uppercase', letterSpacing: 0.8 }}>
              {s.label}
            </div>
            <div style={{ fontSize: 28, fontFamily: T.serif, color: T.fg, marginTop: 4 }}>
              {fmtNum(s.value)}<span style={{ fontSize: 14, color: T.fgDim }}>{s.unit}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, fontFamily: T.mono, fontSize: 10, color: T.fgDim }}>
        {Object.entries(STAGE_COLORS).map(([stage, color]) => (
          <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
            {stage}
          </div>
        ))}
      </div>

      {/* Nightly table */}
      <Panel title="Nightly Breakdown">
        {nights.map(n => {
          const total = (n.deep_hrs || 0) + (n.core_hrs || 0) + (n.rem_hrs || 0) + (n.awake_hrs || 0);
          const maxBar = 10; // hours for full bar width
          return (
            <div key={n.date} style={{
              display: 'grid',
              gridTemplateColumns: '80px 50px 1fr 50px',
              alignItems: 'center',
              gap: 12,
              padding: '6px 0',
              borderBottom: `1px solid ${T.borderDim}`,
            }}>
              <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgDim }}>
                {fmtDate(n.date)}
              </span>
              <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fg }}>
                {fmtNum(n.asleep_hrs || total)}h
              </span>
              {/* Stacked bar */}
              <div style={{ display: 'flex', height: 14, borderRadius: 2, overflow: 'hidden', background: T.bgSunken }}>
                {(['deep', 'core', 'rem', 'awake'] as const).map(stage => {
                  const hrs = n[`${stage}_hrs` as keyof SleepNight] as number | null;
                  if (!hrs) return null;
                  return (
                    <div
                      key={stage}
                      title={`${stage}: ${hrs.toFixed(1)}h`}
                      style={{
                        width: `${(hrs / maxBar) * 100}%`,
                        background: STAGE_COLORS[stage],
                        minWidth: hrs > 0 ? 2 : 0,
                      }}
                    />
                  );
                })}
              </div>
              <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, textAlign: 'right' }}>
                {fmtNum(n.in_bed_hrs)} ib
              </span>
            </div>
          );
        })}
      </Panel>
    </div>
  );
}

/* ================================================================
   WORKOUTS TAB
   ================================================================ */

function WorkoutsTab({ workouts }: { workouts: Workout[] | null }) {
  if (!workouts) {
    return <span style={{ color: T.fgDim, fontFamily: T.mono, fontSize: 11 }}>loading workouts...</span>;
  }

  if (workouts.length === 0) {
    return (
      <Panel title="Workouts">
        <span style={{ color: T.fgFaint, fontSize: 13 }}>No workouts recorded yet. Workouts come from full HealthKit ZIP exports only.</span>
      </Panel>
    );
  }

  return (
    <Panel title={`Recent Workouts (${workouts.length})`}>
      {workouts.map(w => (
        <div key={w.id} style={{
          display: 'grid',
          gridTemplateColumns: '80px auto 1fr',
          gap: 12,
          padding: '10px 0',
          borderBottom: `1px solid ${T.borderDim}`,
          alignItems: 'center',
        }}>
          <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgDim }}>
            {fmtDate(w.date)}
          </span>
          <span style={{
            fontFamily: T.mono, fontSize: 9.5, textTransform: 'uppercase',
            padding: '2px 6px', borderRadius: 3,
            border: `1px solid ${T.borderDim}`, color: T.teal,
            justifySelf: 'start',
          }}>
            {w.type || w.name || 'workout'}
          </span>
          <div style={{ display: 'flex', gap: 16, fontFamily: T.mono, fontSize: 11, color: T.fgDim }}>
            {w.duration_min != null && <span>{fmtNum(w.duration_min)} min</span>}
            {w.distance_mi != null && <span>{fmtNum(w.distance_mi)} mi</span>}
            {w.avg_hr != null && <span>avg {fmtNum(w.avg_hr)} bpm</span>}
            {w.max_hr != null && <span>max {fmtNum(w.max_hr)} bpm</span>}
            {w.active_energy_kcal != null && <span>{fmtNum(w.active_energy_kcal)} kcal</span>}
          </div>
        </div>
      ))}
    </Panel>
  );
}

/* ================================================================
   NUTRITION TAB
   ================================================================ */

function NutritionTab({ data }: { data: { days: NutritionDay[]; averages: Record<string, number> } | null }) {
  if (!data) {
    return <span style={{ color: T.fgDim, fontFamily: T.mono, fontSize: 11 }}>loading nutrition data...</span>;
  }

  const { days, averages } = data;

  const MACRO_COLORS: Record<string, string> = {
    protein: T.teal,
    carbs: T.olive,
    fat: T.rust,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Summary cards */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {[
          { label: 'Avg Calories', value: averages.calories, unit: 'kcal' },
          { label: 'Avg Protein', value: averages.protein_g, unit: 'g', color: MACRO_COLORS.protein },
          { label: 'Avg Carbs', value: averages.carbs_g, unit: 'g', color: MACRO_COLORS.carbs },
          { label: 'Avg Fat', value: averages.fat_g, unit: 'g', color: MACRO_COLORS.fat },
        ].map(s => (
          <div key={s.label} style={{
            background: T.bgRaised, border: `1px solid ${T.border}`,
            borderRadius: 4, padding: '14px 20px', minWidth: 130,
          }}>
            <div style={{ fontFamily: T.mono, fontSize: 10, color: T.fgDim, textTransform: 'uppercase', letterSpacing: 0.8 }}>
              {s.label}
            </div>
            <div style={{ fontSize: 28, fontFamily: T.serif, color: s.color || T.fg, marginTop: 4 }}>
              {fmtNum(s.value)}<span style={{ fontSize: 14, color: T.fgDim }}>{s.unit}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Macro color legend */}
      <div style={{ display: 'flex', gap: 16, fontFamily: T.mono, fontSize: 10, color: T.fgDim }}>
        {Object.entries(MACRO_COLORS).map(([name, color]) => (
          <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
            {name}
          </div>
        ))}
      </div>

      {/* Daily table */}
      <Panel title={`Daily Log (${days.length} days)`}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '80px 70px 60px 60px 60px 1fr',
          gap: '4px 12px',
          fontFamily: T.mono, fontSize: 11,
        }}>
          {/* Header */}
          <span style={{ color: T.fgFaint, fontSize: 10 }}>DATE</span>
          <span style={{ color: T.fgFaint, fontSize: 10, textAlign: 'right' }}>KCAL</span>
          <span style={{ color: MACRO_COLORS.protein, fontSize: 10, textAlign: 'right' }}>PROT</span>
          <span style={{ color: MACRO_COLORS.carbs, fontSize: 10, textAlign: 'right' }}>CARBS</span>
          <span style={{ color: MACRO_COLORS.fat, fontSize: 10, textAlign: 'right' }}>FAT</span>
          <span style={{ color: T.fgFaint, fontSize: 10 }}>MACRO BAR</span>

          {days.map(d => {
            const totalMacro = (d.protein || 0) + (d.carbs || 0) + (d.fat || 0);
            const maxBar = 250; // grams for full width
            return (
              <div key={d.date} style={{ display: 'contents' }}>
                <span style={{ color: T.fgDim }}>{fmtDate(d.date)}</span>
                <span style={{ color: T.fg, textAlign: 'right' }}>{fmtNum(d.calories)}</span>
                <span style={{ color: MACRO_COLORS.protein, textAlign: 'right' }}>{fmtNum(d.protein)}</span>
                <span style={{ color: MACRO_COLORS.carbs, textAlign: 'right' }}>{fmtNum(d.carbs)}</span>
                <span style={{ color: MACRO_COLORS.fat, textAlign: 'right' }}>{fmtNum(d.fat)}</span>
                {/* Stacked macro bar */}
                <div style={{ display: 'flex', height: 12, borderRadius: 2, overflow: 'hidden', background: T.bgSunken, alignSelf: 'center' }}>
                  {totalMacro > 0 && (
                    <>
                      <div style={{ width: `${((d.protein || 0) / maxBar) * 100}%`, background: MACRO_COLORS.protein, minWidth: (d.protein || 0) > 0 ? 2 : 0 }} />
                      <div style={{ width: `${((d.carbs || 0) / maxBar) * 100}%`, background: MACRO_COLORS.carbs, minWidth: (d.carbs || 0) > 0 ? 2 : 0 }} />
                      <div style={{ width: `${((d.fat || 0) / maxBar) * 100}%`, background: MACRO_COLORS.fat, minWidth: (d.fat || 0) > 0 ? 2 : 0 }} />
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

/* ================================================================
   ABOUT ME TAB
   ================================================================ */

function AboutMeTab({ profile, goals, team }: { profile: Profile | null; goals: Goal[]; team: TeamMember[] | null }) {
  const ROLE_COLORS: Record<string, string> = {
    PCP: T.teal, specialist: T.blue, PT: T.olive, coach: T.mint,
    nutritionist: T.rust, dentist: T.fgDim,
  };
  if (!profile) {
    return <span style={{ color: T.fgFaint, fontSize: 13 }}>No profile set. Run: coach.py set-profile --name ...</span>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 700 }}>
      {/* Profile card */}
      <Panel title="Health Seeker Profile">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
          <div style={{
            width: 48, height: 48, borderRadius: '50%',
            background: T.tealDim, border: `2px solid ${T.teal}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: T.serif, fontSize: 22, color: T.teal,
          }}>
            {profile.name?.charAt(0).toUpperCase() || '?'}
          </div>
          <div>
            <div style={{ fontFamily: T.serif, fontSize: 22, color: T.fg }}>{profile.name}</div>
            <div style={{ fontFamily: T.mono, fontSize: 11, color: T.fgDim }}>
              {profile.timezone || 'No timezone set'}
            </div>
          </div>
        </div>

        {/* Baselines */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
          gap: 10, marginTop: 8,
        }}>
          {[
            { label: 'Baseline RHR', value: profile.baseline_rhr, unit: 'bpm' },
            { label: 'Baseline HRV', value: profile.baseline_hrv, unit: 'ms' },
            { label: 'Sleep Target', value: profile.sleep_target_hrs, unit: 'hrs' },
            { label: 'Step Goal', value: profile.step_goal, unit: 'steps' },
          ].filter(b => b.value != null).map(b => (
            <div key={b.label} style={{
              background: T.bgSunken, borderRadius: 4, padding: '10px 12px',
            }}>
              <div style={{ fontFamily: T.mono, fontSize: 9.5, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: 0.6 }}>
                {b.label}
              </div>
              <div style={{ fontSize: 20, fontFamily: T.serif, color: T.fg, marginTop: 2 }}>
                {fmtNum(b.value)}<span style={{ fontSize: 12, color: T.fgDim, marginLeft: 4 }}>{b.unit}</span>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      {/* Goals */}
      {goals.length > 0 && (
        <Panel title="Health Goals">
          {goals.map(g => (
            <div key={g.id} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '10px 0',
              borderBottom: `1px solid ${T.borderDim}`,
            }}>
              <div>
                <span style={{ color: T.fg, fontSize: 14 }}>{g.name}</span>
                <div style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginTop: 2 }}>
                  {g.metric} · {g.direction} {g.target}
                </div>
              </div>
              <span style={{
                fontFamily: T.mono, fontSize: 10, textTransform: 'uppercase',
                padding: '3px 10px', borderRadius: 3,
                background: g.status === 'active' ? T.tealDim : T.bgSunken,
                color: g.status === 'active' ? T.teal : T.fgDim,
              }}>
                {g.status}
              </span>
            </div>
          ))}
        </Panel>
      )}

      {/* Support Team */}
      {team && team.length > 0 && (
        <Panel title="Support Team">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 10 }}>
            {team.map(m => {
              const roleColor = ROLE_COLORS[m.role_type] || T.fgDim;
              return (
                <div key={m.person_id + m.role_type} style={{
                  background: T.bgSunken, borderRadius: 4, padding: '12px 14px',
                  borderLeft: `3px solid ${roleColor}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: '50%',
                      background: `${roleColor}22`, border: `1px solid ${roleColor}44`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontFamily: T.mono, fontSize: 11, color: roleColor, fontWeight: 600,
                    }}>
                      {m.person_name?.charAt(0).toUpperCase() || '?'}
                    </div>
                    <div>
                      <div style={{ fontSize: 13.5, color: T.fg, fontWeight: 500 }}>{m.person_name}</div>
                      {m.title && <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint }}>{m.title}</span>}
                    </div>
                  </div>
                  <span style={{
                    fontFamily: T.mono, fontSize: 9.5, textTransform: 'uppercase',
                    padding: '2px 6px', borderRadius: 3,
                    border: `1px solid ${roleColor}44`, color: roleColor,
                  }}>
                    {m.role_type}
                  </span>
                  {m.email && <div style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginTop: 6 }}>{m.email}</div>}
                  {m.phone && <div style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginTop: 2 }}>{m.phone}</div>}
                </div>
              );
            })}
          </div>
        </Panel>
      )}
    </div>
  );
}

/* ================================================================
   APPOINTMENTS TAB
   ================================================================ */

function AppointmentsTab({ appointments }: { appointments: Appointment[] }) {
  const upcoming = appointments.filter(a => a.status === 'upcoming').sort((a, b) => a.date.localeCompare(b.date));
  const past = appointments.filter(a => a.status !== 'upcoming').sort((a, b) => b.date.localeCompare(a.date));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Upcoming */}
      <Panel title={`Upcoming (${upcoming.length})`} tint="rgba(90,173,175,0.04)">
        {upcoming.length === 0 ? (
          <span style={{ color: T.fgFaint, fontSize: 13 }}>No upcoming appointments.</span>
        ) : upcoming.map(a => <AppointmentRow key={a.id} appt={a} />)}
      </Panel>

      {/* Past */}
      {past.length > 0 && (
        <Panel title={`Past (${past.length})`}>
          {past.map(a => <AppointmentRow key={a.id} appt={a} />)}
        </Panel>
      )}
    </div>
  );
}

function AppointmentRow({ appt }: { appt: Appointment }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '80px auto 1fr auto',
      gap: 12,
      padding: '8px 0',
      borderBottom: `1px solid ${T.borderDim}`,
      alignItems: 'center',
    }}>
      <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgDim }}>
        {fmtDate(appt.date)}
      </span>
      <span style={{
        fontFamily: T.mono, fontSize: 9.5, textTransform: 'uppercase',
        padding: '2px 6px', borderRadius: 3,
        border: `1px solid ${T.borderDim}`, color: T.blue,
        justifySelf: 'start',
      }}>
        {appt.type}
      </span>
      <div>
        <span style={{ color: T.fg, fontSize: 13.5 }}>{appt.name}</span>
        {appt.provider && (
          <span style={{ color: T.fgFaint, fontSize: 12, marginLeft: 8 }}>with {appt.provider}</span>
        )}
        {appt.prep && (
          <div style={{ color: T.fgDim, fontSize: 12, marginTop: 2, fontStyle: 'italic' }}>Prep: {appt.prep}</div>
        )}
      </div>
      <span style={{
        fontFamily: T.mono, fontSize: 9.5, textTransform: 'uppercase',
        color: appt.status === 'upcoming' ? T.mint : T.fgFaint,
      }}>
        {appt.status}
      </span>
    </div>
  );
}
