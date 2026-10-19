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
        <div className="flex items-center justify-between px-4 sm:px-6 py-3.5 sm:py-4 border-b border-[var(--card-border)]">
          <div className="min-w-0 pr-2">
            <h2 className="text-base font-bold text-[var(--text-main)] truncate">
              Сопоставление колонок
            </h2>
            <p className="text-xs text-[var(--text-sub)] mt-0.5 truncate">{fileName}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--card-subtle)] transition-colors cursor-pointer shrink-0"
            aria-label="Закрыть"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 pt-4 sm:pt-5 pb-28 sm:pb-32 space-y-4 sm:space-y-5">
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
                <label className="block text-xs font-semibold text-[var(--text-main)] mb-1.5">
                  Категория данных
                </label>
                <Select
                  options={domainOptions}
                  value={domain}
                  onChange={(v) => setDomain(v as DomainCategory)}
                  id="mapping-domain-select"
                />
                <div className="flex items-center gap-1.5 mt-2">
                  <span className="text-xs text-[var(--text-sub)]">
                    Уверенность определения:
                  </span>
                  {getConfidenceBadge(data.confidence_score)}
                </div>
              </div>

              {/* Column Mapping Section */}
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <p className="text-xs font-semibold text-[var(--text-main)]">
                    Сопоставление колонок ({data.columns_mapping.length})
                  </p>
                  <span className="text-[11px] text-[var(--text-muted)]">
                    Сопоставьте поля файла со стандартом
                  </span>
                </div>

                {/* Mobile View: Vertical Cards (< md) */}
                <div className="md:hidden space-y-3" id="mapping-mobile-cards">
                  {data.columns_mapping.map((col) => {
                    const isMapped = mappings[col.source_column] && mappings[col.source_column] !== 'ignore';
                    return (
                      <div
                        key={col.source_column}
                        className={`p-3.5 rounded-xl border transition-colors ${
                          isMapped
                            ? 'bg-[var(--card-subtle)] border-[var(--card-border)]'
                            : 'bg-[var(--card-bg)] border-[var(--card-border)]/80'
                        }`}
                      >
                        {/* Source Column Header & Confidence */}
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="min-w-0 flex-1">
                            <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] block font-medium">
                              Колонка из файла
                            </span>
                            <p className="font-semibold text-sm text-[var(--text-main)] break-words leading-tight">
                              {col.source_column}
                            </p>
                          </div>
                          <div className="shrink-0 flex items-center gap-1">
                            <span className="text-[10px] text-[var(--text-muted)]">Точн.</span>
                            {getConfidenceBadge(col.confidence)}
                          </div>
                        </div>

                        {/* Sample preview box */}
                        {col.sample_values && col.sample_values.length > 0 && (
                          <div className="mb-2.5 px-2.5 py-1.5 rounded-lg bg-[var(--card-bg)] border border-[var(--card-border)]/60 text-xs">
                            <span className="text-[10px] text-[var(--text-muted)] block uppercase tracking-wider">
                              Пример данных:
                            </span>
                            <span className="font-mono text-[11px] text-[var(--text-sub)] truncate block">
                              {col.sample_values.slice(0, 3).join(', ')}
                            </span>
                          </div>
                        )}

                        {/* Target Field Dropdown */}
                        <div className="pt-2 border-t border-[var(--card-border)]/60">
                          <label className="flex items-center gap-1.5 text-xs font-medium text-[var(--text-sub)] mb-1.5">
                            <ArrowRight className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0" />
                            <span>Поле системы:</span>
                          </label>
                          <Select
                            options={targetFieldOptions}
                            value={mappings[col.source_column] || 'ignore'}
                            onChange={(v) =>
                              setMappings((prev) => ({ ...prev, [col.source_column]: v }))
                            }
                            className="w-full"
                            size="md"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Desktop View: Clean Structured Table (hidden md:block) */}
                <div className="hidden md:block border border-[var(--card-border)] rounded-xl bg-[var(--card-bg)]">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-[var(--card-subtle)] border-b border-[var(--card-border)]">
                        <th className="text-left px-3.5 py-2.5 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider w-[36%] rounded-tl-xl">
                          Колонка из файла
                        </th>
                        <th className="px-2 py-2.5 w-8 text-center"></th>
                        <th className="text-left px-3.5 py-2.5 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider w-[44%]">
                          Поле системы
                        </th>
                        <th className="text-center px-3.5 py-2.5 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider w-[14%] rounded-tr-xl">
                          Точн.
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--card-border)]">
                      {data.columns_mapping.map((col, idx) => {
                        const isLast = idx === data.columns_mapping.length - 1;
                        return (
                          <tr
                            key={col.source_column}
                            className="hover:bg-[var(--card-subtle)]/60 transition-colors"
                          >
                            <td className={`px-3.5 py-2.5 align-middle ${isLast ? 'rounded-bl-xl' : ''}`}>
                              <p className="font-semibold text-[var(--text-main)] text-sm">
                                {col.source_column}
                              </p>
                              <p className="text-xs text-[var(--text-muted)] mt-0.5 truncate max-w-48 font-mono">
                                {col.sample_values.slice(0, 2).join(', ')}
                              </p>
                            </td>
                            <td className="px-1 text-center align-middle">
                              <ArrowRight className="h-3.5 w-3.5 text-[var(--text-muted)] mx-auto" />
                            </td>
                            <td className="px-3.5 py-2.5 align-middle">
                              <Select
                                options={targetFieldOptions}
                                value={mappings[col.source_column] || 'ignore'}
                                onChange={(v) =>
                                  setMappings((prev) => ({ ...prev, [col.source_column]: v }))
                                }
                                className="w-full"
                              />
                            </td>
                            <td className={`px-3.5 py-2.5 text-center align-middle ${isLast ? 'rounded-br-xl' : ''}`}>
                              {getConfidenceBadge(col.confidence)}
                            </td>
                          </tr>
                        );
                      })}
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
                  className="w-full px-3 py-2 text-xs rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] text-[var(--text-main)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--card-border)] transition-colors"
                />
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        {!loading && !confirmed && data && (
          <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-2 px-4 sm:px-6 py-3.5 sm:py-4 border-t border-[var(--card-border)] bg-[var(--card-bg)]">
            <Button variant="secondary" onClick={onClose} className="w-full sm:w-auto">
              Отмена
            </Button>
            <Button onClick={handleConfirm} disabled={confirming} className="w-full sm:w-auto">
              {confirming ? 'Сохранение...' : 'Применить и сохранить шаблон'}
            </Button>
          </div>
        )}
      </div>

    </>
  );
}
