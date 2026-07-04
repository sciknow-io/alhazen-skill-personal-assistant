import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { runSkill, gatewayConfigured } from '@/lib/skill-gateway';

const execFileAsync = promisify(execFile);

// CHIEF_SKILL_ROOT: absolute path to the chief-of-staff skill directory (standalone demo)
// PROJECT_ROOT: absolute path to skillful-alhazen root (installed)
const SKILL_ROOT = process.env.CHIEF_SKILL_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const CHIEF_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'chief_of_staff.py')
  : path.join(PROJECT_ROOT, '.claude/skills/chief-of-staff/chief_of_staff.py');

const CWD = SKILL_ROOT || PROJECT_ROOT;

async function runChief(args: string[]): Promise<unknown> {
  if (gatewayConfigured()) return runSkill('chief-of-staff', args);
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', CHIEF_SCRIPT, ...args],
    { cwd: CWD, maxBuffer: 10 * 1024 * 1024 }
  );
  return JSON.parse(stdout);
}

export async function getDailyAgenda() {
  return runChief(['daily-agenda']);
}

export async function getWeeklyReview() {
  return runChief(['weekly-review']);
}
