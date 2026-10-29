import { isRunningInExpoGo } from 'expo';
import { File, Paths } from 'expo-file-system';
import { Platform } from 'react-native';
import { BASE, fileUri } from '../content';
import { EMPTY, parseFeed, propsFor, type Feed, type Props } from './core';

const PREFS = new File(Paths.document, 'question-widget.json');
const CACHE = new File(Paths.document, 'question-widget-feed.json');
export const TASK = 'newspebbles-question-widget';
export const available = !isRunningInExpoGo() && (Platform.OS === 'ios' || Platform.OS === 'android');
type Preferences = { on: boolean; edition: string };
export function preferences(): Preferences {
  try { const p = JSON.parse(PREFS.textSync()); return { on: p.on === true, edition: typeof p.edition === 'string' ? p.edition : 'breakfast-table' }; }
  catch { return { on: false, edition: 'breakfast-table' }; }
}
function store(file: File, value: object) { if (!file.exists) file.create(); file.writeSync(JSON.stringify(value)); }
export function feed(): Feed {
  for (const file of [CACHE, new File(fileUri('widgets.json'))]) {
    try { return parseFeed(JSON.parse(file.textSync())); } catch { /* keep last complete feed */ }
  }
  return { v: 1, editions: [] };
}
export function currentProps(): Props {
  const p = preferences();
  const e = p.on ? feed().editions.find(e => e.edition === p.edition) : undefined;
  return e ? propsFor(e) : EMPTY;
}
async function apply() { if (available) await (await import('./native')).apply(currentProps()); }
function adopt(next: Feed) {
  const before = feed();
  // A background refresh may be ahead of the app's downloaded newspaper pack.
  const editions = next.editions.map(e => {
    const old = before.editions.find(o => o.edition === e.edition);
    return old && old.date > e.date ? old : e;
  });
  store(CACHE, { v: 1, editions });
}
export async function syncFromPack() {
  try { adopt(parseFeed(JSON.parse(new File(fileUri('widgets.json')).textSync()))); } catch { /* retain cached question */ }
  await apply();
}
export async function refresh() {
  if (!available || !preferences().on) return;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(BASE + 'widgets.json', { credentials: 'omit', signal: controller.signal, headers: { Accept: 'application/json' } });
    if (!res.ok) throw new Error('Question update unavailable');
    const text = await res.text();
    if (text.length > 65536) throw new Error('Question feed too large');
    adopt(parseFeed(JSON.parse(text)));
    await apply();
  } finally { clearTimeout(timer); }
}
export function settings() {
  return { ...preferences(), available, editions: feed().editions.map(e => ({ id: e.edition, name: e.name })),
    platform: Platform.OS,
    note: available ? 'Shows the issue date. Refreshes when the app opens and when your phone allows background updates.' : 'Widgets need the installed development or store app; they are unavailable in Expo Go.' };
}
export async function save(on: boolean, edition: string) {
  if (!available) throw new Error('Widgets require the installed app.');
  if (on && !feed().editions.some(e => e.edition === edition)) throw new Error('Update your papers, then choose an edition.');
  store(PREFS, { on, edition });
  await apply(); // Switching off also clears an already-added widget.
  if (Platform.OS === 'ios') {
    const bg = await import('expo-background-task');
    const manager = await import('expo-task-manager');
    if (on) await bg.registerTaskAsync(TASK, { minimumInterval: 60 });
    else if (await manager.isTaskRegisteredAsync(TASK)) await bg.unregisterTaskAsync(TASK);
  }
  if (on) await refresh().catch(() => {}); // Offline setup still uses the downloaded issue.
}
