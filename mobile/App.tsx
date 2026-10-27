// News Pebbles for iPhone and iPad: the website's own pages (the app build, saved on the phone),
// plus what only an app can do: offline papers, audio with the screen locked, a morning reminder, and the
// phone's print and share sheets after the Parental Gate. See docs/APP_BUILD.md.
import { useCallback, useEffect, useRef, useState, type ComponentRef } from 'react';
import { ActivityIndicator, AppState, Linking, Pressable, Share, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { File, Paths } from 'expo-file-system';
import * as Print from 'expo-print';
import { WebView, type WebViewMessageEvent } from 'react-native-webview';
import type { ShouldStartLoadRequest } from 'react-native-webview/lib/WebViewTypes';

import * as content from './src/content';
import * as player from './src/player';
import * as reminder from './src/reminder';
import { MiniPlayer } from './src/MiniPlayer';

const PAPER = '#F4F1EA';
const STALE = 30 * 60 * 1000;                   // check for new papers when the app comes back after this long

export default function App() {
  return (
    <SafeAreaProvider>
      <Main />
    </SafeAreaProvider>
  );
}

type Phase = { kind: 'loading'; done: number; total: number } | { kind: 'failed' } | { kind: 'ready' };

function Main() {
  const insets = useSafeAreaInsets();
  const web = useRef<ComponentRef<typeof WebView>>(null);
  const [phase, setPhase] = useState<Phase>({ kind: 'loading', done: 0, total: 0 });
  const [start, setStart] = useState<string | null>(null);
  const [pack, setPack] = useState<content.Pack | null>(null);
  const [updating, setUpdating] = useState(false);
  const [page, setPage] = useState({ url: '', bg: PAPER, dark: false });
  const [claimed, setClaimed] = useState<string | null>(null);
  const [status, setStatus] = useState<player.Status | null>(null);
  const [denied, setDenied] = useState(false);

  const send = useCallback((m: object) => {
    web.current?.injectJavaScript(`window.__np && window.__np(${JSON.stringify(m)}); true;`);
  }, []);

  const refresh = useCallback(async (first: boolean) => {
    setUpdating(true);
    try {
      const before = content.local()?.id;
      const got = await content.sync(first ? (p) => setPhase({ kind: 'loading', ...p }) : undefined);
      setPack(got);
      if (first) { setStart(content.fileUri(got.start)); setPhase({ kind: 'ready' }); }
      else if (got.id !== before && /\/index\.html$/.test(page.url)) web.current?.reload();   // new papers on a front page
    } catch {
      if (first) setPhase({ kind: 'failed' });
    } finally {
      setUpdating(false);
    }
  }, [page.url]);

  useEffect(() => {
    player.setup().catch(() => {});
    const saved = content.local();
    if (saved) {
      setPack(saved);
      setStart(content.fileUri(saved.start));
      setPhase({ kind: 'ready' });
      refresh(false);
    } else refresh(true);
    return player.onStatus(setStatus);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (s) => {
      const p = content.local();
      if (s === 'active' && p && Date.now() - p.synced > STALE) refresh(false);
    });
    return () => sub.remove();
  }, [refresh]);

  useEffect(() => { if (phase.kind === 'ready') send({ t: 'status', s: status }); }, [status, phase.kind, send]);

  const settings = useCallback(() => {
    const mb = Math.round(content.bytes(pack) / 1e6);
    const when = pack ? new Date(pack.synced).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '';
    send({
      t: 'settings',
      reminder: reminder.get(),
      offline: {
        state: updating ? 'Updating…' : pack ? '✓ Up to date' : '',
        what: `Papers and audio from the last 7 days${mb ? ` · ${mb} MB` : ''}`,
        note: denied
          ? 'To get the reminder, allow notifications for News Pebbles in the iPhone’s Settings.'
          : `Updated ${when}. New papers download when the app opens.`,
      },
    });
  }, [pack, updating, denied, send]);

  useEffect(() => { if (/\/parents\.html$/.test(page.url)) settings(); }, [settings, page.url]);

  const onMessage = useCallback(async (e: WebViewMessageEvent) => {
    let m: any;
    try { m = JSON.parse(e.nativeEvent.data); } catch { return; }
    switch (m.t) {
      case 'page':
        setPage({ url: m.url, bg: m.bg || PAPER, dark: !!m.dark || isDark(m.bg) });
        setClaimed(null);
        break;
      case 'claim': setClaimed(m.id); break;
      case 'status?': send({ t: 'status', s: player.current() }); break;
      case 'audio': player.handle(m); break;
      case 'print':
        try { await Print.printAsync({ uri: m.url }); } catch {}
        break;
      case 'printHtml':
        try {
          await Print.printAsync({ html: m.html, orientation: m.landscape ? Print.Orientation.landscape : Print.Orientation.portrait });
        } catch {}
        break;
      case 'pdfData':                         // a paper made with Design your own: print, save to Files or send
        try {
          const name = String(m.name || 'News Pebbles.pdf').replace(/[^\w .()-]/g, '_');
          const file = new File(Paths.cache, name.endsWith('.pdf') ? name : name + '.pdf');
          if (file.exists) file.delete();
          file.create();
          file.writeSync(String(m.data || ''), { encoding: 'base64' });
          await Share.share({ url: file.uri });
        } catch {}
        break;
      case 'share':
        try { await Share.share({ title: m.title, message: [m.text, m.url].filter(Boolean).join(' '), url: m.url || undefined }); } catch {}
        break;
      case 'settings?': settings(); break;
      case 'reminder': {
        const r = await reminder.set(!!m.on, String(m.time || '07:00'));
        setDenied(!!r.denied);
        settings();
        break;
      }
    }
  }, [send, settings]);

  // Pages come from the phone; anything else (links out, email) opens outside the app, after the gate.
  const onLoad = useCallback((req: ShouldStartLoadRequest) => {
    if (/^(file|about|data|blob):/.test(req.url)) return true;
    Linking.openURL(req.url).catch(() => {});
    return false;
  }, []);

  if (phase.kind !== 'ready' || !start) {
    return (
      <View style={[styles.center, { paddingTop: insets.top, paddingBottom: insets.bottom }]}>
        <StatusBar style="dark" />
        <Text style={styles.title}>News <Text style={{ color: '#E2584D' }}>Pebbles</Text></Text>
        {phase.kind === 'failed' ? (
          <>
            <Text style={styles.note}>Connect to the internet once to get today’s papers. After that they work offline.</Text>
            <Pressable style={styles.button} onPress={() => { setPhase({ kind: 'loading', done: 0, total: 0 }); refresh(true); }}>
              <Text style={styles.buttonText}>Try again</Text>
            </Pressable>
          </>
        ) : (
          <>
            <ActivityIndicator size="large" color="#007C89" style={{ marginTop: 24 }} />
            <Text style={styles.note}>
              {phase.kind === 'loading' && phase.total
                ? `Getting today’s papers… ${Math.round((100 * phase.done) / phase.total)}%`
                : 'Getting today’s papers…'}
            </Text>
          </>
        )}
      </View>
    );
  }

  const pdf = /\.pdf(\?|#|$)/i.test(page.url);
  const showMini = !!status && claimed !== '*' && claimed !== status.id;
  return (
    <View style={[styles.fill, { backgroundColor: page.bg }]}>
      <StatusBar style={page.dark ? 'light' : 'dark'} />
      <View style={{ height: insets.top, backgroundColor: page.bg }} />
      {pdf && (
        <View style={styles.pdfBar}>
          <Pressable onPress={() => web.current?.goBack()} hitSlop={12} accessibilityRole="button">
            <Text style={styles.back}>‹ Back</Text>
          </Pressable>
        </View>
      )}
      <WebView
        ref={web}
        style={[styles.fill, { backgroundColor: page.bg }]}
        source={{ uri: start }}
        originWhitelist={['*']}
        allowingReadAccessToURL={content.rootUri}
        allowFileAccess
        allowFileAccessFromFileURLs
        allowUniversalAccessFromFileURLs
        allowsBackForwardNavigationGestures
        allowsInlineMediaPlayback
        mediaPlaybackRequiresUserAction={false}
        setSupportMultipleWindows={false}
        contentInsetAdjustmentBehavior="never"
        onShouldStartLoadWithRequest={onLoad}
        onNavigationStateChange={(n) => { if (/\.pdf(\?|#|$)/i.test(n.url)) setPage((p) => ({ ...p, url: n.url })); }}
        onMessage={onMessage}
        onContentProcessDidTerminate={() => web.current?.reload()}
      />
      {showMini && status && (
        <MiniPlayer
          status={status}
          bottom={insets.bottom + 84}
          onOpen={() => send({ t: 'go', href: 'play/listen.html' })}
          onToggle={player.toggle}
          onNext={player.next}
          onClose={player.stop}
        />
      )}
    </View>
  );
}

function isDark(color?: string): boolean {
  const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(color || '');
  return !!m && 0.299 * +m[1] + 0.587 * +m[2] + 0.114 * +m[3] < 110;
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: PAPER, padding: 32 },
  title: { fontSize: 34, fontWeight: '800', color: '#1E2A32' },
  note: { marginTop: 16, fontSize: 17, lineHeight: 24, color: '#5B6870', textAlign: 'center' },
  button: { marginTop: 22, backgroundColor: '#E2584D', borderRadius: 14, paddingVertical: 14, paddingHorizontal: 28 },
  buttonText: { color: '#fff', fontSize: 17, fontWeight: '700' },
  pdfBar: { paddingHorizontal: 16, paddingVertical: 10, backgroundColor: PAPER, borderBottomWidth: 1, borderBottomColor: '#DDD5C6' },
  back: { fontSize: 17, fontWeight: '600', color: '#007C89' },
});
