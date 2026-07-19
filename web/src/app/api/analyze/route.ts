import { spawn } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

/** Live analysis.
 *
 *  Runs the real model. The uploaded determinant profile is passed to pipeline/serve_model.py,
 *  which loads the same cached models the validation report describes and returns a genuine
 *  prediction — including the abstention gates. Nothing here is looked up from a precomputed
 *  table.
 *
 *  This shells out to Python because that is where the model lives. A hosted deployment would
 *  put the same script behind a small inference service rather than a subprocess; the contract
 *  is identical either way.
 */

const REPO = join(process.cwd(), "..");
const SCRIPT = join(REPO, "pipeline", "serve_model.py");
const TIMEOUT_MS = 30_000;

function runPython(profilePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn("python3", [SCRIPT, "--predict", profilePath], {
      cwd: REPO,
      env: { ...process.env, OMP_NUM_THREADS: "2", PYTHONWARNINGS: "ignore" },
    });
    let out = "";
    let err = "";
    const timer = setTimeout(() => {
      proc.kill();
      reject(new Error("analysis timed out"));
    }, TIMEOUT_MS);

    proc.stdout.on("data", (d) => (out += d));
    proc.stderr.on("data", (d) => (err += d));
    proc.on("error", (e) => {
      clearTimeout(timer);
      reject(e);
    });
    proc.on("close", (code) => {
      clearTimeout(timer);
      if (code === 0 && out.trim()) resolve(out);
      else reject(new Error(err.slice(-400) || `exited ${code}`));
    });
  });
}

export async function POST(request: Request) {
  let dir: string | null = null;
  try {
    const profile = await request.json();
    if (!profile || !Array.isArray(profile.determinants)) {
      return Response.json(
        { error: "Expected a JSON profile with a `determinants` array." },
        { status: 400 },
      );
    }

    dir = await mkdtemp(join(tmpdir(), "gf-"));
    const path = join(dir, "profile.json");
    await writeFile(path, JSON.stringify(profile));

    const started = Date.now();
    const raw = await runPython(path);
    const result = JSON.parse(raw);
    result.elapsedMs = Date.now() - started;
    return Response.json(result);
  } catch (e) {
    const message = e instanceof Error ? e.message : "analysis failed";
    return Response.json({ error: message }, { status: 500 });
  } finally {
    if (dir) await rm(dir, { recursive: true, force: true }).catch(() => {});
  }
}
