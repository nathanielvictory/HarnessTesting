import { useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Activity } from '../Activity';
import type { WorkItemActivity } from '../types';

interface Props {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
  activity?: WorkItemActivity | null;
  onReturn?: () => void;
  followLatest?: boolean;
}

export function StepPane({ title, children, actions, activity, onReturn, followLatest = false }: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const following = useRef(followLatest);
  const scrollLimit = useRef(0);
  const [showJump, setShowJump] = useState(false);

  function syncScrollPosition() {
    const viewport = viewportRef.current;
    if (!viewport?.clientHeight) return;
    const limit = viewport.scrollHeight - viewport.clientHeight;
    // Resizing the viewport or appending content can emit a scroll event too.
    if (limit !== scrollLimit.current) return;
    following.current = limit - viewport.scrollTop <= 24;
    setShowJump(!following.current);
  }

  function jumpToLatest() {
    const viewport = viewportRef.current;
    if (!viewport) return;
    following.current = true;
    viewport.scrollTop = viewport.scrollHeight;
    setShowJump(false);
  }

  useLayoutEffect(() => {
    if (!followLatest) return;
    const viewport = viewportRef.current;
    const content = contentRef.current;
    if (!viewport || !content) return;

    function updateScroll() {
      if (!viewport?.clientHeight) return;
      scrollLimit.current = viewport.scrollHeight - viewport.clientHeight;
      if (following.current) viewport.scrollTop = viewport.scrollHeight;
      const nearLatest = scrollLimit.current - viewport.scrollTop <= 24;
      following.current = nearLatest;
      setShowJump(!nearLatest);
    }

    updateScroll();
    const observer = new ResizeObserver(updateScroll);
    observer.observe(viewport);
    observer.observe(content);
    return () => observer.disconnect();
  }, [followLatest]);

  return <section className="step-pane" aria-label={title}>
    <header className="step-header">
      <h3>{title}</h3>
      {onReturn && <button onClick={onReturn}>Back to current step</button>}
      {followLatest && <button className="jump-latest" hidden={!showJump} onClick={jumpToLatest}>↓ Jump to latest</button>}
    </header>
    <div className="step-scroll" tabIndex={0} role="region" aria-label={followLatest ? 'Conversation transcript' : 'Step content'}
      data-following={followLatest && !showJump}
      ref={viewportRef} onScroll={followLatest ? syncScrollPosition : undefined}>
      <div className="step-content" ref={contentRef}>{children}</div>
    </div>
    {(actions || activity) && <footer className="step-footer">
      <Activity activity={activity ?? null} />
      {actions}
    </footer>}
  </section>;
}
