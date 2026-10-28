import React from 'react';
import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import { renderWithProviders } from '../../test/test-utils';
import { HarnessNodeComponent } from './HarnessNodeComponent';

// FQC-UI-QA-663: on Linux fonts the node badge is shortened with an ellipsis (VIS-CLIPPED in CI), so the full name
// must stay readable as a tooltip.
describe('HarnessNodeComponent', () => {
  it('gives a shortened badge its full name as a tooltip', () => {
    renderWithProviders(
      <ReactFlowProvider>
        <HarnessNodeComponent id="n1" selected={false} data={{ tool: 'phdlab_research_harness', label: 'Score' } as never} />
      </ReactFlowProvider>,
    );
    const badge = screen.getByText('PhDLab Research Harness');
    expect(badge).toHaveStyle({ textOverflow: 'ellipsis' });
    expect(badge).toHaveAttribute('title', 'PhDLab Research Harness');
  });
});
