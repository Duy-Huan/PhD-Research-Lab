import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

export interface BusEvent {
  seq: number;
  ts: number;
  type: string;
  client?: string;
  mission_id?: string;
  session_id?: string;
  run_id?: string;
  topic_id?: string;
  [key: string]: unknown;
}

export function useAppBus() {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = useState(false);
  const lastSeqRef = useRef<number>(0);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let active = true;

    function connect() {
      if (!active) return;
      const url = `/api/events/stream?after=${lastSeqRef.current}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.onopen = () => {
        if (!active) return;
        setIsConnected(true);
      };

      es.onmessage = (e) => {
        if (!active) return;
        try {
          const data: BusEvent = JSON.parse(e.data);
          if (data.seq && data.seq > lastSeqRef.current) {
            lastSeqRef.current = data.seq;
          }

          // F01 Remediation: Revalidate all related query keys live
          if (data.type === 'research.mission' || (data.type && data.type.startsWith('research.'))) {
            queryClient.invalidateQueries({ queryKey: ['missions'] });
            queryClient.invalidateQueries({ queryKey: ['workstreams'] });
            queryClient.invalidateQueries({ queryKey: ['teams'] });
            queryClient.invalidateQueries({ queryKey: ['claims'] });
          } else if (data.type && data.type.startsWith('aiws.')) {
            queryClient.invalidateQueries({ queryKey: ['sessions'] });
            if (data.session_id) {
              queryClient.invalidateQueries({ queryKey: ['chat', data.session_id] });
            }
          } else if (data.type && data.type.startsWith('run.')) {
            queryClient.invalidateQueries({ queryKey: ['runs'] });
            queryClient.invalidateQueries({ queryKey: ['dashboard'] });
          } else if (data.type === 'api.mutation') {
            queryClient.invalidateQueries({ queryKey: ['dashboard'] });
          }
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        setIsConnected(false);
        es.close();
        if (active) {
          setTimeout(connect, 3000);
        }
      };
    }

    connect();

    return () => {
      active = false;
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [queryClient]);

  return { isConnected };
}
