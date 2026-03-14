import { lazy } from 'react';

export const ThreeCanvas = lazy(() => import('../components/ThreeCanvas'));
export const Editor = lazy(() =>
  import('../components/Editor').then((module) => ({ default: module.Editor })),
);
export const AutoCutEditor = lazy(() =>
  import('../components/AutoCutEditor').then((module) => ({ default: module.AutoCutEditor })),
);
export const SubtitleEditor = lazy(() =>
  import('../components/SubtitleEditor').then((module) => ({ default: module.SubtitleEditor })),
);
