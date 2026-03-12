interface ClerkSessionLike {
  getToken: (options?: { template?: string }) => Promise<string | null>;
}

interface ClerkLike {
  session?: ClerkSessionLike | null;
}

declare global {
  interface Window {
    Clerk?: ClerkLike;
  }
}

export {};
