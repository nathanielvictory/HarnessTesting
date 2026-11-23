import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface RepositoryLinks {
  itemId: number;
  repositoryPath: string;
}

export function MessageMarkdown({ text, links, nodeId }: {
  text: string;
  links: RepositoryLinks;
  nodeId: number;
}) {
  return <div className="markdown">
    <Markdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      disallowedElements={['img']}
      urlTransform={(url, key) => key === 'href' ? linkUrl(url, links, nodeId) : undefined}
      components={{
        a: ({ node: _node, href, children, ...props }) => href
          ? <a {...props} href={href} target={href.startsWith('#') ? undefined : '_blank'} rel="noopener noreferrer">{children}</a>
          : <span>{children}</span>,
      }}
    >{text}</Markdown>
  </div>;
}

function linkUrl(url: string, { itemId, repositoryPath }: RepositoryLinks, nodeId: number) {
  if (/^(https?:\/\/|mailto:|#)/i.test(url)) return url;
  if (url.startsWith('//')) return undefined;

  let path: string;
  try {
    path = decodeURIComponent(url).replace(/\\/g, '/').replace(/^file:\/\//i, '');
  } catch {
    return undefined;
  }
  path = path.replace(/^\/(?=[a-z]:\/)/i, '');
  const line = path.match(/(?:#L?|:)(\d+)(?:-L?\d+|:\d+)?$/i);
  if (line) path = path.slice(0, line.index);
  if (/^[a-z][a-z\d+.-]*:/i.test(path) && !/^[a-z]:\//i.test(path)) return undefined;

  const root = repositoryPath.replace(/\\/g, '/').replace(/\/$/, '') + '/';
  const windows = /^[a-z]:\//i.test(root);
  const underRoot = windows ? path.toLowerCase().startsWith(root.toLowerCase()) : path.startsWith(root);
  if (underRoot) {
    path = path.slice(root.length);
  } else if (path.startsWith('/') || /^[a-z]:\//i.test(path)) {
    path = path.replace(/^.*\/harness-inspection-[^/]+\/checkout\//, '')
      .replace(/^.*\/worktrees\/\d+\//, '');
    if (/^[a-z]:\//i.test(path)) return undefined;
    path = path.replace(/^\//, '');
  }
  path = path.replace(/^(\.\/)+/, '');
  if (!path || path.split('/').some(part => part === '..')) return undefined;

  const query = new URLSearchParams({ path });
  const anchor = line ? `#L${Number(line[1])}` : '';
  return `/api/work-items/${itemId}/nodes/${nodeId}/file?${query}${anchor}`;
}
