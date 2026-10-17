import { useCallback, useEffect, useState } from "react";

export type Load<T> = { kind: "loading" } | { kind: "ready"; data: T } | { kind: "error" };

export function useLoad<T>(fn: () => Promise<T>): [Load<T>, () => void] {
  const [state, setState] = useState<Load<T>>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    fn().then(
      (data) => {
        if (live) setState({ kind: "ready", data });
      },
      () => {
        if (live) setState({ kind: "error" });
      },
    );
    return () => {
      live = false;
    };
    // fn is a stable module-level function; only a retry should re-run the request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);
  const retry = useCallback(() => {
    setState({ kind: "loading" });
    setAttempt((n) => n + 1);
  }, []);
  return [state, retry];
}
