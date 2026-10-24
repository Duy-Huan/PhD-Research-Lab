import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
  className?: string;
  style?: React.CSSProperties;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  className = '',
  style,
}) => {
  if (!content) return null;

  return (
    <div
      className={`markdown-body prose ${className}`}
      style={{
        lineHeight: 1.65,
        fontSize: 'inherit',
        color: 'inherit',
        wordBreak: 'break-word',
        fontFamily: 'var(--prose)',
        ...style,
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ node, ...props }) => (
            <div style={{ overflowX: 'auto', margin: '10px 0', maxWidth: '100%' }}>
              <table
                style={{
                  borderCollapse: 'collapse',
                  width: '100%',
                  fontSize: 12.5,
                  textAlign: 'left',
                  border: '1px solid var(--line-2)',
                  borderRadius: 6,
                  overflow: 'hidden',
                }}
                {...props}
              />
            </div>
          ),
          thead: ({ node, ...props }) => (
            <thead
              style={{
                background: 'var(--bg-2)',
                borderBottom: '2px solid var(--line-2)',
                fontWeight: 600,
              }}
              {...props}
            />
          ),
          th: ({ node, ...props }) => (
            <th
              style={{
                padding: '8px 12px',
                border: '1px solid var(--line)',
                color: 'var(--fg)',
              }}
              {...props}
            />
          ),
          td: ({ node, ...props }) => (
            <td
              style={{
                padding: '7px 12px',
                border: '1px solid var(--line)',
                fontSize: 12,
              }}
              {...props}
            />
          ),
          h1: ({ node, ...props }) => (
            <h1
              style={{
                fontSize: '1.4em',
                fontWeight: 700,
                marginTop: '1em',
                marginBottom: '0.4em',
                letterSpacing: '-0.02em',
                borderBottom: '1px solid var(--line)',
                paddingBottom: 4,
              }}
              {...props}
            />
          ),
          h2: ({ node, ...props }) => (
            <h2
              style={{
                fontSize: '1.25em',
                fontWeight: 600,
                marginTop: '0.9em',
                marginBottom: '0.35em',
                letterSpacing: '-0.01em',
              }}
              {...props}
            />
          ),
          h3: ({ node, ...props }) => (
            <h3
              style={{
                fontSize: '1.1em',
                fontWeight: 600,
                marginTop: '0.8em',
                marginBottom: '0.3em',
              }}
              {...props}
            />
          ),
          h4: ({ node, ...props }) => (
            <h4
              style={{
                fontSize: '1em',
                fontWeight: 600,
                marginTop: '0.7em',
                marginBottom: '0.25em',
              }}
              {...props}
            />
          ),
          p: ({ node, ...props }) => (
            <p style={{ margin: '0.4em 0', lineHeight: 1.6 }} {...props} />
          ),
          ul: ({ node, ...props }) => (
            <ul
              style={{
                paddingLeft: '1.4em',
                margin: '0.4em 0',
                display: 'flex',
                flexDirection: 'column',
                gap: 3,
              }}
              {...props}
            />
          ),
          ol: ({ node, ...props }) => (
            <ol
              style={{
                paddingLeft: '1.4em',
                margin: '0.4em 0',
                display: 'flex',
                flexDirection: 'column',
                gap: 3,
              }}
              {...props}
            />
          ),
          li: ({ node, ...props }) => (
            <li style={{ margin: '2px 0' }} {...props} />
          ),
          blockquote: ({ node, ...props }) => (
            <blockquote
              style={{
                borderLeft: '3px solid var(--accent)',
                padding: '4px 12px',
                margin: '8px 0',
                background: 'var(--accent-soft)',
                borderRadius: '0 6px 6px 0',
                fontStyle: 'italic',
              }}
              {...props}
            />
          ),
          code: ({ node, className, children, ...props }) => {
            const isInline = !className && !String(children).includes('\n');
            if (isInline) {
              return (
                <code
                  style={{
                    background: 'var(--bg-2)',
                    color: 'var(--accent)',
                    padding: '2px 5px',
                    borderRadius: 4,
                    fontSize: '0.9em',
                    fontFamily: 'var(--mono)',
                    border: '1px solid var(--line-2)',
                  }}
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <pre
                style={{
                  background: 'var(--panel-2, #18181b)',
                  color: '#e4e4e7',
                  padding: '10px 14px',
                  borderRadius: 8,
                  fontSize: 12,
                  fontFamily: 'var(--mono)',
                  overflowX: 'auto',
                  margin: '8px 0',
                  border: '1px solid var(--line-2)',
                }}
              >
                <code className={className} {...props}>
                  {children}
                </code>
              </pre>
            );
          },
          a: ({ node, ...props }) => (
            <a
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: 'var(--accent)',
                textDecoration: 'underline',
                textUnderlineOffset: 3,
              }}
              {...props}
            />
          ),
          hr: () => (
            <hr
              style={{
                border: 'none',
                borderTop: '1px solid var(--line-2)',
                margin: '12px 0',
              }}
            />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
