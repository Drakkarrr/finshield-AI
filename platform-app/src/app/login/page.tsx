'use client';

import React, { Suspense, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import AuthShell from '@/components/AuthShell';
import { Input, Button, Alert } from '@/components/ui';
import { errorMessage } from '@/lib/api';
import { safeRedirect } from '@/lib/routes';

function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();
  const params = useSearchParams();
  const expired = params.get('expired') === '1';
  const target = safeRedirect(params.get('redirect'));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await login(email, password);
      // Full navigation so the proxy sees the new session cookie on the next request.
      window.location.assign(target);
    } catch (err) {
      setError(errorMessage(err, 'Sign-in failed. Please try again.'));
      setLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-2xl font-bold text-ink mb-1">Welcome back</h1>
      <p className="text-ink-muted mb-8">Sign in to your compliance workspace</p>

      {expired && !error && (
        <Alert tone="info" className="mb-4">Your session expired. Sign in again to continue where you left off.</Alert>
      )}
      {error && <Alert tone="danger" className="mb-4">{error}</Alert>}

      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          required
          autoComplete="email"
        />
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
        />
        <Button type="submit" className="w-full" size="lg" loading={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>

      <p className="text-center text-ink-muted text-sm mt-6">
        Don&apos;t have an account?{' '}
        <Link href="/signup" className="font-medium">Start free trial</Link>
      </p>
    </>
  );
}

export default function LoginPage() {
  return (
    <AuthShell
      headline="Transaction compliance,"
      accent="explained."
      lead="Screen transactions with deterministic, explainable risk scoring and run the case-to-filing workflow in one place."
      points={['Rule, list, behavioral and model stages', 'Every decision carries its reasons', 'Tamper-evident audit trail']}
    >
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
