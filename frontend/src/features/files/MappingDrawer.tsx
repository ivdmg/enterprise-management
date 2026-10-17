import { useState, useEffect } from 'react';
import { X, CheckCircle2, ArrowRight } from 'lucide-react';
import { Button } from '@/components/Button';
import { Badge } from '@/components/Badge';
import { Select } from '@/components/Select';
import { apiClient } from '@/api/client';
import type { MappingPreviewData, DomainCategory } from '@/types';

interface MappingDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  fileId: string;
  fileName: string;
}

const domainOptions = [
  { value: 'production_tenders', label: 'Тендеры и производство' },
  { value: 'cashflow_debt', label: 'Финансы и взаиморасчеты' },
  { value: 'payroll_hr', label: 'ФОТ и кадры' },
  { value: 'operational_tasks', label: 'Оперативные задачи' },
];

function getConfidenceBadge(confidence: number) {
  if (confidence >= 0.85) return <Badge variant="success">{Math.round(confidence * 100)}%</Badge>;
  if (confidence >= 0.50) return <Badge variant="warning">{Math.round(confidence * 100)}%</Badge>;
  return <Badge variant="neutral">{Math.round(confidence * 100)}%</Badge>;
}

export function MappingDrawer({ isOpen, onClose, fileId, fileName }: MappingDrawerProps) {
  const [data, setData] = useState<MappingPreviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [domain, setDomain] = useState<DomainCategory>('production_tenders');
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [templateName, setTemplateName] = useState('');
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (isOpen && fileId) {
      setLoading(true);
      setConfirmed(false);
      apiClient
        .getMappingPreview(fileId)
        .then((preview) => {
          setData(preview);
          setDomain(preview.suggested_domain as DomainCategory);
          // Init mappings from preview
          const initial: Record<string, string> = {};
          preview.columns_mapping.forEach((col) => {
            initial[col.source_column] = col.target_field || 'ignore';
          });
          setMappings(initial);
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [isOpen, fileId]);

  const handleConfirm = async () => {
    if (!data) return;
    setConfirming(true);
    try {
      await apiClient.confirmMapping(fileId, {
        sheet_name: data.sheet_name,
        domain_category: domain,
        template_name: templateName || undefined,
        mappings,
      });
      setConfirmed(true);
      setTimeout(onClose, 1500);
    } catch {
      // error handled silently in mock mode
    } finally {
      setConfirming(false);
    }
  };

  if (!isOpen) return null;

  const targetFieldOptions = [
    { value: 'ignore', label: 'Пропустить' },
    ...(data?.available_canonical_fields.map((f) => ({
      value: f.field,
      label: `${f.label}${f.required ? ' *' : ''}`,
    })) || []),
  ];

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-[var(--card-bg)] border-l border-[var(--card-border)] shadow-2xl flex flex-col transition-colors duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--card-border)]">
          <div>
            <h2 className="text-base font-bold text-[var(--text-main)]">
              Сопоставление колонок
            </h2>
            <p className="text-xs text-[var(--text-sub)] mt-0.5">{fileName}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--card-subtle)] transition-colors cursor-pointer"
            aria-label="Закрыть"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="h-6 w-6 border-2 border-[var(--text-main)] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : confirmed ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <CheckCircle2 className="h-12 w-12 text-emerald-600 dark:text-emerald-400 mb-3" />
              <p className="text-lg font-bold text-[var(--text-main)]">
                Данные успешно импортированы
              </p>
              <p className="text-sm text-[var(--text-sub)] mt-1">
                Обработано строк: {data?.total_rows_detected || 0}
              </p>
            </div>
          ) : data ? (

            <>
              {/* Domain selector */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                  Категория данных
                </label>
                <Select
                  options={domainOptions}
                  value={domain}
                  onChange={(v) => setDomain(v as DomainCategory)}
                  id="mapping-domain-select"
                />
                <div className="flex items-center gap-1.5 mt-2">
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    Уверенность определения:
                  </span>
                  {getConfidenceBadge(data.confidence_score)}
                </div>
              </div>

              {/* Mapping table */}
              <div>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Сопоставление колонок ({data.columns_mapping.length})
                </p>
                <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-800/50">
                        <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                          Колонка из файла
                        </th>
                        <th className="px-2 py-2 w-8"></th>
                        <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                          Поле системы
                        </th>
                        <th className="text-center px-3 py-2 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider w-16">
                          Точн.
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.columns_mapping.map((col) => (
                        <tr
                          key={col.source_column}
                          className="border-t border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors"
                        >
                          <td className="px-3 py-2.5">
                            <p className="font-medium text-slate-900 dark:text-slate-100 text-sm">
                              {col.source_column}
                            </p>
                            <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 truncate max-w-48">
                              {col.sample_values.slice(0, 2).join(', ')}
                            </p>
                          </td>
                          <td className="px-1 text-center">
                            <ArrowRight className="h-3.5 w-3.5 text-slate-400" />
                          </td>
                          <td className="px-3 py-2.5">
                            <Select
                              options={targetFieldOptions}
                              value={mappings[col.source_column] || 'ignore'}
                              onChange={(v) =>
                                setMappings((prev) => ({ ...prev, [col.source_column]: v }))
                              }
                              className="w-full"
                            />
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            {getConfidenceBadge(col.confidence)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Template name */}
              <div>
                <label className="block text-xs font-semibold text-[var(--text-main)] mb-1.5">
                  Название шаблона (необязательно)
                </label>
                <input
                  type="text"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  placeholder="Реестр договоров ПТО 2026"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--text-main)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-slate-900 dark:focus:ring-slate-100 transition-colors"
                />
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        {!loading && !confirmed && data && (
          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-[var(--card-border)]">
            <Button variant="secondary" onClick={onClose}>
              Отмена
            </Button>
            <Button onClick={handleConfirm} disabled={confirming}>
              {confirming ? 'Сохранение...' : 'Применить и сохранить шаблон'}
            </Button>
          </div>
        )}
      </div>

    </>
  );
}
