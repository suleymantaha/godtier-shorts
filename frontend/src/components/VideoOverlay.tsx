import { useCallback, useMemo, type KeyboardEvent, type MouseEvent, type TouchEvent } from 'react';
import type { Segment } from '../types';
import { SUBTITLE_STYLES, type StyleName } from '../config/subtitleStyles';
import {
  buildCropGuideStyle,
  findCurrentSubtitle,
  getCropFromClientX,
  getNextCropValue,
} from './videoOverlay/helpers';

interface VideoOverlayProps {
    currentTime: number;
    transcript: Segment[];
    style: StyleName;
    centerX: number;
    onCropChange: (x: number) => void;
}

export function VideoOverlay({
    currentTime,
    transcript,
    style,
    centerX,
    onCropChange,
}: VideoOverlayProps) {
    const currentSub = useMemo(() => findCurrentSubtitle(transcript, currentTime), [currentTime, transcript]);

    const handleMouseDown = useCallback((e: MouseEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect();

        const onMouseMove = (moveEvent: globalThis.MouseEvent) => {
            onCropChange(getCropFromClientX(moveEvent.clientX, rect));
        };
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);

        onCropChange(getCropFromClientX(e.clientX, rect));
    }, [onCropChange]);

    const handleTouchStart = useCallback((e: TouchEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const touch = e.touches[0];
        if (touch) {
            onCropChange(getCropFromClientX(touch.clientX, rect));
        }

        const onTouchMove = (moveEvent: globalThis.TouchEvent) => {
            const t = moveEvent.touches[0];
            if (t) {
                onCropChange(getCropFromClientX(t.clientX, rect));
            }
        };
        const onTouchEnd = () => {
            window.removeEventListener('touchmove', onTouchMove);
            window.removeEventListener('touchend', onTouchEnd);
        };

        window.addEventListener('touchmove', onTouchMove, { passive: true });
        window.addEventListener('touchend', onTouchEnd);
    }, [onCropChange]);

    const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
        const next = getNextCropValue(centerX, e.key);
        if (next === null) {
            return;
        }
        e.preventDefault();
        onCropChange(next);
    }, [centerX, onCropChange]);

    return (
        <div
            className="absolute inset-0 cursor-crosshair select-none"
            onMouseDown={handleMouseDown}
            onTouchStart={handleTouchStart}
        >
            <CropGuide centerX={centerX} />
            <LiveSubtitle currentSub={currentSub} style={style} />
            <CropSlider centerX={centerX} onKeyDown={handleKeyDown} />
        </div>
    );
}

function CropGuide({ centerX }: { centerX: number }) {
    return (
        <div
            className="absolute top-0 bottom-0 border-2 border-dashed border-foreground/30 bg-foreground/5 pointer-events-none transition-all duration-75"
            style={buildCropGuideStyle(centerX)}
        >
            <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-1 h-1 bg-foreground rounded-full opacity-50" />
            </div>
        </div>
    );
}

function LiveSubtitle({
    currentSub,
    style,
}: {
    currentSub: Segment | undefined;
    style: StyleName;
}) {
    if (!currentSub) {
        return null;
    }

    return (
        <div className="absolute inset-x-0 bottom-[15%] flex flex-col items-center pointer-events-none px-4">
            <div className={`text-center font-black uppercase tracking-tighter drop-shadow-[0_4px_4px_rgba(0,0,0,1)] [text-shadow:_0_2px_8px_rgba(0,0,0,0.8)] ${SUBTITLE_STYLES[style]}`}>
                {currentSub.text}
            </div>
        </div>
    );
}

function CropSlider({
    centerX,
    onKeyDown,
}: {
    centerX: number;
    onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void;
}) {
    return (
        <div
            role="slider"
            tabIndex={0}
            aria-label="Crop position"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(centerX * 100)}
            onKeyDown={onKeyDown}
            className="absolute top-3 left-3 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded border border-border text-[11px] font-mono text-foreground/70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
            CROP: {(centerX * 100).toFixed(1)}%
        </div>
    );
}
