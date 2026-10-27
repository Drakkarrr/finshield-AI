'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { useAuth, useCan } from '@/contexts/AuthContext';
import { api, errorMessage, ChangeRequest } from '@/lib/api';
import {
  Alert, Badge, Button, Card, LoadingState, Modal, PageHeader, Textarea,
} from '@/components/ui';
import { formatDateTime } from '@/lib/format';

function Approvals() {
  const { user } = useAuth();
  const can = useCan();
  const canApprove = can(['POST', '/api/v1/change-requests/{request_id}/approve']);
  const [statusFilter, setStatusFilter] = useState<'pending' | 'approved' | 'rejected' | ''>('pending');
  const changeRequests = useSWR(
    ['change-requests', statusFilter],
    () => api.listChangeRequests(statusFilter || undefined),
  );
  const users = useSWR(['admin-users'], () => api.listUsers());
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [processing, setProcessing] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<ChangeRequest | null>(null);

  const list = changeRequests.data ?? [];
  const userMap = new Map(users.data?.map((u) => [u.id, `${u.first_name} ${u.last_name}`]));

  const handleApprove = async (id: string, reason: string) => {
    setProcessing(id);
    setError('');
    setSuccess('');
    try {
      await api.approveChangeRequest(id, reason || undefined);
      setSuccess('Change request approved successfully.');
      await changeRequests.mutate();
      setReviewing(null);
    } catch (err) {
      setError(errorMessage(err, 'Failed to approve change request.'));
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (id: string, reason: string) => {
    setProcessing(id);
    setError('');
    setSuccess('');
    try {
      await api.rejectChangeRequest(id, reason);
      setSuccess('Change request rejected.');
      await changeRequests.mutate();
      setReviewing(null);
    } catch (err) {
      setError(errorMessage(err, 'Failed to reject change request.'));
    } finally {
      setProcessing(null);
    }
  };

  const getStatusTone = (status: string): 'info' | 'success' | 'danger' | 'warning' | 'neutral' | 'accent' => {
    switch (status) {
      case 'pending': return 'warning';
      case 'approved': return 'success';
      case 'rejected': return 'danger';
      default: return 'neutral';
    }
  };

  const getChangeTypeLabel = (type: string): string => {
    switch (type) {
      case 'rule_disable': return 'Rule disable';
      case 'rule_override': return 'Rule parameter override';
      case 'model_promote': return 'Model promotion';
      default: return type;
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Change requests"
        description="Review and approve proposed changes to compliance rules and models"
        actions={
          <div className="flex gap-2">
            {(['', 'pending', 'approved', 'rejected'] as const).map((status) => (
              <Button
                key={status || 'all'}
                variant={statusFilter === status ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setStatusFilter(status)}
              >
                {status || 'All'}
              </Button>
            ))}
          </div>
        }
      />

      {!canApprove && (
        <Alert tone="info">
          Only supervisors and admins can approve or reject change requests.
        </Alert>
      )}

      {error && <Alert tone="danger" onDismiss={() => setError('')}>{error}</Alert>}
      {success && <Alert tone="info" onDismiss={() => setSuccess('')}>{success}</Alert>}

      {changeRequests.isLoading && !changeRequests.data ? (
        <Card><LoadingState label="Loading change requests…" /></Card>
      ) : changeRequests.error ? (
        <Alert tone="danger" title="Could not load change requests">
          {errorMessage(changeRequests.error)}
        </Alert>
      ) : list.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-secondary text-center py-8">
            No {statusFilter || ''} change requests.
          </p>
        </Card>
      ) : (
        <ul className="space-y-3">
          {list.map((cr) => (
            <li key={cr.id}>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={getStatusTone(cr.status)}>{cr.status}</Badge>
                    <span className="text-sm font-semibold text-ink">
                      {getChangeTypeLabel(cr.change_type)}
                    </span>
                    <span className="font-mono text-xs text-ink-muted">{cr.resource_id}</span>
                  </div>
                  {canApprove && cr.status === 'pending' && cr.proposed_by !== user?.id && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setReviewing(cr)}
                      disabled={processing === cr.id}
                    >
                      Review
                    </Button>
                  )}
                </div>
                <div className="space-y-2 text-xs text-ink-muted">
                  <p>
                    <span className="text-ink-secondary">Proposed by:</span> {userMap.get(cr.proposed_by) ?? cr.proposed_by}
                  </p>
                  <p>
                    <span className="text-ink-secondary">Created:</span> {formatDateTime(cr.created_at)}
                  </p>
                  {cr.resolved_at && (
                    <p>
                      <span className="text-ink-secondary">Resolved:</span> {formatDateTime(cr.resolved_at)}
                    </p>
                  )}
                  {cr.approved_by && (
                    <p>
                      <span className="text-ink-secondary">Approved by:</span> {userMap.get(cr.approved_by) ?? cr.approved_by}
                    </p>
                  )}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {reviewing && (
        <ReviewModal
          changeRequest={reviewing}
          onClose={() => setReviewing(null)}
          onApprove={(reason) => handleApprove(reviewing.id, reason)}
          onReject={(reason) => handleReject(reviewing.id, reason)}
          processing={processing === reviewing.id}
        />
      )}
    </div>
  );
}

function ReviewModal({
  changeRequest,
  onClose,
  onApprove,
  onReject,
  processing,
}: {
  changeRequest: ChangeRequest;
  onClose: () => void;
  onApprove: (reason: string) => void;
  onReject: (reason: string) => void;
  processing: boolean;
}) {
  const [reason, setReason] = useState('');
  const [action, setAction] = useState<'approve' | 'reject' | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (action === 'approve') {
      onApprove(reason);
    } else if (action === 'reject') {
      if (!reason.trim()) {
        alert('Please provide a reason for rejection.');
        return;
      }
      onReject(reason);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Review change request"
      description={`${changeRequest.change_type} for ${changeRequest.resource_id}`}
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-ink">Proposed changes</h3>
          <pre className="bg-surface-secondary p-3 rounded text-xs overflow-auto max-h-64">
            {JSON.stringify(changeRequest.payload, null, 2)}
          </pre>
        </div>

        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-ink">Your decision</h3>
          <Textarea
            label="Reason (required for rejection)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Explain your decision..."
          />
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose} disabled={processing}>
            Cancel
          </Button>
          <Button
            variant="danger"
            type="submit"
            loading={processing && action === 'reject'}
            onClick={() => setAction('reject')}
            disabled={processing}
          >
            Reject
          </Button>
          <Button
            variant="primary"
            type="submit"
            loading={processing && action === 'approve'}
            onClick={() => setAction('approve')}
            disabled={processing}
          >
            Approve
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default function ApprovalsPage() {
  return (
    <PlatformLayout>
      <Approvals />
    </PlatformLayout>
  );
}
