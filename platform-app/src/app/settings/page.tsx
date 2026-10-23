'use client';

import React, { useState, Suspense } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { useAuth, useCan } from '@/contexts/AuthContext';
import { api, errorMessage, NotificationPreferences, Plan } from '@/lib/api';
import {
  Alert, Button, Card, Input, LoadingState, Meter, Modal, Select, Switch, Tabs, TabPanel, Tone, PageHeader,
} from '@/components/ui';
import { calcCredits, formatCurrency, formatDate, formatNumber, timezoneLabel, USER_TIMEZONE } from '@/lib/format';

const COMMON_TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Anchorage', 'Pacific/Honolulu', 'America/Sao_Paulo', 'America/Argentina/Buenos_Aires',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Moscow',
  'Asia/Dubai', 'Asia/Kolkata', 'Asia/Bangkok', 'Asia/Shanghai', 'Asia/Hong_Kong',
  'Asia/Tokyo', 'Asia/Seoul', 'Asia/Singapore', 'Asia/Manila', 'Asia/Jakarta',
  'Australia/Sydney', 'Australia/Melbourne', 'Pacific/Auckland',
  'Africa/Cairo', 'Africa/Lagos', 'Africa/Johannesburg',
];

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'security', label: 'Security' },
  { id: 'billing', label: 'Billing' },
];

type Flash = (tone: Tone, text: string) => void;

function SettingsContent() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  // Stripe Checkout sends the browser back to /settings?checkout=success|cancelled.
  const checkout = params.get('checkout');
  const tab = params.get('tab') || (checkout ? 'billing' : 'profile');
  const [message, setMessage] = useState<{ tone: Tone; text: string } | null>(() =>
    checkout === 'success'
      ? { tone: 'success', text: 'Payment received. Your credits are added as soon as Stripe confirms the payment.' }
      : checkout === 'cancelled' ? { tone: 'info', text: 'Checkout cancelled — you were not charged.' } : null);

  const flash: Flash = (tone, text) => setMessage({ tone, text });
  const changeTab = (id: string) => router.replace(`${pathname}?tab=${id}`, { scroll: false });

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Your profile, preferences and your organisation's billing" />
      {message && <Alert tone={message.tone} onDismiss={() => setMessage(null)}>{message.text}</Alert>}
      <Tabs idPrefix="settings" label="Settings sections" tabs={TABS} value={tab} onChange={changeTab} />
      <TabPanel idPrefix="settings" id={tab}>
        {tab === 'profile' && <ProfileTab flash={flash} />}
        {tab === 'notifications' && <NotificationsTab flash={flash} />}
        {tab === 'security' && <SecurityTab flash={flash} />}
        {tab === 'billing' && <BillingTab flash={flash} />}
      </TabPanel>
    </div>
  );
}

function ProfileTab({ flash }: { flash: Flash }) {
  const { user, refreshUser } = useAuth();
  // PlatformLayout renders settings only once the profile is loaded, so `user` is set here.
  const [form, setForm] = useState(() => ({
    first_name: user?.first_name ?? '', last_name: user?.last_name ?? '', company: user?.company ?? '', timezone: user?.timezone || USER_TIMEZONE,
  }));
  const [saving, setSaving] = useState(false);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.updateProfile({ ...form, first_name: form.first_name.trim(), last_name: form.last_name.trim(), company: form.company.trim() || undefined });
      await refreshUser();
      flash('success', 'Profile updated.');
    } catch (err) {
      flash('danger', errorMessage(err, 'Failed to update profile.'));
    } finally {
      setSaving(false);
    }
  };

  const timezones = COMMON_TIMEZONES.includes(form.timezone) ? COMMON_TIMEZONES : [form.timezone, ...COMMON_TIMEZONES];
  return (
    <Card as="form" padding="lg" onSubmit={save} className="space-y-5" aria-labelledby="profile-h">
      <h2 id="profile-h" className="text-sm font-semibold text-ink">Profile</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input label="First name" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
        <Input label="Last name" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
        <Input label="Email" value={user?.email ?? ''} readOnly />
        <Input label="Company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
        <Select label="Timezone" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} options={timezones.map((tz) => ({ value: tz, label: `${tz} — ${timezoneLabel(tz)}` }))} />
        <Input label="Role" value={user?.role ?? ''} readOnly helpText="Roles are assigned by an admin of your organisation." />
        <Input label="Member since" value={user ? formatDate(user.created_at) : ''} readOnly />
      </div>
      <Button type="submit" loading={saving}>Save changes</Button>
    </Card>
  );
}

