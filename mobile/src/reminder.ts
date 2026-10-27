// The morning reminder: one local notification a day, set on the phone. No push server, no account.
import * as Notifications from 'expo-notifications';
import { File, Paths } from 'expo-file-system';

const SAVED = new File(Paths.document, 'reminder.json');
export type Reminder = { on: boolean; time: string };

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false }),
});

export function get(): Reminder {
  try {
    if (SAVED.exists) return JSON.parse(SAVED.textSync()) as Reminder;
  } catch {}
  return { on: false, time: '07:00' };
}

function save(r: Reminder) {
  if (!SAVED.exists) SAVED.create();
  SAVED.writeSync(JSON.stringify(r));
}

/** Turn the reminder on or off; asks for permission the first time. Returns what was actually set. */
export async function set(on: boolean, time: string): Promise<Reminder & { denied?: boolean }> {
  const [h, m] = (/^\d{1,2}:\d{2}$/.test(time) ? time : '07:00').split(':').map(Number);
  await Notifications.cancelAllScheduledNotificationsAsync();
  if (!on) {
    save({ on: false, time });
    return { on: false, time };
  }
  let { status } = await Notifications.getPermissionsAsync();
  if (status !== 'granted') ({ status } = await Notifications.requestPermissionsAsync());
  if (status !== 'granted') {
    save({ on: false, time });
    return { on: false, time, denied: true };
  }
  await Notifications.scheduleNotificationAsync({
    content: { title: 'News Pebbles', body: "Today's papers are ready." },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.DAILY, hour: h, minute: m },
  });
  save({ on: true, time });
  return { on: true, time };
}
