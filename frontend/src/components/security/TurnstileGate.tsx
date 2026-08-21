import { useEffect, useRef } from 'react';

import { TURNSTILE_SITE_KEY } from '../../config';


type TurnstileAction = 'preview_analyze' | 'signup';

interface TurnstileOptions {
  action: TurnstileAction;
  callback: (token: string) => void;
  'error-callback': () => void;
  'expired-callback': () => void;
  sitekey: string;
  theme: 'auto';
}

interface TurnstileApi {
  remove: (widgetId: string) => void;
  render: (container: HTMLElement, options: TurnstileOptions) => string;
  reset: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

interface TurnstileGateProps {
  action: TurnstileAction;
  onToken: (token: string | null) => void;
  resetNonce?: number;
  siteKey?: string;
}

const SCRIPT_ID = 'cloudflare-turnstile-script';
const SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
let scriptPromise: Promise<void> | null = null;

function loadTurnstile(): Promise<void> {
  if (window.turnstile) {
    return Promise.resolve();
  }
  if (scriptPromise) {
    return scriptPromise;
  }
  scriptPromise = new Promise<void>((resolve, reject) => {
    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    const script = existing ?? document.createElement('script');
    const loaded = () => resolve();
    const failed = () => reject(new Error('Turnstile script failed to load'));
    script.addEventListener('load', loaded, { once: true });
    script.addEventListener('error', failed, { once: true });
    if (!existing) {
      script.id = SCRIPT_ID;
      script.src = SCRIPT_URL;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  }).catch((error: unknown) => {
    scriptPromise = null;
    throw error;
  });
  return scriptPromise;
}

export function TurnstileGate({
  action,
  onToken,
  resetNonce = 0,
  siteKey = TURNSTILE_SITE_KEY,
}: TurnstileGateProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!siteKey) {
      onToken(null);
      return undefined;
    }
    let disposed = false;
    void loadTurnstile()
      .then(() => {
        if (disposed || !containerRef.current || !window.turnstile) {
          return;
        }
        widgetIdRef.current = window.turnstile.render(containerRef.current, {
          action,
          callback: (token) => onToken(token),
          'error-callback': () => onToken(null),
          'expired-callback': () => onToken(null),
          sitekey: siteKey,
          theme: 'auto',
        });
      })
      .catch(() => {
        if (!disposed) {
          onToken(null);
        }
      });

    return () => {
      disposed = true;
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
    };
  }, [action, onToken, siteKey]);

  useEffect(() => {
    if (resetNonce > 0 && widgetIdRef.current && window.turnstile) {
      window.turnstile.reset(widgetIdRef.current);
    }
  }, [resetNonce]);

  if (!siteKey) {
    return <p role="alert" className="text-xs text-red-300">Turnstile site key is not configured.</p>;
  }
  return <div ref={containerRef} aria-label="Security verification" />;
}
