import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MarkdownRenderer } from './MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('returns null when content is empty', () => {
    const { container } = render(<MarkdownRenderer content="" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders headings from h1 to h4', () => {
    const markdown = `
# Heading 1
## Heading 2
### Heading 3
#### Heading 4
`;
    render(<MarkdownRenderer content={markdown} />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Heading 1');
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Heading 2');
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent('Heading 3');
    expect(screen.getByRole('heading', { level: 4 })).toHaveTextContent('Heading 4');
  });

  it('renders markdown tables properly with thead, th, and td', () => {
    const markdown = `
| Metric | Value | Status |
| --- | --- | --- |
| Accuracy | 98.5% | Pass |
| Latency | 12ms | Optimal |
`;
    render(<MarkdownRenderer content={markdown} />);
    expect(screen.getByText('Metric')).toBeInTheDocument();
    expect(screen.getByText('Accuracy')).toBeInTheDocument();
    expect(screen.getByText('98.5%')).toBeInTheDocument();
    expect(screen.getByText('Latency')).toBeInTheDocument();
  });

  it('renders lists, blockquotes, horizontal rules, and links', () => {
    const markdown = `
> This is an important scientific finding.

- Unordered item 1
- Unordered item 2

1. Ordered item 1
2. Ordered item 2

---

Read more at [PhD Research Lab](https://phdlab.ai).
`;
    render(<MarkdownRenderer content={markdown} />);
    expect(screen.getByText(/This is an important scientific finding/i)).toBeInTheDocument();
    expect(screen.getByText('Unordered item 1')).toBeInTheDocument();
    expect(screen.getByText('Ordered item 1')).toBeInTheDocument();
    
    const link = screen.getByRole('link', { name: 'PhD Research Lab' });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', 'https://phdlab.ai');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('renders inline code and code block with pre tag', () => {
    const markdown = `
Use the function \`calculate_loss()\` to compute gradients.

\`\`\`python
def train_step(data):
    loss = calculate_loss(data)
    return loss
\`\`\`
`;
    render(<MarkdownRenderer content={markdown} />);
    expect(screen.getByText('calculate_loss()')).toBeInTheDocument();
    expect(screen.getByText(/def train_step/i)).toBeInTheDocument();
  });
});
