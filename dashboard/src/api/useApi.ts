// A tiny React "hook": load data from the API when a component appears - and again whenever one of
// its inputs (`deps`, e.g. the suite id or the page offset) changes. Plain fetch + useState + useEffect.
import { type DependencyList, useCallback, useEffect, useState } from "react";
import { ApiError } from "./client";

export type ApiState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; data: T };

export function useApi<T>(load: () => Promise<T>, deps: DependencyList = []): ApiState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0); // changing this number re-runs the effect ("Try again")

  useEffect(() => {
    let active = true; // ignore answers that arrive after the inputs changed or the page closed
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
    // `load` is rebuilt on every render; the real inputs are listed in `deps`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt, ...deps]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, reload };
}
