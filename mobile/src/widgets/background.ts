// Loaded before Router: headless launches must register their handlers too.
// Conditional require is necessary: Expo Go does not contain these native modules.
/* eslint-disable @typescript-eslint/no-require-imports */
import { isRunningInExpoGo } from 'expo';
import { Platform } from 'react-native';

if (!isRunningInExpoGo() && Platform.OS === 'android') {
  const { registerWidgetTaskHandler } = require('react-native-android-widget') as typeof import('react-native-android-widget');
  registerWidgetTaskHandler(async task => { await (await import('./native.android')).handle(task); });
}
if (!isRunningInExpoGo() && Platform.OS === 'ios') {
  const manager = require('expo-task-manager') as typeof import('expo-task-manager');
  const bg = require('expo-background-task') as typeof import('expo-background-task');
  if (!manager.isTaskDefined('newspebbles-question-widget')) manager.defineTask('newspebbles-question-widget', async () => {
    try { await (await import('./service')).refresh(); return bg.BackgroundTaskResult.Success; }
    catch { return bg.BackgroundTaskResult.Failed; }
  });
}
