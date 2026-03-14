import type { Clip } from '../types';
import { SubtitleEditorLayout } from './subtitleEditor/sections';
import { useSubtitleEditorController } from './subtitleEditor/useSubtitleEditorController';

export interface SubtitleEditorProps {
  lockedToClip?: boolean;
  targetClip?: Clip | null;
}

export function SubtitleEditor({ lockedToClip = false, targetClip = null }: SubtitleEditorProps) {
  const controller = useSubtitleEditorController({ lockedToClip, targetClip });

  return <SubtitleEditorLayout controller={controller} />;
}
