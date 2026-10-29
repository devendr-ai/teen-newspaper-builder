import { FlexWidget, TextWidget, requestWidgetUpdate, type WidgetTaskHandlerProps } from 'react-native-android-widget';
import { EMPTY, type Props } from './core';

export function Question({ data = EMPTY, dark = false }: { data?: Props; dark?: boolean }) {
  const ink = dark ? '#F4F1EA' : '#1E2A32';
  return <FlexWidget style={{ flex: 1, padding: 14, backgroundColor: dark ? '#182226' : '#F4F1EA', borderRadius: 18 }} clickAction="OPEN_URI" clickActionData={{ uri: data.url }}>
    <TextWidget text="🦉 A QUESTION TO SHARE" style={{ fontSize: 12, fontWeight: 'bold', color: ink }} maxLines={1} />
    <TextWidget text={data.question} style={{ fontSize: 16, fontWeight: 'bold', color: ink, marginTop: 8 }} maxLines={4} truncate="END" />
    <TextWidget text={data.edition + (data.date ? ' · ' + data.date : '')} style={{ fontSize: 11, color: ink, marginTop: 8 }} maxLines={1} />
    <TextWidget text={'▶ ' + data.action} style={{ fontSize: 12, color: ink, marginTop: 5 }} maxLines={1} />
  </FlexWidget>;
}
export async function apply(data: Props) {
  await requestWidgetUpdate({ widgetName: 'NewsPebblesQuestion', renderWidget: () => ({ light: <Question data={data} />, dark: <Question data={data} dark /> }) });
}
export async function handle(task: WidgetTaskHandlerProps) {
  if (task.widgetInfo.widgetName !== 'NewsPebblesQuestion' || task.widgetAction === 'WIDGET_DELETED') return;
  const { refresh, currentProps } = await import('./service');
  await refresh().catch(() => {});
  task.renderWidget({ light: <Question data={currentProps()} />, dark: <Question data={currentProps()} dark /> });
}
