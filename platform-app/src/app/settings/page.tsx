'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import PlatformLayout from '@/components/PlatformLayout';
import { useAuth } from '@/contexts/AuthContext';
import { api, Plan, PlansResponse, NotificationPreferences } from '@/lib/api';
import { formatCurrency, formatNumber, formatDate, formatDateTime, calcCredits, USER_TIMEZONE, timezoneLabel } from '@/lib/format';

// Common timezones for the selector
const COMMON_TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Anchorage', 'Pacific/Honolulu', 'America/Sao_Paulo', 'America/Argentina/Buenos_Aires',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Moscow',
  'Asia/Dubai', 'Asia/Kolkata', 'Asia/Bangkok', 'Asia/Shanghai', 'Asia/Hong_Kong',
  'Asia/Tokyo', 'Asia/Seoul', 'Asia/Singapore', 'Asia/Manila', 'Asia/Jakarta',
  'Australia/Sydney', 'Australia/Melbourne', 'Pacific/Auckland',
  'Africa/Cairo', 'Africa/Lagos', 'Africa/Johannesburg',
];

function SettingsContent() {
  const { user, refreshUser } = useAuth();
  const searchParams = useSearchParams();
  const [tab, setTab] = useState(searchParams.get('tab') || 'profile');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const t = searchParams.get('tab');
    if (t) setTab(t);
  }, [searchParams]);

  const flash = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(''), 4000);
  };

  const tabs = [
    { id: 'profile', label: 'Profile' },
    { id: 'notifications', label: 'Notifications' },
    { id: 'security', label: 'Security' },
    { id: 'billing', label: 'Billing' },
  ];

  return (
    <PlatformLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink">Settings</h1>
          <p className="text-sm text-ink-muted mt-0.5">Manage your account and preferences</p>
        </div>

        {message && (
          <div className="p-3 rounded-xl bg-accent/10 border border-accent/20 text-accent-dark text-sm">{message}</div>
        )}

        <div className="flex gap-1 bg-bg-alt rounded-xl p-1 w-fit">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                tab === t.id ? 'bg-accent/10 text-accent-dark' : 'text-ink-muted hover:text-ink'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'profile' && <ProfileTab flash={flash} />}
        {tab === 'notifications' && <NotificationsTab flash={flash} />}
        {tab === 'security' && <SecurityTab flash={flash} />}
        {tab === 'billing' && <BillingTab flash={flash} refreshUser={refreshUser} />}
      </div>
    </PlatformLayout>
  );
}

