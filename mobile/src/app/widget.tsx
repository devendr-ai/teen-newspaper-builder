import { useState } from 'react';
import { Redirect, useLocalSearchParams } from 'expo-router';
import { intent } from '../widgets/core';
export default function WidgetLink() {
  const { edition, issue } = useLocalSearchParams();
  const [request] = useState(() => String(Date.now()));
  const target = intent(edition, issue);
  return <Redirect href={target ? { pathname: '/', params: { widget: target.edition, issue: target.date, request } } : '/'} />;
}