const PREFS: Array<{ key: keyof NotificationPreferences; label: string }> = [
  { key: 'email_blocked_tx', label: 'Email alerts for blocked transactions' },
  { key: 'email_new_cases', label: 'Email alerts for new cases' },
  { key: 'email_daily_summary', label: 'Daily compliance summary' },
  { key: 'email_weekly_report', label: 'Weekly analytics report' },
  { key: 'email_system_downtime', label: 'System downtime notifications' },
  { key: 'email_credit_alerts', label: 'Credit usage alerts (below 20%)' },
];

function NotificationsTab({ flash }: { flash: Flash }) {
  const remote = useSWR('notification-prefs', api.getNotificationPreferences);
  if (remote.error) return <Alert tone="danger">{errorMessage(remote.error)}</Alert>;
  if (!remote.data) return <LoadingState label="Loading preferences…" />;
  return <PreferencesForm initial={remote.data} onSaved={(p) => remote.mutate(p, { revalidate: false })} flash={flash} />;
}

function PreferencesForm({ initial, onSaved, flash }: {
  initial: NotificationPreferences; onSaved: (p: NotificationPreferences) => void; flash: Flash;
}) {
  const [prefs, setPrefs] = useState(initial);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateNotificationPreferences(prefs);
      onSaved(prefs);
      flash('success', 'Notification preferences saved.');
    } catch (err) {
      flash('danger', errorMessage(err, 'Failed to save preferences.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card as="section" padding="lg" className="space-y-4" aria-labelledby="prefs-h">
      <h2 id="prefs-h" className="text-sm font-semibold text-ink">Notification preferences</h2>
      <ul className="divide-y divide-border-light">
        {PREFS.map((p) => (
          <li key={p.key} className="py-3">
            <Switch label={p.label} checked={prefs[p.key]} onChange={(v) => setPrefs({ ...prefs, [p.key]: v })} />
          </li>
        ))}
      </ul>
      <Button onClick={save} loading={saving}>Save preferences</Button>
    </Card>
  );
}

function SecurityTab({ flash }: { flash: Flash }) {
  const [form, setForm] = useState({ current: '', next: '', confirm: '' });
  const [saving, setSaving] = useState(false);
  const mismatch = form.confirm.length > 0 && form.next !== form.confirm;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mismatch) return;
    setSaving(true);
    try {
      await api.changePassword({ current_password: form.current, new_password: form.next });
      setForm({ current: '', next: '', confirm: '' });
      flash('success', 'Password updated.');
    } catch (err) {
      flash('danger', errorMessage(err, 'Failed to change password.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card as="form" padding="lg" onSubmit={save} className="space-y-4 max-w-lg" aria-labelledby="security-h">
      <h2 id="security-h" className="text-sm font-semibold text-ink">Change password</h2>
      <Input label="Current password" type="password" autoComplete="current-password" value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} required />
      <Input label="New password" type="password" autoComplete="new-password" minLength={6} helpText="At least 6 characters." value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} required />
      <Input label="Confirm new password" type="password" autoComplete="new-password" value={form.confirm} error={mismatch ? 'Passwords do not match.' : undefined} onChange={(e) => setForm({ ...form, confirm: e.target.value })} required />
      <Button type="submit" loading={saving} disabled={mismatch}>Update password</Button>
    </Card>
  );
}

