import { Text, VStack } from '@expo/ui/swift-ui';
import { font, foregroundStyle, lineLimit, widgetURL } from '@expo/ui/swift-ui/modifiers';
import { createWidget, type WidgetEnvironment } from 'expo-widgets';
import { EMPTY, type Props } from './core';

const Question = (props: Props, environment: WidgetEnvironment) => {
  'widget';
  const lock = environment.widgetFamily === 'accessoryRectangular';
  const ink = environment.widgetRenderingMode === 'vibrant' ? { type: 'hierarchical' as const, style: 'primary' as const } : environment.colorScheme === 'dark' ? '#F4F1EA' : '#1E2A32';
  return <VStack alignment="leading" spacing={lock ? 2 : 5} modifiers={[widgetURL(props.url)]}>
    <Text modifiers={[font({ size: lock ? 11 : 12, weight: 'bold' }), foregroundStyle(ink), lineLimit(1)]}>🦉 {lock ? 'News Pebbles' : 'A QUESTION TO SHARE'}</Text>
    <Text modifiers={[font({ size: lock ? 12 : 16, weight: 'semibold' }), foregroundStyle(ink), lineLimit(lock ? 2 : 4)]}>{lock ? props.short : props.question}</Text>
    <Text modifiers={[font({ size: 10 }), foregroundStyle(ink), lineLimit(1)]}>{lock ? props.date : props.edition + (props.date ? ' · ' + props.date : '')}</Text>
    {!lock && <Text modifiers={[font({ size: 11 }), foregroundStyle(ink), lineLimit(1)]}>▶ {props.action}</Text>}
  </VStack>;
};
const home = createWidget<Props>('NewsPebblesQuestion', Question, EMPTY);
const lock = createWidget<Props>('NewsPebblesLockQuestion', Question, EMPTY);
export async function apply(props: Props) { home.updateSnapshot(props); lock.updateSnapshot(props); }
