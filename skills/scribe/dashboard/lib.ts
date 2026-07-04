import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { runSkill, gatewayConfigured } from '@/lib/skill-gateway';

const execFileAsync = promisify(execFile);

// SCRIBE_SKILL_ROOT: absolute path to the scribe skill directory (used in standalone demo)
// PROJECT_ROOT: absolute path to skillful-alhazen root (used when installed)
const SKILL_ROOT = process.env.SCRIBE_SKILL_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const SCRIBE_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'scribe.py')
  : path.join(PROJECT_ROOT, '.claude/skills/scribe/scribe.py');

// Working directory for uv run: the skill dir (standalone) or project root (installed)
const CWD = SKILL_ROOT || PROJECT_ROOT;

// Prefer the warm gateway (no per-request Python cold-start, and the dashboard
// container ships no uv/skill code); fall back to spawning the CLI directly for
// host dev where no gateway is running.
async function runScribe(args: string[]): Promise<unknown> {
  if (gatewayConfigured()) return runSkill('scribe', args);
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', SCRIBE_SCRIPT, ...args],
    { cwd: CWD, maxBuffer: 10 * 1024 * 1024 }
  );
  return JSON.parse(stdout);
}

export async function listPieces(filters?: { status?: string; type?: string }) {
  const args = ['list-pieces'];
  if (filters?.status) args.push('--status', filters.status);
  if (filters?.type) args.push('--type', filters.type);
  return runScribe(args);
}

export async function getPiece(id: string) {
  return runScribe(['show-piece', '--id', id]);
}

export async function updatePiece(
  id: string,
  updates: { status?: string; goal?: string; deadline?: string }
) {
  const args = ['update-piece', '--id', id];
  if (updates.status) args.push('--status', updates.status);
  if (updates.goal) args.push('--goal', updates.goal);
  if (updates.deadline) args.push('--deadline', updates.deadline);
  return runScribe(args);
}

export async function listPersonas() {
  return runScribe(['list-personas']);
}

export async function showProfile(id?: string) {
  const args = ['show-profile'];
  if (id) args.push('--id', id);
  return runScribe(args);
}

export async function listSamples(filters?: { kind?: string; docType?: string }) {
  const args = ['list-samples'];
  if (filters?.kind) args.push('--kind', filters.kind);
  if (filters?.docType) args.push('--doc-type', filters.docType);
  return runScribe(args);
}
