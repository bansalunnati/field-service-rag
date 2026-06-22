"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { AlertTriangle, Info } from "lucide-react";
import { Button } from "@/components/ui/button";

type DialogKind = "confirm" | "alert";

interface DialogOptions {
  kind: DialogKind;
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

interface DialogState extends DialogOptions {
  resolve: (value: boolean) => void;
}

interface ConfirmDialogContextValue {
  confirm: (message: string, opts?: Partial<DialogOptions>) => Promise<boolean>;
  notify: (message: string, opts?: Partial<DialogOptions>) => Promise<void>;
}

const ConfirmDialogContext = createContext<ConfirmDialogContextValue | null>(null);

export function ConfirmDialogProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<DialogState | null>(null);

  const confirm = useCallback((message: string, opts?: Partial<DialogOptions>) => {
    return new Promise<boolean>((resolve) => {
      setState({ kind: "confirm", message, resolve, ...opts });
    });
  }, []);

  const notify = useCallback((message: string, opts?: Partial<DialogOptions>) => {
    return new Promise<void>((resolve) => {
      setState({ kind: "alert", message, resolve: () => resolve(), ...opts });
    });
  }, []);

  const close = (result: boolean) => {
    state?.resolve(result);
    setState(null);
  };

  return (
    <ConfirmDialogContext.Provider value={{ confirm, notify }}>
      {children}
      {state && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={() => close(false)}
        >
          <div
            className="w-full max-w-sm rounded-xl bg-card text-card-foreground ring-1 ring-foreground/10 shadow-xl p-5 mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3">
              <div
                className={`flex size-9 shrink-0 items-center justify-center rounded-full ${
                  state.destructive
                    ? "bg-destructive/10 text-destructive"
                    : "bg-primary/10 text-primary"
                }`}
              >
                {state.destructive ? <AlertTriangle size={18} /> : <Info size={18} />}
              </div>
              <div className="min-w-0 pt-0.5">
                {state.title && (
                  <h3 className="font-semibold text-sm mb-1">{state.title}</h3>
                )}
                <p className="text-sm text-muted-foreground">{state.message}</p>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              {state.kind === "confirm" && (
                <Button variant="outline" size="sm" onClick={() => close(false)}>
                  {state.cancelLabel ?? "Cancel"}
                </Button>
              )}
              <Button
                variant={state.destructive ? "destructive" : "default"}
                size="sm"
                onClick={() => close(true)}
              >
                {state.confirmLabel ?? (state.kind === "confirm" ? "Confirm" : "OK")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </ConfirmDialogContext.Provider>
  );
}

export function useConfirmDialog() {
  const ctx = useContext(ConfirmDialogContext);
  if (!ctx) {
    throw new Error("useConfirmDialog must be used within a ConfirmDialogProvider");
  }
  return ctx;
}
