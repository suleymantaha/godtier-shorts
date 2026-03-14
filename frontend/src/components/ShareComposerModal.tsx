import type { Clip } from '../types';
import { ShareComposerLayout } from './shareComposer/sections';
import { useShareComposerController } from './shareComposer/useShareComposerController';

interface ShareComposerModalProps {
  clip: Clip | null;
  open: boolean;
  onClose: () => void;
}

export function ShareComposerModal({ clip, open, onClose }: ShareComposerModalProps) {
  const controller = useShareComposerController({ clip, open });

  if (!open || !clip) {
    return null;
  }

  return <ShareComposerLayout clip={clip} controller={controller} onClose={onClose} />;
}
