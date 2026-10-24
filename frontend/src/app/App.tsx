import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from '../shell/AppShell';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 5000,
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
};
