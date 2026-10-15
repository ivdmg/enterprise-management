import { useEffect, useState } from 'react';
import { X, AlertTriangle, AlertCircle, Info, CheckCircle2 } from 'lucide-react';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { apiClient } from '@/api/client';
import { formatCurrency, formatDate } from '@/utils/format';
import type { Alert } from '@/types';

interface AlertsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

function getSeverityIcon(severity: string) {
  switch (severity) {
    case 'CRITICAL':
      return <AlertTriangle className="h-4 w-4 text-rose-500" />;
    case 'WARNING':
      return <AlertCircle className="h-4 w-4 text-amber-500" />;
    default:
      return <Info className="h-4 w-4 text-slate-400" />;
  }
}

function getSeverityBadge(severity: string) {
  switch (severity) {
    case 'CRITICAL':
      return <Badge variant="danger">Критично</Badge>;
    case 'WARNING':
      return <Badge variant="warning">Внимание</Badge>;
    default:
      return <Badge variant="neutral">Инфо</Badge>;
  }
}

export function AlertsDrawer({ isOpen, onClose }: AlertsDrawerProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(false);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [comment, setComment] = useState('');

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      apiClient
        .getAlerts()
        .then(setAlerts)
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  const handleResolve = async (alertId: string) => {
    if (!comment.trim()) return;
    try {
      await apiClient.resolveAlert(alertId, comment);
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, is_resolved: true } : a)),
      );
      setResolvingId(null);
      setComment('');
    } catch {
      // handled
    }
  };

  if (!isOpen) return null;

  const unresolvedAlerts = alerts.filter((a) => !a.is_resolved);
  const resolvedAlerts = alerts.filter((a) => a.is_resolved);

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Центр алертов
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Закрыть"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="h-6 w-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="divide-y divide-slate-200 dark:divide-slate-800">
              {/* Active alerts */}
              {unresolvedAlerts.length > 0 && (
                <div className="p-4 space-y-3">
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Активные ({unresolvedAlerts.length})
                  </p>
                  {unresolvedAlerts.map((alert) => (
                    <div
                      key={alert.id}
                      className="p-3 rounded-lg border border-slate-200 dark:border-slate-700 space-y-2"
                    >
                      <div className="flex items-start gap-2">
                        {getSeverityIcon(alert.severity)}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            {getSeverityBadge(alert.severity)}
                          </div>
                          <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                            {alert.title}
                          </p>
                          {alert.description && (
                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                              {alert.description}
                            </p>
                          )}
                          <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-400 dark:text-slate-500">
                            {alert.calculated_financial_impact > 0 && (
                              <span className="font-medium text-rose-600 dark:text-rose-400">
                                {formatCurrency(alert.calculated_financial_impact)}
                              </span>
                            )}
                            {alert.created_at && <span>{formatDate(alert.created_at)}</span>}
                          </div>
                        </div>
                      </div>

                      {/* Resolve form */}
                      {resolvingId === alert.id ? (
                        <div className="space-y-2 pt-1">
                          <textarea
                            value={comment}
                            onChange={(e) => setComment(e.target.value)}
                            placeholder="Комментарий по решению..."
                            rows={2}
                            className="w-full px-3 py-2 text-sm rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors resize-none"
                          />
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => {
                                setResolvingId(null);
                                setComment('');
                              }}
                            >
                              Отмена
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => handleResolve(alert.id)}
                              disabled={!comment.trim()}
                            >
                              Подтвердить
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setResolvingId(alert.id)}
                          className="mt-1"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Отметить решённым
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Resolved alerts */}
              {resolvedAlerts.length > 0 && (
                <div className="p-4 space-y-3">
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Решённые ({resolvedAlerts.length})
                  </p>
                  {resolvedAlerts.map((alert) => (
                    <div
                      key={alert.id}
                      className="p-3 rounded-lg border border-slate-200 dark:border-slate-700 opacity-60"
                    >
                      <div className="flex items-start gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm text-slate-700 dark:text-slate-300 line-through">
                            {alert.title}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {alerts.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center px-4">
                  <CheckCircle2 className="h-10 w-10 text-emerald-500 mb-3" />
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Нет активных уведомлений
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
