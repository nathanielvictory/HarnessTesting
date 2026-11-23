import { useEffect, useState } from 'react';
import { request } from '../../api/request';
import './usage.css';

interface UsageTotals {
  responses: number;
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  estimated_api_usd: string | null;
  unpriced_responses: number;
  unmeasured_requests: number;
  codex_responses: number;
}

const count = new Intl.NumberFormat();
const usd = new Intl.NumberFormat(undefined, {
  style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 4,
});

export function UsageSummary({ scope, id, busy }: {
  scope: 'projects' | 'work-items';
  id: number;
  busy: boolean;
}) {
  const [usage, setUsage] = useState<UsageTotals | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    if (busy) return;
    const controller = new AbortController();
    const { signal } = controller;
    request<UsageTotals>(`/${scope}/${id}/usage`, undefined, signal).then(totals => {
      if (signal.aborted) return;
      setUsage(totals);
      setUnavailable(false);
    }).catch(() => {
      if (!signal.aborted) setUnavailable(true);
    });
    return () => controller.abort();
  }, [scope, id, busy]);

  const title = scope === 'projects' ? 'Project usage' : 'Work item usage';
  const estimate = usage?.estimated_api_usd == null ? null : Number(usage.estimated_api_usd);

  return <section className="usage-summary" aria-label={title}>
    <h2>{title}</h2>
    {unavailable ? <p>Usage unavailable.</p> : usage === null ? <p>Loading usage…</p> : !usage.responses ? (
      <p>No usage recorded yet.</p>
    ) : <>
      <dl>
        <div><dt>Model responses</dt><dd>{count.format(usage.responses)}</dd></div>
        <div><dt>Input tokens</dt><dd>{count.format(usage.input_tokens)}</dd></div>
        <div><dt>Cached input tokens</dt><dd>{count.format(usage.cached_input_tokens)}</dd></div>
        <div><dt>Output tokens</dt><dd>{count.format(usage.output_tokens)}</dd></div>
        <div><dt>Estimated cost at API rates</dt><dd>{
          estimate === null ? 'Unavailable' : estimate > 0 && estimate < .0001 ? `<${usd.format(.0001)}` : usd.format(estimate)
        }</dd></div>
      </dl>
      {usage.codex_responses > 0 && <p>{count.format(usage.codex_responses)} via Codex subscription</p>}
      {usage.unpriced_responses > 0 && <p>{count.format(usage.unpriced_responses)} with incomplete pricing</p>}
      {usage.unmeasured_requests > 0 && <p>Some responses reported incomplete token usage.</p>}
    </>}
  </section>;
}
