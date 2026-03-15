import type { CSSProperties } from 'react';

import type { Segment } from '../../types';
import { findActiveSubtitleState, type ActiveSubtitleState } from '../../utils/subtitleTiming';

const CROP_STEP = 0.02;

export function clampCrop(x: number): number {
  return Math.max(0, Math.min(1, x));
}

export function findCurrentSubtitle(transcript: Segment[], currentTime: number): Segment | undefined {
  return transcript.find((segment) => currentTime >= segment.start && currentTime <= segment.end);
}

export function findCurrentSubtitleState(transcript: Segment[], currentTime: number): ActiveSubtitleState | null {
  return findActiveSubtitleState(transcript, currentTime);
}

export function getCropFromClientX(clientX: number, rect: Pick<DOMRect, 'left' | 'width'>): number {
  return clampCrop((clientX - rect.left) / rect.width);
}

export function getNextCropValue(centerX: number, key: string): number | null {
  if (key === 'ArrowRight' || key === 'Right') {
    return clampCrop(centerX + CROP_STEP);
  }

  if (key === 'ArrowLeft' || key === 'Left') {
    return clampCrop(centerX - CROP_STEP);
  }

  return null;
}

export function buildCropGuideStyle(centerX: number): CSSProperties {
  return {
    aspectRatio: '9/16',
    left: `calc(${centerX * 100}% - (100vh * 9/16 * 16/9 / 2))`,
    maxWidth: '56.25%',
    transform: 'translateX(-50%)',
    width: 'calc(100% * 9/16 * (16/9))',
  };
}
