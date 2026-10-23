import Link from 'next/link';

export default function Forbidden() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-danger mb-4">403</h1>
        <h2 className="text-2xl font-semibold text-ink mb-2">Access Forbidden</h2>
        <p className="text-ink-muted mb-6">
          You don&apos;t have permission to access this resource.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Link
            href="/dashboard"
            className="bg-accent hover:bg-accent-dark text-white font-semibold px-6 py-2.5 rounded-xl transition-all"
          >
            Go to Dashboard
          </Link>
          <Link
            href="/login"
            className="bg-bg hover:bg-bg-alt border border-border text-ink-secondary font-medium px-6 py-2.5 rounded-xl transition-all"
          >
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}
