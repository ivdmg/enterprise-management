import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { CheckCircle2, AlertTriangle, Info, XCircle, X } from 'lucide-react';

export type ToastType = 'success' | 'info' | 'warning' | 'error';

interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextType>({
  showToast: () => {},
});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, type: ToastType = 'success') => {
      const id = `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
      setToasts((prev) => [...prev, { id, message, type }]);

      setTimeout(() => {
        removeToast(id);
      }, 4500);
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {/* Toast container */}
      <div
        className="fixed z-50 bottom-4 right-4 left-4 sm:left-auto sm:w-96 flex flex-col gap-2 pointer-events-none"
        aria-live="polite"
      >
        {toasts.map((toast) => {
          let icon = <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />;
          let borderStyle = 'border-slate-200 dark:border-slate-800';

          if (toast.type === 'error') {
            icon = <XCircle className="h-5 w-5 text-rose-600 dark:text-rose-400 shrink-0" />;
            borderStyle = 'border-rose-500/30';
          } else if (toast.type === 'warning') {
            icon = <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />;
            borderStyle = 'border-amber-500/30';
          } else if (toast.type === 'info') {
            icon = <Info className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0" />;
          }

          return (
            <div
              key={toast.id}
              className={`pointer-events-auto flex items-start gap-3 p-3.5 rounded-lg bg-white dark:bg-slate-900 border ${borderStyle} shadow-lg text-sm text-slate-800 dark:text-slate-200 transition-all transform translate-y-0`}
            >
              {icon}
              <div className="flex-1 pt-0.5 leading-snug break-words">{toast.message}</div>
              <button
                onClick={() => removeToast(toast.id)}
                className="min-h-[44px] min-w-[44px] -m-2 flex items-center justify-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                aria-label="Закрыть уведомление"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