function BillingTab({ flash }: { flash: Flash }) {
  const { user, refreshUser } = useAuth();
  const can = useCan();
  const plans = useSWR('billing-plans', api.listPlans);
  const [confirmPlan, setConfirmPlan] = useState<Plan | null>(null);
  const [pack, setPack] = useState<{ credits: number; price_usd: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const canSubscribe = can(['POST', '/api/v1/billing/subscribe']);
  const canBuy = can(['POST', '/api/v1/credits/checkout']);

  const data = plans.data;
  const currentPlan = data?.plans.find((p) => p.id === user?.plan);
  const credits = calcCredits(user?.total_credits ?? 0, user?.used_credits ?? 0);
  const simulated = data?.payments_mode === 'simulated';
  const isUpgrade = (p: Plan) => (p.price_monthly ?? 0) > (currentPlan?.price_monthly ?? 0);

  const subscribe = async () => {
    if (!confirmPlan) return;
    setBusy(true);
    try {
      const res = await api.subscribe(confirmPlan.id);
      await Promise.all([refreshUser(), plans.mutate()]);
      flash('success', res.message);
    } catch (err) {
      flash('danger', errorMessage(err, 'Plan change failed.'));
    } finally {
      setBusy(false);
      setConfirmPlan(null);
    }
  };

  const checkout = async () => {
    if (!pack) return;
    setBusy(true);
    try {
      const res = await api.checkoutCredits(pack.credits);
      if (res.mode === 'stripe') {
        window.location.assign(res.checkout_url);
        return;
      }
      await refreshUser();
      flash('info', `Simulated payment: ${formatNumber(res.credits_added)} credits added for ${formatCurrency(res.price_usd)}. No payment was taken — this environment runs in simulated payments mode.`);
      setPack(null);
    } catch (err) {
      flash('danger', errorMessage(err, 'Checkout failed.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {!canSubscribe && <Alert tone="info">Plan changes and credit purchases are made by an admin of your organisation.</Alert>}

      <Card as="section" padding="lg" aria-labelledby="plan-h">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 id="plan-h" className="text-sm font-semibold text-ink mb-2">Current plan</h2>
            <p className="text-lg font-bold text-ink capitalize">{currentPlan?.name || user?.plan}</p>
            <p className="text-sm text-ink-muted">
              {currentPlan?.price_monthly != null ? `${formatCurrency(currentPlan.price_monthly)}/month + credit usage` : 'Custom pricing'}
            </p>
            {data?.billing_cycle_end && <p className="text-xs text-ink-muted mt-1">Renews {formatDate(data.billing_cycle_end)}</p>}
            {data?.days_remaining != null && <p className="text-xs text-ink-muted">{data.days_remaining} days left in this {data.is_trial ? 'trial' : 'cycle'}</p>}
            {data?.pending_plan_change && <p className="text-xs text-warning-fg mt-1">Change to {data.pending_plan_change} scheduled for the end of the cycle</p>}
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-accent-fg">{formatNumber(credits.remaining)}</p>
            <p className="text-xs text-ink-muted">credits remaining</p>
          </div>
        </div>
        <Meter className="mt-4" value={credits.used} max={credits.total || 1} label="Credits used" valueText={`${credits.pctUsed}% used`} />
        <p className="text-xs text-ink-muted mt-1">{formatNumber(credits.used)} of {formatNumber(credits.total)} used ({credits.pctUsed}%)</p>
      </Card>

      <Card as="section" padding="lg" aria-labelledby="plans-h">
        <h2 id="plans-h" className="text-sm font-semibold text-ink mb-1">Plans</h2>
        <p className="text-xs text-ink-muted mb-4">Upgrades take effect immediately with prorated billing; downgrades apply at the end of the cycle.</p>
        {plans.isLoading ? <LoadingState label="Loading plans…" /> : plans.error ? <Alert tone="danger">{errorMessage(plans.error)}</Alert> : (
          <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {data?.plans.map((p) => {
              const isCurrent = p.id === user?.plan;
              const isEnterprise = p.included_credits == null;
              return (
                <li key={p.id} className={`rounded-xl border p-4 flex flex-col ${isCurrent ? 'border-accent bg-accent/5' : 'border-border bg-bg-alt'}`}>
                  <h3 className="text-sm font-semibold text-ink">{p.name}{isCurrent && <span className="sr-only"> (current plan)</span>}</h3>
                  <p className="text-lg font-bold text-accent-fg mt-1">
                    {p.price_monthly != null ? formatCurrency(p.price_monthly) : 'Custom'}
                    {p.price_monthly != null && <span className="text-xs text-ink-muted font-normal">/mo</span>}
                  </p>
                  <ul className="mt-3 space-y-1.5 flex-1">
                    {p.features.map((f) => <li key={f} className="text-2xs text-ink-secondary">✓ {f}</li>)}
                  </ul>
                  {canSubscribe && (
                    <Button
                      className="mt-4 w-full"
                      size="sm"
                      variant={isCurrent || isEnterprise ? 'secondary' : 'primary'}
                      disabled={isCurrent || isEnterprise}
                      onClick={() => setConfirmPlan(p)}
                    >
                      {isCurrent ? 'Current plan' : isEnterprise ? 'Contact sales' : isUpgrade(p) ? 'Upgrade' : 'Downgrade'}
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {canBuy && data && (
        <Card as="section" padding="lg" aria-labelledby="credits-h">
          <h2 id="credits-h" className="text-sm font-semibold text-ink mb-1">Add credits</h2>
          {simulated ? (
            <Alert tone="warning" className="mb-4">Simulated payments mode: purchases add credits without taking a real payment.</Alert>
          ) : (
            <p className="text-xs text-ink-muted mb-4">One-time top-ups. Payment happens on Stripe&apos;s checkout page; FinShield never sees card details.</p>
          )}
          <ul className="grid grid-cols-3 gap-3">
            {data.credit_packs.map((p) => (
              <li key={p.credits}>
                <button
                  type="button"
                  onClick={() => setPack(p)}
                  className="w-full glass glass-hover p-4 text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                >
                  <span className="block text-lg font-bold text-ink">{formatNumber(p.credits)}</span>
                  <span className="block text-xs text-accent-fg font-semibold">{formatCurrency(p.price_usd)}</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Modal
        open={pack !== null}
        onClose={() => setPack(null)}
        title="Buy credits"
        description={pack ? `${formatNumber(pack.credits)} credits for ${formatCurrency(pack.price_usd)}${simulated ? ' (simulated)' : ''}` : undefined}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPack(null)}>Cancel</Button>
            <Button onClick={checkout} loading={busy}>{simulated ? 'Add credits (simulated)' : 'Continue to Stripe'}</Button>
          </>
        }
      >
        <p className="text-sm text-ink-secondary">
          {simulated
            ? <>This environment runs in <strong>simulated</strong> payments mode: the credits are added and no payment is taken.</>
            : 'You will be sent to Stripe to pay; your credits are added once Stripe confirms the payment.'}
        </p>
      </Modal>

      <Modal
        open={confirmPlan !== null}
        onClose={() => setConfirmPlan(null)}
        title={confirmPlan && isUpgrade(confirmPlan) ? 'Confirm upgrade' : 'Confirm downgrade'}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmPlan(null)}>Cancel</Button>
            <Button onClick={subscribe} loading={busy}>Confirm</Button>
          </>
        }
      >
        {confirmPlan && (
          <div className="space-y-3 text-sm text-ink-secondary">
            <p>Change from <strong>{currentPlan?.name}</strong> to <strong>{confirmPlan.name}</strong>?</p>
            {isUpgrade(confirmPlan) ? (
              <p>The upgrade takes effect immediately and is prorated for the rest of the cycle. Credits are topped up to {formatNumber(confirmPlan.included_credits ?? 0)}.</p>
            ) : (
              <p>The downgrade takes effect at the end of the current cycle{data?.billing_cycle_end ? ` (${formatDate(data.billing_cycle_end)})` : ''}.</p>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <PlatformLayout>
      <Suspense fallback={<LoadingState />}>
        <SettingsContent />
      </Suspense>
    </PlatformLayout>
  );
}
