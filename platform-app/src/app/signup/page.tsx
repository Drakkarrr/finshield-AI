'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import AuthShell from '@/components/AuthShell';
import { Input, Button, Alert } from '@/components/ui';
import { errorMessage } from '@/lib/api';

export default function SignupPage() {
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', company: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { signup } = useAuth();
  const router = useRouter();

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await signup(form);
      router.push('/dashboard');
    } catch (err) {
      setError(errorMessage(err, 'Sign-up failed. Please try again.'));
      setLoading(false);
    }
  };

  return (
    <AuthShell
      headline="Start screening in"
      accent="minutes, not months."
      lead="14-day free trial with 1,000 Starter credits. No card required."
      points={['1,000 screening credits', '14-day Starter access', 'Rule + behavioral pipeline', 'API keys for integration']}
    >
      <h1 className="text-2xl font-bold text-ink mb-1">Create your account</h1>
      <p className="text-ink-muted mb-8">You become the admin of a new organisation.</p>

      {error && <Alert tone="danger" className="mb-4">{error}</Alert>}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Input label="First name" value={form.firstName} onChange={update('firstName')} required autoComplete="given-name" />
          <Input label="Last name" value={form.lastName} onChange={update('lastName')} required autoComplete="family-name" />
        </div>
        <Input label="Work email" type="email" value={form.email} onChange={update('email')} required autoComplete="email" />
        <Input label="Company" value={form.company} onChange={update('company')} required autoComplete="organization" />
        <Input
          label="Password"
          type="password"
          value={form.password}
          onChange={update('password')}
          minLength={8}
          required
          autoComplete="new-password"
          helpText="At least 8 characters."
        />
        <Button type="submit" className="w-full" size="lg" loading={loading}>
          {loading ? 'Creating account…' : 'Create account'}
        </Button>
      </form>

      <p className="text-center text-ink-muted text-sm mt-6">
        Already have an account? <Link href="/login" className="font-medium">Sign in</Link>
      </p>
    </AuthShell>
  );
}
