import { apiFetch } from './client';
import type { BillingAccount, CheckoutCustomer, CheckoutSession } from '../types/billing';

function idempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `checkout-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export const billingApi = {
  getAccount: () => apiFetch<BillingAccount>('/api/billing/account'),
  cancel: () => apiFetch<{ status: string }>('/api/billing/cancel', { method: 'POST' }),
  changePlan: (planCode: string, interval: 'monthly' | 'yearly') => apiFetch<{ status: string }>('/api/billing/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_code: planCode, interval }),
  }),
  checkout: (planCode: string, interval: 'monthly' | 'yearly', customer: CheckoutCustomer) => {
    const address = {
      address: customer.address,
      contact_name: customer.contact_name,
      city: customer.city,
      country: customer.country,
      ...(customer.zip_code ? { zip_code: customer.zip_code } : {}),
    };
    return apiFetch<CheckoutSession>('/api/billing/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey() },
      body: JSON.stringify({
        plan_code: planCode,
        interval,
        customer: {
          name: customer.name,
          surname: customer.surname,
          email: customer.email,
          gsm_number: customer.gsm_number,
          identity_number: customer.identity_number,
          billing_address: address,
          shipping_address: address,
        },
      }),
    });
  },
};
