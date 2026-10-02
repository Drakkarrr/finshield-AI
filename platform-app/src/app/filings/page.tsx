'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, Filing } from '@/lib/api';
import { formatDateTime, timeAgo } from '@/lib/format';

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  under_review: 'bg-blue-100 text-blue-700',
  submitted: 'bg-yellow-100 text-yellow-700',
  confirmed: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
};

const FILING_TYPE_STYLES: Record<string, string> = {
  SAR: 'bg-purple-100 text-purple-700',
  STR: 'bg-indigo-100 text-indigo-700',
};

export default function FilingsPage() {
  const [filings, setFilings] = useState<Filing[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFiling, setSelectedFiling] = useState<Filing | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterType, setFilterType] = useState<string>('');

  useEffect(() => {
    loadFilings();
  }, [filterStatus, filterType]);

  async function loadFilings() {
    try {
      setLoading(true);
      const data = await api.listFilings(filterStatus || undefined, filterType || undefined);
      setFilings(data);
    } catch (err) {
      console.error('Failed to load filings:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleViewFiling(filing: Filing) {
    setSelectedFiling(filing);
    setShowDetail(true);
  }

  async function handleUpdateStatus(filingId: string, newStatus: string) {
    try {
      await api.updateFiling(filingId, { status: newStatus });
      await loadFilings();
      if (selectedFiling?.id === filingId) {
        const updated = filings.find(f => f.id === filingId);
        if (updated) setSelectedFiling(updated);
      }
    } catch (err) {
      console.error('Failed to update filing:', err);
    }
  }

  function getDaysUntilDeadline(deadline: string | null): number | null {
    if (!deadline) return null;
    const now = new Date();
    const deadlineDate = new Date(deadline);
    const diffMs = deadlineDate.getTime() - now.getTime();
    return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Regulatory Filings</h1>
          <p className="mt-1 text-sm text-gray-600">
            SAR/STR filings for confirmed suspicious activity
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="under_review">Under Review</option>
          <option value="submitted">Submitted</option>
          <option value="confirmed">Confirmed</option>
          <option value="rejected">Rejected</option>
        </select>

        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All Types</option>
          <option value="SAR">SAR</option>
          <option value="STR">STR</option>
        </select>
      </div>

      {/* Filings List */}
      {loading ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <p className="text-gray-500">Loading filings...</p>
        </div>
      ) : filings.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <p className="text-gray-500">No filings found</p>
          <p className="mt-2 text-sm text-gray-400">
            Filings are created when cases are resolved as suspicious
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filings.map((filing) => {
            const daysUntilDeadline = getDaysUntilDeadline(filing.deadline);
            const isOverdue = daysUntilDeadline !== null && daysUntilDeadline < 0;
            const isUrgent = daysUntilDeadline !== null && daysUntilDeadline >= 0 && daysUntilDeadline <= 7;

            return (
              <div
                key={filing.id}
                className="rounded-lg border border-gray-200 bg-white p-4 transition-shadow hover:shadow-md"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${FILING_TYPE_STYLES[filing.filing_type]}`}>
                        {filing.filing_type}
                      </span>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[filing.status]}`}>
                        {filing.status.replace('_', ' ')}
                      </span>
                      {isOverdue && (
                        <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
                          OVERDUE
                        </span>
                      )}
                      {isUrgent && !isOverdue && (
                        <span className="inline-flex items-center rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-medium text-yellow-700">
                          DUE SOON
                        </span>
                      )}
                    </div>

                    <div className="mt-2 flex items-center gap-4 text-sm text-gray-600">
                      <span>Case: {filing.case_id.substring(0, 8)}...</span>
                      <span>•</span>
                      <span>Created {timeAgo(filing.created_at)}</span>
                      {filing.deadline && (
                        <>
                          <span>•</span>
                          <span className={isOverdue ? 'text-red-600 font-medium' : isUrgent ? 'text-yellow-600 font-medium' : ''}>
                            Deadline: {formatDateTime(filing.deadline)}
                            {daysUntilDeadline !== null && (
                              <span className="ml-1">
                                ({daysUntilDeadline < 0 ? `${Math.abs(daysUntilDeadline)} days overdue` : `${daysUntilDeadline} days left`})
                              </span>
                            )}
                          </span>
                        </>
                      )}
                    </div>

                    {filing.narrative && (
                      <p className="mt-2 text-sm text-gray-700 line-clamp-2">
                        {filing.narrative}
                      </p>
                    )}

                    {filing.reference_number && (
                      <p className="mt-2 text-xs text-gray-500">
                        Reference: {filing.reference_number}
                      </p>
                    )}
                  </div>

                  <div className="ml-4">
                    <button
                      onClick={() => handleViewFiling(filing)}
                      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                    >
                      View Details
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Detail Modal */}
      {showDetail && selectedFiling && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-white p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">
                Filing Details - {selectedFiling.filing_type}
              </h2>
              <button
                onClick={() => setShowDetail(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              {/* Status and Type */}
              <div className="flex items-center gap-2">
                <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${FILING_TYPE_STYLES[selectedFiling.filing_type]}`}>
                  {selectedFiling.filing_type}
                </span>
                <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${STATUS_STYLES[selectedFiling.status]}`}>
                  {selectedFiling.status.replace('_', ' ')}
                </span>
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div>
                  <p className="text-xs text-gray-500">Case ID</p>
                  <p className="text-sm font-medium text-gray-900">{selectedFiling.case_id}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Created</p>
                  <p className="text-sm font-medium text-gray-900">{formatDateTime(selectedFiling.created_at)}</p>
                </div>
                {selectedFiling.deadline && (
                  <div>
                    <p className="text-xs text-gray-500">Deadline</p>
                    <p className="text-sm font-medium text-gray-900">{formatDateTime(selectedFiling.deadline)}</p>
                  </div>
                )}
                {selectedFiling.reference_number && (
                  <div>
                    <p className="text-xs text-gray-500">Reference Number</p>
                    <p className="text-sm font-medium text-gray-900">{selectedFiling.reference_number}</p>
                  </div>
                )}
                {selectedFiling.submitted_at && (
                  <div>
                    <p className="text-xs text-gray-500">Submitted</p>
                    <p className="text-sm font-medium text-gray-900">{formatDateTime(selectedFiling.submitted_at)}</p>
                  </div>
                )}
                {selectedFiling.confirmed_at && (
                  <div>
                    <p className="text-xs text-gray-500">Confirmed</p>
                    <p className="text-sm font-medium text-gray-900">{formatDateTime(selectedFiling.confirmed_at)}</p>
                  </div>
                )}
              </div>

              {/* Narrative */}
              <div>
                <label className="block text-sm font-medium text-gray-700">Narrative</label>
                <div className="mt-1 rounded-lg border border-gray-300 bg-white p-3">
                  <p className="whitespace-pre-wrap text-sm text-gray-900">
                    {selectedFiling.narrative || 'No narrative provided'}
                  </p>
                </div>
              </div>

              {/* Structured Data */}
              {selectedFiling.structured_data && (
                <div>
                  <label className="block text-sm font-medium text-gray-700">Transaction Details</label>
                  <div className="mt-1 rounded-lg border border-gray-300 bg-white p-3">
                    <pre className="overflow-x-auto text-xs text-gray-700">
                      {JSON.stringify(selectedFiling.structured_data, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 border-t border-gray-200 pt-4">
                {selectedFiling.status === 'draft' && (
                  <>
                    <button
                      onClick={async () => {
                        await handleUpdateStatus(selectedFiling.id, 'under_review');
                        setShowDetail(false);
                      }}
                      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                    >
                      Submit for Review
                    </button>
                    <button
                      onClick={async () => {
                        await api.deleteFiling(selectedFiling.id);
                        await loadFilings();
                        setShowDetail(false);
                      }}
                      className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
                    >
                      Delete Draft
                    </button>
                  </>
                )}
                {selectedFiling.status === 'under_review' && (
                  <button
                    onClick={async () => {
                      await handleUpdateStatus(selectedFiling.id, 'submitted');
                      setShowDetail(false);
                    }}
                    className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                  >
                    Mark as Submitted
                  </button>
                )}
                {selectedFiling.status === 'submitted' && (
                  <button
                    onClick={async () => {
                      await handleUpdateStatus(selectedFiling.id, 'confirmed');
                      setShowDetail(false);
                    }}
                    className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                  >
                    Confirm Filing
                  </button>
                )}
                <button
                  onClick={() => setShowDetail(false)}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
