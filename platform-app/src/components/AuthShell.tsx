import React from 'react';

const SHIELD = 'M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z';

function Logo({ dark }: { dark?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className={`w-10 h-10 rounded-xl flex items-center justify-center ${dark ? 'bg-accent/15' : 'bg-navy'}`}>
        <svg className="w-6 h-6 text-accent" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d={SHIELD} />
        </svg>
      </span>
      <span className={`text-xl font-bold ${dark ? 'text-white' : 'text-ink'}`}>FinShield AI</span>
    </div>
  );
}

/** Two-column sign-in / sign-up layout: brand panel (large screens) + form column. */
export default function AuthShell({ headline, accent, lead, points, children }: {
  headline: string; accent: string; lead: string; points: string[]; children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 bg-navy items-center justify-center p-12">
        <div className="max-w-md">
          <div className="mb-8"><Logo dark /></div>
          <p className="text-3xl font-bold text-white mb-4">
            {headline}<br /><span className="text-accent">{accent}</span>
          </p>
          <p className="text-white/70 text-lg mb-8">{lead}</p>
          <ul className="space-y-3">
            {points.map((f) => (
              <li key={f} className="flex items-center gap-3 text-white/80 text-sm">
                <svg className="w-4 h-4 text-accent shrink-0" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                {f}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <main className="flex-1 flex items-center justify-center p-8 bg-bg">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8"><Logo /></div>
          {children}
        </div>
      </main>
    </div>
  );
}
