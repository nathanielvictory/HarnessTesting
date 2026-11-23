import { Conversation } from '../Conversation';
import type { StepProps } from './types';

export function ImplementationStep({ node, done, busy, perform }: StepProps) {
  return <>
    <h3>Implementation</h3>
    {node.branch_ref && <p className="revision"><code>{node.branch_ref}</code></p>}
    <Conversation node={node} />
    {!done && <button className="primary" disabled={busy} onClick={() => perform({ type: 'implement' })}>
      Run implementation
    </button>}
  </>;
}
