'use client';

import React from 'react';
import PlatformLayout from '@/components/PlatformLayout';

const ENDPOINTS = [
  {
    group: 'Authentication',
    items: [
      { method: 'POST', path: '/api/auth/register', desc: 'Create an account (returns JWT + 50,000 credits)' },
      { method: 'POST', path: '/api/auth/login', desc: 'Authenticate and receive a JWT token' },
      { method: 'GET', path: '/api/auth/me', desc: 'Get the current user profile' },
    ],
  },
  {
    group: 'Compliance',
    items: [
      { method: 'POST', path: '/api/v1/transactions', desc: 'Screen a transaction through the 7-stage pipeline' },
      { method: 'GET', path: '/api/v1/transactions', desc: 'List your recent screened transactions' },
    ],
  },
  {
    group: 'Cases',
    items: [
      { method: 'POST', path: '/api/v1/cases', desc: 'Create a compliance case' },
      { method: 'GET', path: '/api/v1/cases/{id}', desc: 'Retrieve a specific case' },
      { method: 'GET', path: '/api/v1/cases', desc: 'List all cases' },
    ],
  },
  {
    group: 'Account & Billing',
    items: [
      { method: 'GET', path: '/api/v1/credits', desc: 'Get current credit balance' },
      { method: 'POST', path: '/api/v1/credits/purchase', desc: 'Buy an additional credit pack' },
      { method: 'GET', path: '/api/v1/billing/plans', desc: 'List available subscription plans' },
      { method: 'POST', path: '/api/v1/billing/subscribe', desc: 'Change your subscription plan' },
    ],
  },
  {
    group: 'Developer',
    items: [
      { method: 'GET', path: '/api/v1/rules', desc: 'List active hard-rule definitions' },
      { method: 'GET', path: '/api/v1/stats', desc: 'Aggregate dashboard analytics' },
      { method: 'POST', path: '/api/v1/keys', desc: 'Create an API key' },
      { method: 'GET', path: '/api/v1/keys', desc: 'List API keys' },
      { method: 'DELETE', path: '/api/v1/keys/{id}', desc: 'Revoke an API key' },
    ],
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET: 'text-emerald-600 bg-emerald-50',
  POST: 'text-blue-600 bg-blue-50',
  DELETE: 'text-red-600 bg-red-50',
};

export default function DocsPage() {
  return (
    <PlatformLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink">API Documentation</h1>
          <p className="text-sm text-ink-muted mt-0.5">REST API reference for the FinShield compliance engine</p>
        </div>

        {/* Base URL + auth */}
        <div className="glass p-6">
          <h3 className="text-sm font-semibold text-ink mb-3">Getting Started</h3>
          <p className="text-sm text-ink-muted mb-3">
            All endpoints are served from your API base URL. Authenticate with a Bearer token (JWT from login)
            or an API key. Interactive docs are available at <code className="text-accent-dark">/api/docs</code>.
          </p>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-xs text-ink-light w-20">Base URL</span>
              <code className="text-xs text-ink bg-bg-alt rounded px-2 py-1">http://localhost:8091/api</code>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-ink-light w-20">Auth</span>
              <code className="text-xs text-ink bg-bg-alt rounded px-2 py-1">Authorization: Bearer &lt;token&gt;</code>
            </div>
          </div>
        </div>

        {/* Example request */}
        <div className="glass p-6">
          <h3 className="text-sm font-semibold text-ink mb-3">Screen a Transaction</h3>
          <pre className="bg-bg-alt rounded-xl p-4 text-xs text-ink-secondary overflow-x-auto">
{`curl -X POST http://localhost:8091/api/v1/transactions \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "amount": 50000,
    "currency": "USD",
    "transaction_type": "international",
    "sender_name": "John Doe",
    "receiver_name": "Jane Smith",
    "destination_country": "US"
  }'`}
          </pre>
          <p className="text-xs text-ink-light mt-3">
            Response includes the decision status, risk score, credit tier consumed, per-rule results, and the
            pipeline stages executed.
          </p>
        </div>

        {/* Endpoint reference */}
        {ENDPOINTS.map((group) => (
          <div key={group.group} className="glass p-6">
            <h3 className="text-sm font-semibold text-ink mb-3">{group.group}</h3>
            <div className="space-y-2">
              {group.items.map((ep) => (
                <div key={ep.method + ep.path} className="flex items-center gap-3 py-1.5 border-b border-border-light last:border-0">
                  <span className={`shrink-0 w-16 text-center text-[10px] font-bold py-1 rounded ${METHOD_COLORS[ep.method]}`}>
                    {ep.method}
                  </span>
                  <code className="shrink-0 text-xs text-ink font-mono">{ep.path}</code>
                  <span className="text-xs text-ink-light">{ep.desc}</span>
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* Credit model */}
        <div className="glass p-6">
          <h3 className="text-sm font-semibold text-ink mb-3">Credit Model</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { tier: 'Rule Only', cost: '0.2', desc: 'No rules triggered, low risk' },
              { tier: 'Behavioral', cost: '0.5', desc: 'Anomaly monitoring invoked' },
              { tier: 'Full ML', cost: '1.0', desc: 'RAG + classifier + risk scoring' },
            ].map((c) => (
              <div key={c.tier} className="rounded-xl border border-border bg-bg-alt p-4">
                <div className="text-sm font-semibold text-ink">{c.tier}</div>
                <div className="text-2xl font-bold text-accent-dark mt-1">{c.cost}<span className="text-xs text-ink-light font-normal"> credits</span></div>
                <div className="text-[11px] text-ink-light mt-1">{c.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </PlatformLayout>
  );
}
