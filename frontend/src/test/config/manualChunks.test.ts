import { describe, expect, it } from 'vitest';

import { resolveManualChunk } from '../../../build/manualChunks';

describe('resolveManualChunk', () => {
  it('keeps clerk packages in the auth chunk', () => {
    expect(resolveManualChunk('/repo/frontend/node_modules/@clerk/clerk-react/dist/index.js')).toBe('vendor-auth');
  });

  it('splits react-three packages by role', () => {
    expect(resolveManualChunk('/repo/frontend/node_modules/@react-three/fiber/dist/react-three-fiber.esm.js')).toBe('vendor-react-three-fiber');
    expect(resolveManualChunk('/repo/frontend/node_modules/@react-three/drei/core/Stars.js')).toBe('vendor-react-three-drei');
  });

  it('routes three ecosystem support packages away from the core chunk', () => {
    expect(resolveManualChunk('/repo/frontend/node_modules/three-stdlib/index.js')).toBe('vendor-react-three-support');
    expect(resolveManualChunk('/repo/frontend/node_modules/troika-three-text/dist/troika-three-text.esm.js')).toBe('vendor-react-three-support');
  });

  it('normalizes windows paths and keeps raw three in the core chunk', () => {
    expect(resolveManualChunk('C:\\repo\\frontend\\node_modules\\three\\build\\three.module.js')).toBe('vendor-three-core');
  });

  it('ignores application files', () => {
    expect(resolveManualChunk('/repo/frontend/src/App.tsx')).toBeUndefined();
  });
});
