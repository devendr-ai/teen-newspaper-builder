// The phone's own player for the car-ride brief and the Listen tab (assets/app/app.js sends the tracks).
// It keeps playing with the screen locked and shows on the lock screen, Control Center and in the car.
import { createAudioPlaylist, setAudioModeAsync, type AudioPlaylist, type AudioPlaylistStatus } from 'expo-audio';

export type Track = { src: string; title: string };
export type Status = {
  id: string; title: string; track: string; index: number; count: number;
  playing: boolean; time: number; duration: number; ended: boolean;
};
type Load = { id: string; title?: string; artist?: string; tracks: Track[]; at?: number; rate?: number };

let list: AudioPlaylist | null = null;
let now: (Load & { title: string }) | null = null;
let pendingSeek = 0;
let last: Status | null = null;
const listeners = new Set<(s: Status | null) => void>();

export async function setup() {
  await setAudioModeAsync({ playsInSilentMode: true, shouldPlayInBackground: true, interruptionMode: 'doNotMix' });
}

export function onStatus(fn: (s: Status | null) => void): () => void {
  listeners.add(fn);
  fn(last);
  return () => { listeners.delete(fn); };
}

export function current(): Status | null {
  return last;
}

function emit(s: Status | null) {
  last = s;
  listeners.forEach((fn) => fn(s));
}

function lockScreen(index: number) {
  if (!list || !now) return;
  list.updateLockScreenMetadata({ title: now.tracks[index]?.title || now.title, artist: now.title, albumTitle: 'News Pebbles' });
}

let shownIndex = -1;
function update(s: AudioPlaylistStatus) {
  if (!now) return;
  if (s.isLoaded && pendingSeek > 0) {
    const at = pendingSeek;
    pendingSeek = 0;
    list?.seekTo(at);
  }
  if (s.currentIndex !== shownIndex) {
    shownIndex = s.currentIndex;
    lockScreen(s.currentIndex);
  }
  const lastTrack = s.currentIndex >= now.tracks.length - 1;
  emit({
    id: now.id, title: now.title, track: now.tracks[s.currentIndex]?.title || '', index: s.currentIndex,
    count: now.tracks.length, playing: s.playing, time: s.currentTime, duration: s.duration,
    ended: s.didJustFinish && lastTrack,
  });
}

export function load(m: Load) {
  list?.destroy();
  now = { ...m, title: m.title || 'News Pebbles' };
  shownIndex = -1;
  pendingSeek = m.at && m.at > 1 ? m.at : 0;
  list = createAudioPlaylist({ sources: m.tracks.map((t) => ({ uri: t.src })), updateInterval: 400 });
  list.addListener('playlistStatusUpdate', update);
  if (m.rate) list.playbackRate = m.rate;
  const several = m.tracks.length > 1;
  list.setActiveForLockScreen(
    true,
    { title: m.tracks[0]?.title || now.title, artist: now.title, albumTitle: 'News Pebbles' },
    { showNextTrack: several, showPreviousTrack: several, showSeekForward: !several, showSeekBackward: !several },
  );
  list.play();
}

export function play() { list?.play(); }
export function pause() { list?.pause(); }
export function toggle() { if (list) { if (list.playing) list.pause(); else list.play(); } }
export function next() { list?.next(); }
export function seek(at: number) { list?.seekTo(Math.max(0, at)); }
export function rate(r: number) { if (list) list.playbackRate = r; }

export function stop() {
  list?.clearLockScreenControls();
  list?.destroy();
  list = null;
  now = null;
  emit(null);
}

/** A message from a page: {t: "audio", op, ...} (assets/app/app.js). */
export function handle(m: { op: string; id?: string; at?: number; rate?: number } & Partial<Load>) {
  switch (m.op) {
    case 'list': if (m.id && m.tracks?.length) load(m as Load); break;
    case 'play': play(); break;
    case 'pause': pause(); break;
    case 'toggle': toggle(); break;
    case 'next': next(); break;
    case 'seek': if (typeof m.at === 'number') seek(m.at); break;
    case 'rate': if (typeof m.rate === 'number') rate(m.rate); break;
    case 'stop': stop(); break;
  }
}
