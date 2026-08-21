interface ClerkSessionLike {
  getToken: (options?: { template?: string }) => Promise<string | null>;
}

interface ClerkLike {
  isLoaded?: boolean;
  session?: ClerkSessionLike | null;
}

declare global {
  interface Window {
    Clerk?: ClerkLike;
  }
}

export {};
