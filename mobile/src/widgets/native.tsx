// Fallback for platforms without widgets. Keep it .tsx like native.ios.tsx and native.android.tsx:
// Metro tries every platform variant of one extension before the next, so a native.ts here would
// shadow native.ios.tsx and the widget would never get its question.
import type { Props } from './core';
export async function apply(_props: Props): Promise<void> {}
