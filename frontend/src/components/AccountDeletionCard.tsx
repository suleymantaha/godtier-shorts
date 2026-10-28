import { useUser } from '@clerk/clerk-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { accountApi } from '../api/client';
import { isAppError } from '../api/errors';
import { clearClientAccountState, hardReloadPage } from '../auth/accountCleanup';
import { tSafe } from '../i18n';
import type { PendingAccountDeletionSummary } from '../types';

function resolvePendingMessage(summary: PendingAccountDeletionSummary): string {
  if (summary.reason === 'subscription_cancellation_required') {
    return tSafe('accountDeletion.pendingSubscription');
  }
  if (summary.reason === 'upload_url_expiry' && typeof summary.retry_after_seconds === 'number') {
    return tSafe('accountDeletion.pendingUpload', { seconds: summary.retry_after_seconds });
  }
  return tSafe('accountDeletion.pending');
}

function resolveErrorMessage(error: unknown): string {
  if (isAppError(error)) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return tSafe('accountDeletion.genericError');
}

export function AccountDeletionCard() {
  const { t } = useTranslation();
  const { user } = useUser();
  const [confirmation, setConfirmation] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<'error' | 'warning' | null>(null);

  const canDelete = confirmation === 'DELETE' && Boolean(user) && !isDeleting;

  async function handleDeleteAccount() {
    if (!canDelete || !user) {
      return;
    }

    setIsDeleting(true);
    setMessage(null);
    setMessageTone(null);

    try {
      const response = await accountApi.deleteMyData('DELETE');
      if (response.status !== 'purged') {
        setIsPending(true);
        setMessage(response.status === 'deletion_pending'
          ? resolvePendingMessage(response.summary) : t('accountDeletion.genericError'));
        setMessageTone('warning');
        setIsDeleting(false);
        return;
      }
    } catch (error) {
      setMessage(resolveErrorMessage(error));
      setMessageTone('error');
      setIsDeleting(false);
      return;
    }

    try {
      await user.delete();
      clearClientAccountState();
      hardReloadPage();
    } catch {
      clearClientAccountState();
      setMessage(t('accountDeletion.partialError'));
      setMessageTone('warning');
      setIsDeleting(false);
    }
  }

  return (
    <section className="glass-card rounded-2xl border border-rose-500/20 bg-rose-500/5 p-5 sm:p-6">
      <div className="flex flex-col gap-4">
        <div>
          <p className="text-xs font-mono uppercase tracking-[0.2em] text-rose-200">{t('accountDeletion.danger')}</p>
          <h2 className="mt-2 text-lg font-semibold text-foreground">{t('accountDeletion.title')}</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {t('accountDeletion.description')}
          </p>
        </div>
        <label className="flex flex-col gap-2 text-xs font-mono uppercase tracking-[0.18em] text-muted-foreground">
          {t('accountDeletion.confirmation')}
          <input
            aria-label={t('accountDeletion.inputAria')}
            className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm tracking-[0.08em] text-foreground outline-none transition focus:border-rose-400/60"
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder={t('accountDeletion.placeholder')}
            type="text"
            value={confirmation}
          />
        </label>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <button
            className="rounded-xl border border-rose-400/40 bg-rose-500/20 px-4 py-3 text-sm font-semibold text-rose-50 transition disabled:cursor-not-allowed disabled:opacity-40"
            disabled={!canDelete}
            onClick={handleDeleteAccount}
            type="button"
          >
            {isDeleting ? t('accountDeletion.deleting') : t(isPending ? 'accountDeletion.retry' : 'accountDeletion.action')}
          </button>
          {message ? (
            <p
              className={messageTone === 'warning' ? 'text-sm text-amber-200' : 'text-sm text-rose-200'}
              role="alert"
            >
              {message}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
