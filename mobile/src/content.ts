// The papers on this phone: the app pack from <site>/app/ (ygc/apppack.py), kept in the app's cache folder.
// Each sync downloads manifest.json, fetches only the files whose hash changed (or that iOS cleared to save
// space) and deletes the ones that are gone. Everything the WebView shows comes from these files.
import { Directory, File, Paths } from 'expo-file-system';

export const BASE = 'https://newspebbles.com/app/';
const ROOT = new Directory(Paths.cache, 'site');
const INDEX = new File(Paths.document, 'pack.json');
const PARALLEL = 6;

type Entry = [hash: string, size: number];
type Manifest = { v: number; id: string; built: string; start: string; files: Record<string, Entry> };
export type Pack = { id: string; built: string; start: string; files: Record<string, Entry>; synced: number };
export type Progress = { done: number; total: number };

export const rootUri = ROOT.uri;

export function fileUri(rel: string): string {
  return new File(ROOT, rel).uri;
}

export function local(): Pack | null {
  try {
    if (!INDEX.exists) return null;
    const pack = JSON.parse(INDEX.textSync()) as Pack;
    return new File(ROOT, pack.start).exists ? pack : null;
  } catch {
    return null;
  }
}

export function bytes(pack: Pack | null): number {
  return pack ? Object.values(pack.files).reduce((n, [, size]) => n + size, 0) : 0;
}

function safe(rel: string): boolean {
  return !!rel && !rel.startsWith('/') && !rel.split('/').some((part) => part === '..' || part === '');
}

let running: Promise<Pack> | null = null;

/** Bring the phone's papers up to date. Concurrent calls share one run. */
export function sync(onProgress?: (p: Progress) => void): Promise<Pack> {
  if (!running) running = run(onProgress).finally(() => { running = null; });
  return running;
}

async function run(onProgress?: (p: Progress) => void): Promise<Pack> {
  const res = await fetch(BASE + 'manifest.json?t=' + Date.now(), { cache: 'no-store' });
  if (!res.ok) throw new Error(`manifest: HTTP ${res.status}`);
  const m = (await res.json()) as Manifest;
  if (m.v !== 1 || !m.files || !m.files[m.start]) throw new Error('manifest: not an app pack');
  const before = local()?.files ?? readFiles();
  const todo = Object.keys(m.files).filter((rel) => {
    if (!safe(rel)) return false;
    return before[rel]?.[0] !== m.files[rel][0] || !new File(ROOT, rel).exists;
  });
  let done = 0;
  onProgress?.({ done, total: todo.length });
  const queue = todo.slice();
  async function worker() {
    for (let rel = queue.shift(); rel; rel = queue.shift()) {
      const target = new File(ROOT, rel);
      target.parentDirectory.create({ intermediates: true, idempotent: true });
      const url = BASE + rel.split('/').map(encodeURIComponent).join('/');
      const got = await File.downloadFileAsync(url, target, { idempotent: true });
      if (got.size !== m.files[rel][1]) throw new Error(`download: ${rel} is incomplete`);
      onProgress?.({ done: ++done, total: todo.length });
    }
  }
  await Promise.all(Array.from({ length: Math.min(PARALLEL, todo.length) }, worker));
  const pack: Pack = { id: m.id, built: m.built, start: m.start, files: m.files, synced: Date.now() };
  if (!INDEX.exists) INDEX.create();
  INDEX.writeSync(JSON.stringify(pack));
  for (const rel of Object.keys(before)) {                 // yesterday's files that the pack no longer has
    if (!m.files[rel] && safe(rel)) {
      const old = new File(ROOT, rel);
      if (old.exists) old.delete();
    }
  }
  return pack;
}

function readFiles(): Record<string, Entry> {
  try {
    return INDEX.exists ? (JSON.parse(INDEX.textSync()) as Pack).files : {};
  } catch {
    return {};
  }
}