// ── Profile Tab ──
function ProfileTab({ flash }: { flash: (m: string) => void }) {
  const { user, refreshUser } = useAuth();
  const [firstName, setFirstName] = useState(user?.first_name || '');
  const [lastName, setLastName] = useState(user?.last_name || '');
  const [company, setCompany] = useState(user?.company || '');
  const [timezone, setTimezone] = useState(user?.timezone || USER_TIMEZONE);
  const [saving, setSaving] = useState(false);

  // Re-sync fields once the async user profile hydrates (prevents wiping data on save)
  useEffect(() => {
    if (user) {
      setFirstName(user.first_name || '');
      setLastName(user.last_name || '');
      setCompany(user.company || '');
      setTimezone(user.timezone || USER_TIMEZONE);
    }
  }, [user]);

  const handleSave = async () => {
    if (!firstName.trim() || !lastName.trim()) {
      flash('First and last name are required.');
      return;
    }
    setSaving(true);
    try {
      await api.updateProfile({ first_name: firstName.trim(), last_name: lastName.trim(), company: company.trim() || undefined, timezone });
      await refreshUser();
      flash('Profile updated successfully.');
    } catch (e: any) {
      flash(e.message || 'Failed to update profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="glass p-6 space-y-5 animate-fade-in-up">
      <h3 className="text-sm font-semibold text-ink">Profile Information</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label htmlFor="profile_first_name" className="block text-xs font-medium text-ink-muted mb-1.5">First Name</label>
          <input id="profile_first_name" value={firstName} onChange={e => setFirstName(e.target.value)} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink" />
        </div>
        <div>
          <label htmlFor="profile_last_name" className="block text-xs font-medium text-ink-muted mb-1.5">Last Name</label>
          <input id="profile_last_name" value={lastName} onChange={e => setLastName(e.target.value)} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink" />
        </div>
        <div>
          <label htmlFor="profile_email" className="block text-xs font-medium text-ink-muted mb-1.5">Email</label>
          <input id="profile_email" defaultValue={user?.email || ''} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink" readOnly />
        </div>
        <div>
          <label htmlFor="profile_company" className="block text-xs font-medium text-ink-muted mb-1.5">Company</label>
          <input id="profile_company" value={company} onChange={e => setCompany(e.target.value)} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink" />
        </div>
        <div>
          <label htmlFor="profile_timezone" className="block text-xs font-medium text-ink-muted mb-1.5">Timezone</label>
          <select id="profile_timezone" value={timezone} onChange={e => setTimezone(e.target.value)} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink">
            {COMMON_TIMEZONES.map((tz) => (
              <option key={tz} value={tz}>{tz} — {timezoneLabel(tz)}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="profile_member_since" className="block text-xs font-medium text-ink-muted mb-1.5">Member since</label>
          <input id="profile_member_since" defaultValue={user ? formatDate(user.created_at || '') : ''} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink" readOnly />
        </div>
      </div>
      <button onClick={handleSave} disabled={saving} className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-6 py-2.5 rounded-xl transition-all disabled:opacity-50">
        {saving ? 'Saving...' : 'Save Changes'}
      </button>
    </div>
  );
}

// ── Notifications Tab ──
function NotificationsTab({ flash }: { flash: (m: string) => void }) {
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getNotificationPreferences()
      .then(setPrefs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!prefs) return;
    setSaving(true);
    try {
      await api.updateNotificationPreferences(prefs);
      flash('Notification preferences saved.');
    } catch (e: any) {
      flash(e.message || 'Failed to save preferences.');
    } finally {
      setSaving(false);
    }
  };

  const toggle = (key: keyof NotificationPreferences) => {
    if (!prefs) return;
    setPrefs({ ...prefs, [key]: !prefs[key] });
  };

  if (loading) {
    return (
      <div className="glass p-12 text-center">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm text-ink-muted">Loading preferences...</p>
      </div>
    );
  }

  const items = prefs ? [
    { label: 'Email alerts for blocked transactions', key: 'email_blocked_tx' as const, value: prefs.email_blocked_tx },
    { label: 'Email alerts for new cases', key: 'email_new_cases' as const, value: prefs.email_new_cases },
    { label: 'Daily compliance summary', key: 'email_daily_summary' as const, value: prefs.email_daily_summary },
    { label: 'Weekly analytics report', key: 'email_weekly_report' as const, value: prefs.email_weekly_report },
    { label: 'System downtime notifications', key: 'email_system_downtime' as const, value: prefs.email_system_downtime },
    { label: 'Credit usage alerts (below 20%)', key: 'email_credit_alerts' as const, value: prefs.email_credit_alerts },
  ] : [];

  return (
    <div className="glass p-6 space-y-5 animate-fade-in-up">
      <h3 className="text-sm font-semibold text-ink">Notification Preferences</h3>
      {items.map((n) => (
        <div key={n.key} className="flex items-center justify-between py-2 border-b border-border-light">
          <span className="text-sm text-ink-secondary">{n.label}</span>
          <button
            onClick={() => toggle(n.key)}
            className={`relative w-9 h-5 rounded-full transition-colors ${n.value ? 'bg-accent/30' : 'bg-white/10'}`}
          >
            <span className={`absolute top-[2px] left-[2px] w-4 h-4 rounded-full transition-all ${n.value ? 'translate-x-4 bg-accent' : 'bg-gray-400'}`} />
          </button>
        </div>
      ))}
      <button onClick={handleSave} disabled={saving} className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-6 py-2.5 rounded-xl transition-all disabled:opacity-50">
        {saving ? 'Saving...' : 'Save Preferences'}
      </button>
    </div>
  );
}

// ── Security Tab ──
function SecurityTab({ flash }: { flash: (m: string) => void }) {
  const [current, setCurrent] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (newPw !== confirm) { flash('New passwords do not match.'); return; }
    if (newPw.length < 6) { flash('New password must be at least 6 characters.'); return; }
    setSaving(true);
    try {
      await api.changePassword({ current_password: current, new_password: newPw });
      setCurrent(''); setNewPw(''); setConfirm('');
      flash('Password updated successfully.');
    } catch (e: any) {
      flash(e.message || 'Failed to change password.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="glass p-6 space-y-5 animate-fade-in-up">
      <h3 className="text-sm font-semibold text-ink">Security Settings</h3>
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-ink-muted mb-1.5">Current Password</label>
          <input type="password" value={current} onChange={e => setCurrent(e.target.value)} placeholder="Enter current password" className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-muted mb-1.5">New Password</label>
          <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} placeholder="Enter new password (min 6 characters)" className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-muted mb-1.5">Confirm New Password</label>
          <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="Confirm new password" className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" />
        </div>
      </div>
      <button onClick={handleSave} disabled={saving || !current || !newPw || !confirm} className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-6 py-2.5 rounded-xl transition-all disabled:opacity-50">
        {saving ? 'Updating...' : 'Update Password'}
      </button>
    </div>
  );
}

// ── Billing Tab ──
function BillingTab({ flash, refreshUser }: { flash: (m: string) => void; refreshUser: () => Promise<void> }) {
  const { user } = useAuth();
  const [plansData, setPlansData] = useState<PlansResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [checkoutPack, setCheckoutPack] = useState<{ credits: number; price: number } | null>(null);
  const [cardForm, setCardForm] = useState({ last4: '', expiry: '', holder: '' });
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [confirmPlan, setConfirmPlan] = useState<Plan | null>(null);
  const [useSavedCard, setUseSavedCard] = useState(false);
  const [showSavedCardForm, setShowSavedCardForm] = useState(false);
  const [savedCardForm, setSavedCardForm] = useState({ last4: '', expiry: '', holder: '' });
  const [savingCard, setSavingCard] = useState(false);
  const [removingCard, setRemovingCard] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.listPlans()
      .then(setPlansData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Auto-enable saved card if available
  useEffect(() => {
    if (user?.saved_card_last4) {
      setUseSavedCard(true);
    }
  }, [user?.saved_card_last4]);

  const currentPlan = plansData?.plans.find(p => p.id === user?.plan);
  const credits = calcCredits(user?.total_credits ?? 0, user?.used_credits ?? 0);
  const daysRemaining = plansData?.days_remaining;

  const handleSubscribe = async (plan: Plan) => {
    setConfirmPlan(plan);
  };

  const confirmSubscribe = async () => {
    if (!confirmPlan) return;
    setActionLoading(confirmPlan.id);
    try {
      const res = await api.subscribe(confirmPlan.id);
      await refreshUser();
      // Reload plans to get updated cycle info
      const updated = await api.listPlans();
      setPlansData(updated);
      flash(res.message);
    } catch (e: any) {
      flash(e.message || 'Subscription failed.');
    } finally {
      setActionLoading(null);
      setConfirmPlan(null);
    }
  };

  const handleCheckout = async () => {
    if (!checkoutPack) return;
    setCheckoutLoading(true);
    try {
      const res = await api.checkoutCredits({
        credits: checkoutPack.credits,
        card_last4: useSavedCard ? undefined : cardForm.last4,
        card_expiry: useSavedCard ? undefined : cardForm.expiry,
        card_holder: useSavedCard ? undefined : cardForm.holder,
        use_saved_card: useSavedCard,
      });
      await refreshUser();
      flash(`${formatNumber(res.credits_added)} credits added for ${formatCurrency(res.price_usd)}. Card ****${res.card_last4}.`);
      setCheckoutPack(null);
      setCardForm({ last4: '', expiry: '', holder: '' });
    } catch (e: any) {
      flash(e.message || 'Payment failed.');
    } finally {
      setCheckoutLoading(false);
    }
  };

  const handleSaveCard = async () => {
    if (!savedCardForm.last4 || !savedCardForm.expiry || !savedCardForm.holder) {
      flash('Please fill in all card fields.');
      return;
    }
    setSavingCard(true);
    try {
      await api.savePaymentMethod({
        card_last4: savedCardForm.last4,
        card_expiry: savedCardForm.expiry,
        card_holder: savedCardForm.holder,
      });
      await refreshUser();
      flash('Payment method saved successfully.');
      setShowSavedCardForm(false);
      setSavedCardForm({ last4: '', expiry: '', holder: '' });
      setUseSavedCard(true);
    } catch (e: any) {
      flash(e.message || 'Failed to save payment method.');
    } finally {
      setSavingCard(false);
    }
  };

  const handleRemoveCard = async () => {
    if (!confirm('Remove saved payment method?')) return;
    setRemovingCard(true);
    try {
      await api.removePaymentMethod();
      await refreshUser();
      flash('Payment method removed.');
      setUseSavedCard(false);
    } catch (e: any) {
      flash(e.message || 'Failed to remove payment method.');
    } finally {
      setRemovingCard(false);
    }
  };

  const CREDIT_PACKS = [
    { credits: 10000, price: 9, label: '$9' },
    { credits: 50000, price: 39, label: '$39' },
    { credits: 200000, price: 129, label: '$129' },
  ];

  return (
    <div className="space-y-4 animate-fade-in-up">
      {/* Current Plan + Billing Cycle */}
      <div className="glass p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-ink">Current Plan</h3>
          {daysRemaining != null && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-ink-muted">{daysRemaining} days remaining</span>
              <div className="w-20 h-1.5 bg-bg rounded-full overflow-hidden">
                <div className="h-full bg-accent rounded-full" style={{ width: `${Math.max(5, (daysRemaining / 30) * 100)}%` }} />
              </div>
            </div>
          )}
          <div className="text-[10px] text-ink-light mt-0.5">Timezone: {timezoneLabel(USER_TIMEZONE)}</div>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-lg font-bold text-ink capitalize">{currentPlan?.name || user?.plan || 'Growth'}</div>
            <div className="text-sm text-ink-muted">
              {currentPlan?.price_monthly != null ? `$${currentPlan.price_monthly}/month + credit usage` : 'Custom pricing'}
            </div>
            {plansData?.billing_cycle_end && (
              <div className="text-xs text-ink-light mt-1">
                Renews {formatDate(plansData.billing_cycle_end)}
              </div>
            )}
            {plansData?.pending_plan_change && (
              <div className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                <span>⏳</span> Downgrade to {plansData.pending_plan_change} scheduled for end of cycle
              </div>
            )}
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-accent-dark">{formatNumber(credits.remaining)}</div>
            <div className="text-xs text-ink-muted">credits remaining</div>
          </div>
        </div>
        <div className="mt-4 w-full h-2 bg-bg rounded-full overflow-hidden">
          <div className="h-full bg-accent rounded-full transition-all duration-500" style={{ width: `${credits.pctUsed}%` }} />
        </div>
        <div className="text-xs text-ink-light mt-1">{formatNumber(credits.used)} of {formatNumber(credits.total)} used ({credits.pctUsed}%)</div>
      </div>

      {/* Plans */}
      <div className="glass p-6">
        <h3 className="text-sm font-semibold text-ink mb-1">Change Plan</h3>
        <p className="text-xs text-ink-light mb-4">Upgrades take effect immediately with prorated billing. Downgrades apply at the end of your current cycle.</p>
        {loading ? (
          <div className="py-8 text-center">
            <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto" />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {plansData?.plans.map((p) => {
              const isCurrent = p.id === user?.plan;
              const isEnterprise = p.included_credits == null;
              const currentPrice = currentPlan?.price_monthly ?? 0;
              const isDowngrade = (p.price_monthly ?? 0) < currentPrice;
              return (
                <div key={p.id} className={`rounded-xl border p-4 transition-all ${isCurrent ? 'border-accent/50 bg-accent/5' : 'border-border bg-bg-alt'}`}>
                  <div className="text-sm font-semibold text-ink">{p.name}</div>
                  <div className="text-lg font-bold text-accent-dark mt-1">
                    {p.price_monthly != null ? formatCurrency(p.price_monthly) : 'Custom'}
                    {p.price_monthly != null && <span className="text-xs text-ink-light font-normal">/mo</span>}
                  </div>
                  <ul className="mt-3 space-y-1.5">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-1.5 text-[11px] text-ink-muted">
                        <span className="text-accent-dark mt-0.5">✓</span>
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                  <button
                    disabled={isCurrent || isEnterprise || actionLoading === p.id}
                    onClick={() => handleSubscribe(p)}
                    className={`mt-4 w-full text-xs font-semibold py-2 rounded-lg transition-all ${
                      isCurrent
                        ? 'bg-bg text-ink-light cursor-default'
                        : isEnterprise
                        ? 'bg-bg text-ink-muted cursor-not-allowed'
                        : 'bg-accent hover:bg-accent-light text-ink'
                    } disabled:opacity-60`}
                  >
                    {isCurrent ? 'Current' : isEnterprise ? 'Contact sales' : actionLoading === p.id ? 'Working...' : isDowngrade ? 'Downgrade' : 'Upgrade'}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Add Credits */}
      <div className="glass p-6">
        <h3 className="text-sm font-semibold text-ink mb-1">Add Credits</h3>
        <p className="text-xs text-ink-light mb-4">One-time credit top-ups with payment verification.</p>
        <div className="grid grid-cols-3 gap-3">
          {CREDIT_PACKS.map((p) => (
            <button
              key={p.credits}
              onClick={() => setCheckoutPack(p)}
              className="glass glass-hover p-4 text-center transition-all hover:-translate-y-0.5"
            >
              <div className="text-lg font-bold text-ink">{formatNumber(p.credits)}</div>
              <div className="text-xs text-accent-dark font-semibold">{formatCurrency(p.price)}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Saved Payment Method */}
      <div className="glass p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-ink">Payment Method</h3>
            <p className="text-xs text-ink-light mt-0.5">Saved card for quick checkout (Qoder-like flow)</p>
          </div>
        </div>
        {user?.saved_card_last4 ? (
          <div className="flex items-center justify-between bg-bg-alt rounded-xl px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-6 bg-gradient-to-r from-blue-600 to-blue-800 rounded flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" />
                </svg>
              </div>
              <div>
                <div className="text-sm font-medium text-ink">**** **** **** {user.saved_card_last4}</div>
                <div className="text-[11px] text-ink-muted">{user.saved_card_holder} · Expires {user.saved_card_expiry}</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowSavedCardForm(true)}
                className="text-xs text-accent-dark hover:text-accent px-3 py-1.5 rounded-lg bg-accent/5 hover:bg-accent/10 transition-colors"
              >
                Update
              </button>
              <button
                onClick={handleRemoveCard}
                disabled={removingCard}
                className="text-xs text-red-600 hover:text-red-700 px-3 py-1.5 rounded-lg bg-red-50 hover:bg-red-100 transition-colors disabled:opacity-50"
              >
                {removingCard ? 'Removing...' : 'Remove'}
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center py-4">
            <p className="text-sm text-ink-light mb-3">No payment method saved. Add one for faster checkout.</p>
            <button
              onClick={() => setShowSavedCardForm(true)}
              className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-4 py-2 rounded-xl transition-all"
            >
              + Add Payment Method
            </button>
          </div>
        )}
      </div>

      {/* Save Card Modal */}
      {showSavedCardForm && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center" onClick={() => setShowSavedCardForm(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-sm glass border border-border rounded-2xl shadow-2xl p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-ink mb-1">{user?.saved_card_last4 ? 'Update' : 'Add'} Payment Method</h3>
            <p className="text-sm text-ink-muted mb-4">This card will be saved for future purchases.</p>
            <div className="space-y-3">
              <div>
                <label htmlFor="saved_card_holder" className="block text-xs font-medium text-ink-muted mb-1">Cardholder Name</label>
                <input id="saved_card_holder" value={savedCardForm.holder} onChange={e => setSavedCardForm({...savedCardForm, holder: e.target.value})} placeholder="John Doe" className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="saved_card_last4" className="block text-xs font-medium text-ink-muted mb-1">Last 4 Digits</label>
                  <input id="saved_card_last4" value={savedCardForm.last4} onChange={e => setSavedCardForm({...savedCardForm, last4: e.target.value.replace(/\D/g, '').slice(0, 4)})} placeholder="4242" maxLength={4} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light font-mono" />
                </div>
                <div>
                  <label htmlFor="saved_card_expiry" className="block text-xs font-medium text-ink-muted mb-1">Expiry (MM/YY)</label>
                  <input id="saved_card_expiry" value={savedCardForm.expiry} onChange={e => setSavedCardForm({...savedCardForm, expiry: e.target.value.slice(0, 5)})} placeholder="12/26" className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light font-mono" />
                </div>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 mt-4">
              <button onClick={() => setShowSavedCardForm(false)} className="px-4 py-2 text-sm text-ink-muted hover:text-ink transition-colors">Cancel</button>
              <button
                onClick={handleSaveCard}
                disabled={savingCard || !savedCardForm.last4 || !savedCardForm.expiry || !savedCardForm.holder}
                className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-6 py-2 rounded-xl transition-all disabled:opacity-50"
              >
                {savingCard ? 'Saving...' : 'Save Card'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Checkout Modal */}
      {checkoutPack && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center" onClick={() => setCheckoutPack(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-sm glass border border-border rounded-2xl shadow-2xl p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-ink mb-1">Purchase Credits</h3>
            <p className="text-sm text-ink-muted mb-4">{formatNumber(checkoutPack.credits)} credits for <span className="text-accent-dark font-semibold">{formatCurrency(checkoutPack.price)}</span></p>

            {/* Saved card toggle */}
            {user?.saved_card_last4 && (
              <div className="mb-4 p-3 rounded-xl bg-bg-alt border border-border">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useSavedCard}
                    onChange={e => setUseSavedCard(e.target.checked)}
                    className="w-4 h-4 rounded border-border accent-accent"
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-ink">Use saved card</div>
                    <div className="text-[11px] text-ink-muted">**** **** **** {user.saved_card_last4} ({user.saved_card_holder})</div>
                  </div>
                </label>
              </div>
            )}

            {!useSavedCard && (
              <div className="space-y-3">
                <div>
                  <label htmlFor="checkout_holder" className="block text-xs font-medium text-ink-muted mb-1">Cardholder Name</label>
                  <input id="checkout_holder" value={cardForm.holder} onChange={e => setCardForm({...cardForm, holder: e.target.value})} placeholder="John Doe" className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="checkout_last4" className="block text-xs font-medium text-ink-muted mb-1">Last 4 Digits</label>
                    <input id="checkout_last4" value={cardForm.last4} onChange={e => setCardForm({...cardForm, last4: e.target.value.replace(/\D/g, '').slice(0, 4)})} placeholder="4242" maxLength={4} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light font-mono" />
                  </div>
                  <div>
                    <label htmlFor="checkout_expiry" className="block text-xs font-medium text-ink-muted mb-1">Expiry (MM/YY)</label>
                    <input id="checkout_expiry" value={cardForm.expiry} onChange={e => setCardForm({...cardForm, expiry: e.target.value.slice(0, 5)})} placeholder="12/26" className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light font-mono" />
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-center gap-2 mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-500/10">
              <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
              <span className="text-[11px] text-emerald-600">Secured with 256-bit encryption (simulated)</span>
            </div>

            <div className="flex items-center justify-end gap-3 mt-4">
              <button onClick={() => setCheckoutPack(null)} className="px-4 py-2 text-sm text-ink-muted hover:text-ink transition-colors">Cancel</button>
              <button
                onClick={handleCheckout}
                disabled={checkoutLoading || (!useSavedCard && (!cardForm.last4 || !cardForm.expiry || !cardForm.holder))}
                className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-6 py-2 rounded-xl transition-all disabled:opacity-50"
              >
                {checkoutLoading ? 'Processing...' : `Pay ${formatCurrency(checkoutPack.price)}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Plan Change Confirmation */}
      {confirmPlan && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center" onClick={() => setConfirmPlan(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md glass border border-border rounded-2xl shadow-2xl p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-ink mb-2">
              {(confirmPlan.price_monthly ?? 0) > (currentPlan?.price_monthly ?? 0) ? 'Confirm Upgrade' : 'Confirm Downgrade'}
            </h3>
            <div className="space-y-3 text-sm text-ink-muted mb-4">
              <p>Change from <span className="text-ink font-semibold">{currentPlan?.name}</span> to <span className="text-ink font-semibold">{confirmPlan.name}</span>?</p>
              {(confirmPlan.price_monthly ?? 0) > (currentPlan?.price_monthly ?? 0) ? (
                <div className="p-3 rounded-lg bg-accent/5 border border-accent/10">
                  <p className="text-xs text-accent-dark">Upgrade takes effect immediately. You&apos;ll be charged a prorated amount for the remainder of your billing cycle.</p>
                  <p className="text-xs text-ink-muted mt-1">Credits will be adjusted to {confirmPlan.included_credits?.toLocaleString()}.</p>
                </div>
              ) : (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-500/10">
                  <p className="text-xs text-amber-600">Downgrade takes effect at the end of your current billing cycle ({plansData?.billing_cycle_end ? formatDate(plansData.billing_cycle_end) : 'N/A'}). You&apos;ll keep your current plan features until then.</p>
                </div>
              )}
            </div>
            <div className="flex items-center justify-end gap-3">
              <button onClick={() => setConfirmPlan(null)} className="px-4 py-2 text-sm text-ink-muted hover:text-ink transition-colors">Cancel</button>
              <button
                onClick={confirmSubscribe}
                className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-6 py-2 rounded-xl transition-all"
              >
                Confirm {(confirmPlan.price_monthly ?? 0) > (currentPlan?.price_monthly ?? 0) ? 'Upgrade' : 'Downgrade'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    }>
      <SettingsContent />
    </Suspense>
  );
}
