'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

export default function SignupPage() {
  const [form, setForm] = React.useState({ firstName: '', lastName: '', email: '', company: '', password: '' });
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const { signup } = useAuth();
  const router = useRouter();

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await signup(form);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Signup failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left — Brand panel (dark navy) */}
      <div className="hidden lg:flex lg:w-1/2 bg-navy items-center justify-center p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_30%,rgba(200,135,14,0.06),transparent_60%)]" />
        <div className="relative max-w-md">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-accent/15 rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </div>
            <span className="text-white text-xl font-bold">FinShield AI</span>
          </div>
          <h1 className="text-3xl font-bold text-white mb-4">
            Start screening in<br />
            <span className="text-accent">minutes, not months.</span>
          </h1>
          <p className="text-white/60 text-lg mb-8">
            14-day free trial with 1,000 Starter credits. No credit card required. Upgrade when ready.
          </p>
          <div className="bg-white/[0.05] border border-white/[0.08] rounded-2xl p-6">
            <div className="text-sm text-white/50 mb-3">Free trial includes:</div>
            <div className="space-y-2.5">
              {[
                '1,000 screening credits',
                '14-day full Starter access',
                'Rule + behavioral pipeline',
                '1 API key for integration',
              ].map((f) => (
                <div key={f} className="flex items-center gap-2.5">
                  <svg className="w-4 h-4 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  <span className="text-white/70 text-sm">{f}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Right — Form (light) */}
      <div className="flex-1 flex items-center justify-center p-8 bg-bg">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-navy rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </div>
            <span className="text-ink font-bold">FinShield AI</span>
          </div>

          <h2 className="text-2xl font-bold text-ink mb-1">Create your account</h2>
          <p className="text-ink-muted mb-8">14-day free trial · 1,000 credits · No card required</p>

          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="signup-first" className="block text-sm font-medium text-ink-secondary mb-1.5">First name</label>
                <input id="signup-first" type="text" value={form.firstName} onChange={update('firstName')} placeholder="John" className="w-full bg-white border border-border rounded-xl px-4 py-3 text-sm text-ink placeholder-ink-light transition-all" required aria-required="true" autoComplete="given-name" />
              </div>
              <div>
                <label htmlFor="signup-last" className="block text-sm font-medium text-ink-secondary mb-1.5">Last name</label>
                <input id="signup-last" type="text" value={form.lastName} onChange={update('lastName')} placeholder="Doe" className="w-full bg-white border border-border rounded-xl px-4 py-3 text-sm text-ink placeholder-ink-light transition-all" required aria-required="true" autoComplete="family-name" />
              </div>
            </div>
            <div>
              <label htmlFor="signup-email" className="block text-sm font-medium text-ink-secondary mb-1.5">Work email</label>
              <input id="signup-email" type="email" value={form.email} onChange={update('email')} placeholder="john@company.com" className="w-full bg-white border border-border rounded-xl px-4 py-3 text-sm text-ink placeholder-ink-light transition-all" required aria-required="true" autoComplete="email" />
            </div>
            <div>
              <label htmlFor="signup-company" className="block text-sm font-medium text-ink-secondary mb-1.5">Company</label>
              <input id="signup-company" type="text" value={form.company} onChange={update('company')} placeholder="Acme Financial" className="w-full bg-white border border-border rounded-xl px-4 py-3 text-sm text-ink placeholder-ink-light transition-all" required aria-required="true" autoComplete="organization" />
            </div>
            <div>
              <label htmlFor="signup-password" className="block text-sm font-medium text-ink-secondary mb-1.5">Password</label>
              <input id="signup-password" type="password" value={form.password} onChange={update('password')} placeholder="Min 8 characters" className="w-full bg-white border border-border rounded-xl px-4 py-3 text-sm text-ink placeholder-ink-light transition-all" minLength={8} required aria-required="true" autoComplete="new-password" />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-accent hover:bg-accent-dark text-white font-semibold py-3 rounded-xl transition-all duration-200 disabled:opacity-50"
            >
              {loading ? 'Creating account...' : 'Create Account — Free'}
            </button>
          </form>

          <p className="text-center text-ink-muted text-sm mt-6">
            Already have an account?{' '}
            <Link href="/login" className="text-accent hover:text-accent-dark font-medium transition-colors">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
