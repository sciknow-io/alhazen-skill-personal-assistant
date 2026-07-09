import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { runSkill, gatewayConfigured } from '@/lib/skill-gateway';

const execFileAsync = promisify(execFile);

// OPS_SKILL_ROOT: absolute path to the ops skill directory (used in standalone demo)
// PROJECT_ROOT: absolute path to skillful-alhazen root (used when installed)
const SKILL_ROOT = process.env.OPS_SKILL_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const OPS_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'ops.py')
  : path.join(PROJECT_ROOT, '.claude/skills/ops/ops.py');

// Working directory for uv run: the skill dir (standalone) or project root (installed)
const CWD = SKILL_ROOT || PROJECT_ROOT;

// Prefer the warm gateway (no per-request Python cold-start, and the dashboard
// container ships no uv/skill code); fall back to spawning the CLI directly for
// host dev where no gateway is running.
async function runOps(args: string[]): Promise<unknown> {
  if (gatewayConfigured()) return runSkill('ops', args);
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', OPS_SCRIPT, ...args],
    { cwd: CWD, maxBuffer: 10 * 1024 * 1024 }
  );
  return JSON.parse(stdout);
}

// ── Today ────────────────────────────────────────────────────────────────

export async function getToday() {
  return runOps(['today']);
}

// ── Brief specs & instances ──────────────────────────────────────────────

export async function listSpecs(status?: string) {
  const args = ['list-specs'];
  if (status) args.push('--status', status);
  return runOps(args);
}

export async function listBriefs(spec?: string, limit?: number) {
  const args = ['list-briefs'];
  if (spec) args.push('--spec', spec);
  if (limit !== undefined) args.push('--limit', String(limit));
  return runOps(args);
}

// ── Stakeholder CRM ──────────────────────────────────────────────────────

export async function listStakeholders() {
  return runOps(['list-stakeholders']);
}

export async function showStakeholder(personId: string) {
  return runOps(['show-stakeholder', '--person', personId]);
}

// ── Commitments ──────────────────────────────────────────────────────────

export async function listCommitments(filters?: {
  due?: string;
  owedBy?: string;
  status?: string;
  person?: string;
}) {
  const args = ['list-commitments'];
  if (filters?.due) args.push('--due', filters.due);
  if (filters?.owedBy) args.push('--owed-by', filters.owedBy);
  if (filters?.status) args.push('--status', filters.status);
  if (filters?.person) args.push('--person', filters.person);
  return runOps(args);
}

export async function updateCommitment(
  id: string,
  updates: { status?: string; due?: string }
) {
  const args = ['update-commitment', '--id', id];
  if (updates.status) args.push('--status', updates.status);
  if (updates.due) args.push('--due', updates.due);
  return runOps(args);
}

// ── Monitors ─────────────────────────────────────────────────────────────

export async function listMonitors(status?: string) {
  const args = ['list-monitors'];
  if (status) args.push('--status', status);
  return runOps(args);
}

// ── OKRs ─────────────────────────────────────────────────────────────────

export async function listObjectives(status?: string) {
  return runOps(['list-objectives', ...(status ? ['--status', status] : [])]);
}

export async function showObjectiveTree(objectiveId: string) {
  return runOps(['show-tree', '--objective', objectiveId]);
}
