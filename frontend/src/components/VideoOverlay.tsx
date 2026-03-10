import { useMemo, useCallback } from 'react';
import type { FC, MouseEvent, TouchEvent, KeyboardEvent } from 'react';
import type { Segment } from '../types';
import { SUBTITLE_STYLES } from '../config/subtitleStyles';
import type { StyleName } from '../config/subtitleStyles';

interface VideoOverlayProps {
    currentTime: number;
    transcript: Segment[];
    style: StyleName;
    centerX: number;
    onCropChange: (x: number) => void;
}

const CROP_STEP = 0.02;

function clampCrop(x: number): number {
    return Math.max(0, Math.min(1, x));
}

export const VideoOverlay: FC<VideoOverlayProps> = ({
    currentTime,
    transcript,
    style,
    centerX,
    onCropChange,
}) => {
    const currentSub = useMemo(() => {
        return transcript.find(s => currentTime >= s.start && currentTime <= s.end);
    }, [currentTime, transcript]);

    const getXFromMouse = useCallback((clientX: number, rect: DOMRect) => {
        return clampCrop((clientX - rect.left) / rect.width);
    }, []);

    const handleMouseDown = useCallback((e: MouseEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect();

        const onMouseMove = (moveEvent: globalThis.MouseEvent) => {
            onCropChange(clampCrop((moveEvent.clientX - rect.left) / rect.width));
        };
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);

        onCropChange(getXFromMouse(e.clientX, rect));
    }, [getXFromMouse, onCropChange]);

    const handleTouchStart = useCallback((e: TouchEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const touch = e.touches[0];
        if (touch) {
            onCropChange(clampCrop((touch.clientX - rect.left) / rect.width));
        }

        const onTouchMove = (moveEvent: globalThis.TouchEvent) => {
            const t = moveEvent.touches[0];
            if (t) {
                onCropChange(clampCrop((t.clientX - rect.left) / rect.width));
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
        let next = centerX;
        if (e.key === 'ArrowRight' || e.key === 'Right') {
            next = clampCrop(centerX + CROP_STEP);
        } else if (e.key === 'ArrowLeft' || e.key === 'Left') {
            next = clampCrop(centerX - CROP_STEP);
        } else {
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
            {/* 9:16 Crop Guide */}
            <div
                className="absolute top-0 bottom-0 border-2 border-dashed border-white/30 bg-white/5 pointer-events-none transition-all duration-75"
                style={{
                    left: `calc(${centerX * 100}% - (100vh * 9/16 * 16/9 / 2))`,
                    width: 'calc(100% * 9/16 * (16/9))',
                    maxWidth: '56.25%',
                    aspectRatio: '9/16',
                    transform: 'translateX(-50%)',
                }}
            >
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-1 h-1 bg-white rounded-full opacity-50" />
                </div>
            </div>

            {/* Live Subtitle Preview */}
            {currentSub && (
                <div className="absolute inset-x-0 bottom-[15%] flex flex-col items-center pointer-events-none px-4">
                    <div className={`text-center font-black uppercase tracking-tighter drop-shadow-[0_4px_4px_rgba(0,0,0,1)] [text-shadow:_0_2px_8px_rgba(0,0,0,0.8)] ${SUBTITLE_STYLES[style]}`}>
                        {currentSub.text}
                    </div>
                </div>
            )}

            {/* Keyboard-accessible crop slider */}
            <div
                role="slider"
                tabIndex={0}
                aria-label="Crop position"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(centerX * 100)}
                onKeyDown={handleKeyDown}
                className="absolute top-3 left-3 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded border border-white/10 text-[11px] font-mono text-white/70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
                CROP: {(centerX * 100).toFixed(1)}%
            </div>
        </div>
    );
};
