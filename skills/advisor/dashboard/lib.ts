import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { runSkill, gatewayConfigured } from '@/lib/skill-gateway';

const execFileAsync = promisify(execFile);

// ADVISOR_SKILL_ROOT: absolute path to the advisor skill directory (standalone mode)
// PROJECT_ROOT: absolute path to skillful-alhazen root (installed mode)
const SKILL_ROOT = process.env.ADVISOR_SKILL_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const ADVISOR_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'advisor.py')
  : path.join(PROJECT_ROOT, '.claude/skills/advisor/advisor.py');

// Working directory for uv run: the skill dir (standalone) or project root (installed)
const CWD = SKILL_ROOT || PROJECT_ROOT;

// Prefer the warm gateway (no per-request Python cold-start); fall back to
// spawning the CLI directly for host dev where no gateway is running.
async function runAdvisor(args: string[]): Promise<unknown> {
  if (gatewayConfigured()) return runSkill('advisor', args);
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', ADVISOR_SCRIPT, ...args],
    {
      cwd: CWD,
      env: { ...process.env, TYPEDB_DATABASE: 'alh_personal' },
      maxBuffer: 10 * 1024 * 1024,
    }
  );
  return JSON.parse(stdout);
}

// --- Decisions ---

export async function listDecisions(filters?: {
  status?: string;
  stakes?: string;
  reviewDue?: boolean;
  journal?: boolean;
}) {
  const args = ['list-decisions'];
  if (filters?.status) args.push('--status', filters.status);
  if (filters?.stakes) args.push('--stakes', filters.stakes);
  if (filters?.reviewDue) args.push('--review-due');
  if (filters?.journal) args.push('--journal');
  return runAdvisor(args);
}

export async function getDecision(id: string) {
  return runAdvisor(['show-decision', '--id', id]);
}

// --- Board roster ---

export async function listAdvisors(includeRetired?: boolean) {
  const args = ['list-advisors'];
  if (includeRetired) args.push('--include-retired');
  return runAdvisor(args);
}

// --- Journal ---

export async function listJournal() {
  return runAdvisor(['list-decisions', '--journal']);
}

// --- Context system ---

export async function listContext(kind?: string, full?: boolean) {
  const args = ['list-context'];
  if (kind) args.push('--kind', kind);
  if (full) args.push('--full');
  return runAdvisor(args);
}
