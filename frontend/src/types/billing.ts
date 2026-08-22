export interface BillingPlan {
  code: string;
  name: string;
  monthly_price_minor: number;
  currency: string;
  monthly_compute_credits: number;
  max_source_minutes_per_job: number;
  max_clips_per_job: number;
  max_active_jobs: number;
  retention_days: number;
}

export interface BillingSubscription {
  plan: BillingPlan;
  interval: string | null;
  status: 'pending' | 'active' | 'past_due' | 'cancelled' | 'expired';
  entitlement_active: boolean;
  period_start: string | null;
  period_end: string | null;
  cancel_at_period_end: boolean;
  grace_until: string | null;
}

export interface BillingAccount {
  subscription: BillingSubscription | null;
  plans: BillingPlan[];
  usage: {
    current_period_source_seconds: number;
    source_seconds_per_job_limit: number;
    compute_credits_used: number;
    compute_credits_available: number;
    compute_credits_reserved: number;
  };
  payments: Array<{
    id: string;
    amount_minor: number;
    currency: string;
    status: string;
    created_at: string;
  }>;
}

export interface CheckoutCustomer {
  name: string;
  surname: string;
  email: string;
  gsm_number: string;
  identity_number: string;
  address: string;
  contact_name: string;
  city: string;
  country: string;
  zip_code?: string;
}

export interface CheckoutSession {
  token: string;
  checkout_form_content: string;
  expires_in_seconds: number;
}
