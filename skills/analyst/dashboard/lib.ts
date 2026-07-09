import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { runSkill, gatewayConfigured } from '@/lib/skill-gateway';

const execFileAsync = promisify(execFile);

// ANALYST_SKILL_ROOT: absolute path to the analyst skill directory (used in standalone demo)
// PROJECT_ROOT: absolute path to skillful-alhazen root (used when installed)
const SKILL_ROOT = process.env.ANALYST_SKILL_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const ANALYST_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'analyst.py')
  : path.join(PROJECT_ROOT, '.claude/skills/analyst/analyst.py');

// Working directory for uv run: the skill dir (standalone) or project root (installed)
const CWD = SKILL_ROOT || PROJECT_ROOT;

// Prefer the warm gateway (no per-request Python cold-start, and the dashboard
// container ships no uv/skill code); fall back to spawning the CLI directly for
// host dev where no gateway is running.
async function runAnalyst(args: string[]): Promise<unknown> {
  if (gatewayConfigured()) return runSkill('analyst', args);
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', ANALYST_SCRIPT, ...args],
    { cwd: CWD, maxBuffer: 10 * 1024 * 1024 }
  );
  return JSON.parse(stdout);
}

export async function listMissions(status?: string) {
  const args = ['list-missions'];
  if (status) args.push('--status', status);
  return runAnalyst(args);
}

export async function getMission(id: string) {
  return runAnalyst(['show-mission', '--id', id]);
}

export async function updateMission(
  id: string,
  updates: { status?: string; priority?: string }
) {
  const args = ['update-mission', '--id', id];
  if (updates.status) args.push('--status', updates.status);
  if (updates.priority) args.push('--priority', updates.priority);
  return runAnalyst(args);
}

export async function listFindings(filters?: {
  mission?: string;
  divergent?: boolean;
  unverified?: boolean;
}) {
  const args = ['list-findings'];
  if (filters?.mission) args.push('--mission', filters.mission);
  if (filters?.divergent) args.push('--divergent');
  if (filters?.unverified) args.push('--unverified');
  return runAnalyst(args);
}

export async function verifyFinding(
  findingId: string,
  status: 'confirmed' | 'refuted' | 'needs-work',
  content?: string
) {
  const args = ['verify-finding', '--finding', findingId, '--status', status];
  if (content) args.push('--content', content);
  return runAnalyst(args);
}

export async function recordGate(
  missionId: string,
  gate: { grounded: string; missing: string; nameOnIt: string; passed: boolean }
) {
  const args = [
    'record-gate',
    '--mission', missionId,
    '--grounded', gate.grounded,
    '--missing', gate.missing,
    '--name-on-it', gate.nameOnIt,
    gate.passed ? '--passed' : '--failed',
  ];
  return runAnalyst(args);
}

export async function runAudit(severity?: string) {
  const args = ['audit'];
  if (severity) args.push('--severity', severity);
  return runAnalyst(args);
}
