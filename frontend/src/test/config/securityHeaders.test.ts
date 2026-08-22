import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

describe('Cloudflare Pages security headers', () => {
  it('ships strict browser headers with Clerk, Turnstile and iyzico allowlists', () => {
    const source = fs.readFileSync(path.resolve(process.cwd(), 'public/_headers'), 'utf8');

    expect(source).toContain('Strict-Transport-Security: max-age=31536000');
    expect(source).toContain("frame-ancestors 'none'");
    expect(source).toContain('https://challenges.cloudflare.com');
    expect(source).toContain('https://*.protect.clerk.com');
    expect(source).toContain('https://*.iyzipay.com');
    expect(source).toContain('X-Content-Type-Options: nosniff');
    expect(source).not.toContain("default-src *");
  });
});
