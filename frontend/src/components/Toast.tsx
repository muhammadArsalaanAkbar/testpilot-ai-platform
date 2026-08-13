"use client";

import * as RadixToast from "@radix-ui/react-toast";
import { AlertCircle, CheckCircle2, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/lib/cn";

type ToastVariant = "success" | "error";

interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  showToast: (toast: Omit<ToastMessage, "id">) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** Transient success/error notifications (UX-006) — does not block the
 * underlying page. Use `useToast().showToast(...)` from any client component
 * beneath <ToastRootProvider>. */
export function ToastRootProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const showToast = useCallback((toast: Omit<ToastMessage, "id">) => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev, { ...toast, id }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      <RadixToast.Provider swipeDirection="right">
        {children}
        {toasts.map((toast) => (
          <RadixToast.Root
            key={toast.id}
            duration={5000}
            onOpenChange={(open) => !open && dismiss(toast.id)}
            className={cn(
              "flex items-start gap-2 rounded-md border p-3 shadow-md",
              "data-[state=open]:animate-in data-[state=open]:slide-in-from-right",
              "data-[state=closed]:animate-out data-[state=closed]:fade-out",
              toast.variant === "success"
                ? "border-status-passed bg-status-passed-bg text-status-passed"
                : "border-status-failed bg-status-failed-bg text-status-failed",
            )}
          >
            {toast.variant === "success" ? (
              <CheckCircle2 className="h-5 w-5 shrink-0" aria-hidden="true" />
            ) : (
              <AlertCircle className="h-5 w-5 shrink-0" aria-hidden="true" />
            )}
            <div className="flex-1">
              <RadixToast.Title className="text-body font-medium">{toast.title}</RadixToast.Title>
              {toast.description && (
                <RadixToast.Description className="text-caption opacity-90">
                  {toast.description}
                </RadixToast.Description>
              )}
            </div>
            <RadixToast.Close aria-label="Dismiss">
              <X className="h-4 w-4" aria-hidden="true" />
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="fixed bottom-4 right-4 z-[100] flex w-96 max-w-full flex-col gap-2" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastRootProvider");
  return ctx;
}
