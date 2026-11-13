// A tiny React "hook": load data from the API when a component appears, and remember
// loading / error / data in state. Plain fetch + useState + useEffect - no extra library.
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./client";

export type ApiState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; data: T };

export function useApi<T>(load: () => Promise<T>): ApiState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0); // changing this number re-runs the effect

  useEffect(() => {
    let active = true; // ignore answers that arrive after the component is gone
    setState({ status: "loading" });
    load()
      .then((data) => active && setState({ status: "ready", data }))
      .catch((error: unknown) => {
        const apiError = error instanceof ApiError
          ? error
          : new ApiError(0, "client_error", error instanceof Error ? error.message : String(error));
        if (active) setState({ status: "error", error: apiError });
      });
    return () => {
      active = false;
    };
    // `load` is expected to be stable for a given page; `attempt` triggers a reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, reload };
}
