interface ManualChunkRule {
  chunk: string;
  patterns: string[];
}

const MANUAL_CHUNK_RULES: ManualChunkRule[] = [
  {
    chunk: 'vendor-auth',
    patterns: ['node_modules/@clerk/', 'node_modules/@clerk'],
  },
  {
    chunk: 'vendor-react-three-drei',
    patterns: ['node_modules/@react-three/drei'],
  },
  {
    chunk: 'vendor-react-three-fiber',
    patterns: ['node_modules/@react-three/fiber'],
  },
  {
    chunk: 'vendor-react-three-support',
    patterns: [
      'node_modules/three-stdlib',
      'node_modules/maath',
      'node_modules/camera-controls',
      'node_modules/meshline',
      'node_modules/troika-',
      'node_modules/suspend-react',
    ],
  },
  {
    chunk: 'vendor-three-core',
    patterns: [
      'node_modules/three/examples/jsm',
      'node_modules/three/src',
      'node_modules/three/build',
      'node_modules/three',
    ],
  },
];

export function resolveManualChunk(id: string): string | undefined {
  const normalizedId = id.replaceAll('\\', '/');

  for (const rule of MANUAL_CHUNK_RULES) {
    if (rule.patterns.some((pattern) => normalizedId.includes(pattern))) {
      return rule.chunk;
    }
  }

  return undefined;
}
