import type { FC } from 'react';
import { Play, Pause } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface VideoControlsProps {
  isPlaying: boolean;
  onTogglePlay: () => void;
}

export const VideoControls: FC<VideoControlsProps> = ({ isPlaying, onTogglePlay }) => {
  const { t } = useTranslation();

  return (
    <div className="absolute inset-x-0 bottom-0 py-4 bg-gradient-to-t from-background/90 to-transparent flex items-center justify-center">
      <button
        type="button"
        onClick={onTogglePlay}
        aria-label={isPlaying ? t('common.actions.pause') : t('common.actions.play')}
        className="w-11 h-11 rounded-full bg-foreground/15 backdrop-blur-md border border-border flex items-center justify-center hover:scale-110 active:scale-95 transition-transform focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        {isPlaying ? (
          <Pause className="w-5 h-5 text-foreground fill-current" aria-hidden="true" />
        ) : (
          <Play className="w-5 h-5 text-foreground fill-current ml-0.5" aria-hidden="true" />
        )}
      </button>
    </div>
  );
};
