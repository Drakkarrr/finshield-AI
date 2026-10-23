'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { useAuth } from '@/contexts/AuthContext';
import { AdminUser, api, errorMessage } from '@/lib/api';
import { ROLES } from '@/lib/permissions';
import {
  Alert, Button, Card, EmptyState, Input, LoadingState, Modal, PageHeader, Select, StatusBadge, Table, TBody, THead,
  Td, Th, Tr, humanize,
} from '@/components/ui';
import { formatDate } from '@/lib/format';

const ROLE_OPTIONS = ROLES.map((r) => ({ value: r, label: humanize(r) }));

// One line per role, from the docstring of backend/app/permissions.py.
const ROLE_HELP: Record<string, string> = {
  analyst: 'Screen transactions, read everything in the organisation, create cases, comment and add notes.',
  investigator: 'Analyst + work cases (status, assignment, SLA sweep, aggregation) and draft filings.',
  supervisor: 'Investigator + submit / confirm filings, delete records, read configuration, audit trail and privacy requests.',
  admin: 'Supervisor + configure settings, flags, rules, models, breakers, webhooks, users and billing.',
};

function Users() {
  const { user: me } = useAuth();
  const users = useSWR('admin-users', api.listUsers);
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);

  const update = async (u: AdminUser, changes: { role?: string; is_active?: boolean }, done: string) => {
    setBusyId(u.id);
    setNotice(null);
    try {
      await api.updateUser(u.id, changes);
      await users.mutate();
      setNotice({ tone: 'success', text: done });
    } catch (e) {
      setNotice({ tone: 'danger', text: errorMessage(e, 'Update failed.') });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="People in your organisation and their roles"
        actions={<Button onClick={() => setCreating(true)}>Add user</Button>}
      />
      {notice && <Alert tone={notice.tone} onDismiss={() => setNotice(null)}>{notice.text}</Alert>}

      <Card padding="none">
        {users.isLoading && !users.data ? <LoadingState label="Loading users…" /> : users.error ? (
          <div className="p-5"><Alert tone="danger">{errorMessage(users.error)}</Alert></div>
        ) : (users.data ?? []).length === 0 ? <EmptyState title="No users." /> : (
          <Table caption="Users in your organisation">
            <THead><Th>Name</Th><Th>Email</Th><Th>Role</Th><Th>Status</Th><Th>Added</Th><Th align="right">Actions</Th></THead>
            <TBody>
              {users.data!.map((u) => (
                <Tr key={u.id}>
                  <Th scope="row">{u.first_name} {u.last_name}{u.id === me?.id && <span className="text-2xs text-ink-muted font-normal"> (you)</span>}</Th>
                  <Td className="text-xs text-ink-secondary">{u.email}</Td>
                  <Td>
                    <Select
                      label={`Role of ${u.email}`}
                      hideLabel
                      className="w-40"
                      value={u.role}
                      disabled={busyId === u.id}
                      onChange={(e) => update(u, { role: e.target.value }, `${u.email} is now ${e.target.value}.`)}
                      options={ROLE_OPTIONS}
                    />
                  </Td>
                  <Td><StatusBadge status={u.is_active ? 'active' : 'revoked'} label={u.is_active ? 'Active' : 'Deactivated'} /></Td>
                  <Td className="text-xs text-ink-muted">{u.created_at ? formatDate(u.created_at) : '—'}</Td>
                  <Td align="right">
                    <Button
                      variant={u.is_active ? 'danger' : 'secondary'}
                      size="sm"
                      loading={busyId === u.id}
                      onClick={() => update(u, { is_active: !u.is_active }, `${u.email} ${u.is_active ? 'deactivated' : 'reactivated'}.`)}
                    >
                      {u.is_active ? 'Deactivate' : 'Reactivate'}
                    </Button>
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      <Card as="section" padding="lg" aria-labelledby="roles-h">
        <h2 id="roles-h" className="text-sm font-semibold text-ink mb-3">What each role can do</h2>
        <dl className="space-y-2">
          {ROLES.map((r) => (
            <div key={r} className="grid grid-cols-1 sm:grid-cols-6 gap-1">
              <dt className="text-sm font-medium text-ink">{humanize(r)}</dt>
              <dd className="sm:col-span-5 text-sm text-ink-secondary">{ROLE_HELP[r]}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {creating && (
        <CreateUserModal
          onClose={() => setCreating(false)}
          onCreated={(u) => { setCreating(false); users.mutate(); setNotice({ tone: 'success', text: `${u.email} added as ${u.role}.` }); }}
        />
      )}
    </div>
  );
}

function CreateUserModal({ onClose, onCreated }: { onClose: () => void; onCreated: (u: AdminUser) => void }) {
  const [form, setForm] = useState({ email: '', first_name: '', last_name: '', password: '', role: 'analyst' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      onCreated(await api.createUser(form));
    } catch (err) {
      setError(errorMessage(err, 'Could not add the user.'));
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Add user" description="They sign in with this email and the initial password you set.">
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Input label="First name" value={form.first_name} onChange={set('first_name')} required />
          <Input label="Last name" value={form.last_name} onChange={set('last_name')} required />
        </div>
        <Input label="Email" type="email" autoComplete="off" value={form.email} onChange={set('email')} required />
        <Input label="Initial password" type="password" autoComplete="new-password" minLength={8} helpText="At least 8 characters. Ask them to change it after signing in." value={form.password} onChange={set('password')} required />
        <Select label="Role" value={form.role} onChange={set('role')} options={ROLE_OPTIONS} helpText={ROLE_HELP[form.role]} />
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving}>Add user</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function UsersPage() {
  return (
    <PlatformLayout>
      <Users />
    </PlatformLayout>
  );
}
