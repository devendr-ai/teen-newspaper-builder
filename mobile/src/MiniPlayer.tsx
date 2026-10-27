// What's playing, above the pages' own tab bar, on every page that doesn't show its own player.
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { Status } from './player';

type Props = { status: Status; bottom: number; onOpen: () => void; onToggle: () => void; onNext: () => void; onClose: () => void };

export function MiniPlayer({ status, bottom, onOpen, onToggle, onNext, onClose }: Props) {
  const pct = status.duration ? Math.min(100, (100 * status.time) / status.duration) : 0;
  return (
    <View style={[styles.box, { bottom }]}>
      <Pressable style={styles.what} onPress={onOpen} accessibilityRole="button" accessibilityLabel={`Open Listen. Now playing ${status.title}`}>
        <Text style={styles.icon}>🎧</Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.title} numberOfLines={1}>{status.title}</Text>
          <Text style={styles.track} numberOfLines={1}>{status.track}</Text>
        </View>
      </Pressable>
      <Pressable onPress={onToggle} hitSlop={10} style={styles.button} accessibilityRole="button" accessibilityLabel={status.playing ? 'Pause' : 'Play'}>
        <Text style={styles.buttonText}>{status.playing ? '❚❚' : '▶'}</Text>
      </Pressable>
      {status.count > 1 && (
        <Pressable onPress={onNext} hitSlop={10} style={styles.button} accessibilityRole="button" accessibilityLabel="Next story">
          <Text style={styles.buttonText}>⏭</Text>
        </Pressable>
      )}
      {!status.playing && (
        <Pressable onPress={onClose} hitSlop={10} style={styles.button} accessibilityRole="button" accessibilityLabel="Close the player">
          <Text style={styles.buttonText}>✕</Text>
        </Pressable>
      )}
      <View style={styles.bar}><View style={[styles.fill, { width: `${pct}%` }]} /></View>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    position: 'absolute', left: 10, right: 10, flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#1E2A32', borderRadius: 18, paddingLeft: 12, paddingRight: 6, paddingTop: 8, paddingBottom: 12,
    shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 12, shadowOffset: { width: 0, height: 6 },
  },
  what: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 44 },
  icon: { fontSize: 22 },
  title: { color: '#fff', fontWeight: '700', fontSize: 15 },
  track: { color: '#fff', opacity: 0.75, fontSize: 13 },
  button: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  buttonText: { color: '#fff', fontSize: 18 },
  bar: { position: 'absolute', left: 14, right: 14, bottom: 5, height: 3, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.25)' },
  fill: { height: 3, borderRadius: 2, backgroundColor: '#fff' },
});
