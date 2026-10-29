// Pure data/route rules, shared by foreground, background and tests. No native imports.
export type Edition = { edition: string; name: string; date: string; question: string; reader: string; brief: string | null };
export type Feed = { v: 1; editions: Edition[] };
export type Props = { question: string; short: string; edition: string; date: string; action: string; url: string };
export const EMPTY: Props = { question: 'Choose a paper in For parents to see an issue-based question.', short: 'Choose a paper in For parents.', edition: 'News Pebbles', date: '', action: 'Open News Pebbles', url: 'newspebbles:///' };
export function validDate(value: unknown): value is string {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}
export function intent(edition: unknown, date: unknown): { edition: string; date: string; reader: string } | null {
  if (typeof edition !== 'string' || !/^[a-z][a-z0-9-]{0,60}$/.test(edition) || !validDate(date)) return null;
  return { edition, date, reader: `play/${edition}/${date}.html` };
}
export function parseFeed(data: unknown): Feed {
  const d = data as Partial<Feed>;
  if (!d || d.v !== 1 || !Array.isArray(d.editions) || d.editions.length > 50) throw new Error('Invalid widget feed');
  const seen = new Set();
  for (const e of d.editions) {
    const route = intent(e.edition, e.date);
    if (!route || e.reader !== route.reader || seen.has(e.edition) || typeof e.name !== 'string' || !e.name || e.name.length > 100 || typeof e.question !== 'string' || e.question.length < 8 || e.question.length > 240 || !e.question.endsWith('?') || /[<>\x00-\x1f]/.test(e.question) || (e.brief !== null && e.brief !== `play/briefs/${e.date}.json`)) throw new Error('Invalid widget edition');
    seen.add(e.edition);
  }
  return d as Feed;
}
export function propsFor(e: Edition): Props {
  const short = e.question.length <= 82 ? e.question : e.question.slice(0, 79).replace(/\s+\S*$/, '') + '…';
  return { question: e.question, short, edition: e.name, date: e.date, action: e.brief ? 'Open brief or story' : 'Open this story', url: `newspebbles:///widget?edition=${e.edition}&issue=${e.date}` };
}
export function audioPath(data: unknown, edition: string, date: string): string | null {
  const d = data as { paper?: string; date?: string; audio?: string };
  if (d?.paper !== edition || d.date !== date || typeof d.audio !== 'string' || !/^audio\/[a-zA-Z0-9_-]+\.mp3$/.test(d.audio)) return null;
  return 'play/' + d.audio;
}
