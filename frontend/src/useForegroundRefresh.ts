import { useEffect, useRef } from 'react';

export function useForegroundRefresh(refresh: () => Promise<void>) {
  const lastAttempt = useRef(Date.now());
  const pending = useRef<Promise<void> | null>(null);
  useEffect(() => {
    const onReturn = () => {
      if (document.visibilityState !== 'visible' || pending.current || Date.now() - lastAttempt.current < 30_000) return;
      lastAttempt.current = Date.now();
      pending.current = refresh().catch(() => {}).finally(() => { pending.current = null; });
    };
    window.addEventListener('focus', onReturn);
    document.addEventListener('visibilitychange', onReturn);
    return () => {
      window.removeEventListener('focus', onReturn);
      document.removeEventListener('visibilitychange', onReturn);
    };
  }, [refresh]);
}
