import { useState, useCallback, useRef } from 'react';
import {
  Upload,
  FileSpreadsheet,
  X,
  Folder,
  Building2,
  AlertCircle,
  FileCheck,
} from 'lucide-react';
import { Modal } from '@/components/Modal';
import { Button } from '@/components/Button';
import { apiClient } from '@/api/client';
import { useToast } from '@/context/ToastContext';
import { formatFileSize } from '@/utils/format';
import type { UploadAndAssignResult } from '@/types';

const ALLOWED_EXTENSIONS = ['.xlsx', '.xls', '.csv'];
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB

const DEFAULT_TARGET_FOLDERS = [
  { value: '/02_Финансы_1С/2026-10/', label: '/02_Финансы_1С/2026-10/ (Основная папка отчетов)' },
  { value: '/04_Взаиморасчеты_сверки/2026-Q3/', label: '/04_Взаиморасчеты_сверки/2026-Q3/' },
  { value: '/01_Акты_КС2_КС3/2026-10/', label: '/01_Акты_КС2_КС3/2026-10/' },
  { value: '/05_Счета_поставщиков_ТМЦ/', label: '/05_Счета_поставщиков_ТМЦ/' },
];

const CONTRACT_OPTIONS = [
  { value: 'ТЭП-101 / Кислородный цех №101', label: 'ТЭП-101 — Кислородный цех №101' },
  { value: 'БМК-12 / Котельная БМК-12', label: 'БМК-12 — Котельная БМК-12' },
  { value: 'ОЧС-03 / Очистные сооружения', label: 'ОЧС-03 — Очистные сооружения' },
  { value: 'СКЛ-204 / Склад готовой продукции №4', label: 'СКЛ-204 — Склад готовой продукции №4' },
];

interface AccountantUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess?: (result: UploadAndAssignResult) => void;
}

export function AccountantUploadModal({
  isOpen,
  onClose,
  onUploadSuccess,
}: AccountantUploadModalProps) {
  const { showToast } = useToast();

  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [targetFolder, setTargetFolder] = useState('/02_Финансы_1С/2026-10/');
  const [contract, setContract] = useState(CONTRACT_OPTIONS[0].value);
  const [comment, setComment] = useState(
    'Отчет по взаиморасчетам за 15 октября, просьба согласовать с заказчиком по объекту 104'
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const resetState = () => {
    setFile(null);
    setError('');
    setIsSubmitting(false);
    setIsDragging(false);
  };

  const handleClose = () => {
    if (isSubmitting) return;
    resetState();
    onClose();
  };

  const validateFile = (f: File): string | null => {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Недопустимый формат файла. Требуется выгрузка из 1С: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }
    if (f.size > MAX_FILE_SIZE) {
      return `Файл превышает допустимый размер ${formatFileSize(MAX_FILE_SIZE)}`;
    }
    return null;
  };

  const handleFile = useCallback((f: File) => {
    setError('');
    const valError = validateFile(f);
    if (valError) {
      setError(valError);
      return;
    }
    setFile(f);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const dropped = e.dataTransfer.files[0];
      if (dropped) handleFile(dropped);
    },
    [handleFile]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Пожалуйста, выберите файл выгрузки из 1С');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const result = await apiClient.uploadAndAssignFile({
        file,
        target_folder: targetFolder,
        comment,
        assignee_role: 'manager',
        contract_id_or_name: contract,
      });

      showToast(
        `Отчет «${file.name}» загружен на Google Диск и передан менеджеру проектов!`,
        'success'
      );

      if (onUploadSuccess) {
        onUploadSuccess(result);
      }
      handleClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка при передаче документа';
      setError(msg);
      showToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Передача отчета 1С менеджеру проекта"
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Сценарий «Бухгалтер &rarr; Менеджер»: загрузка отчета 1С на Google Диск и автоматическое
          создание оперативной задачи менеджеру проекта для согласования с заказчиком.
        </p>

        {/* Drag and Drop Zone */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
            Файл выгрузки из 1С (.xlsx / .xls)
          </label>
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />

          {!file ? (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                isDragging
                  ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/20'
                  : 'border-slate-300 dark:border-slate-700 hover:border-indigo-500 dark:hover:border-indigo-500 bg-slate-50/50 dark:bg-slate-900/40'
              }`}
            >
              <div className="w-10 h-10 rounded-full bg-indigo-50 dark:bg-indigo-950/50 flex items-center justify-center mx-auto text-indigo-600 dark:text-indigo-400 mb-2">
                <Upload className="h-5 w-5" />
              </div>
              <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
                Перетащите файл .xlsx сюда или{' '}
                <span className="text-indigo-600 dark:text-indigo-400 font-semibold underline">
                  выберите с диска
                </span>
              </p>
              <p className="text-[11px] text-slate-400 mt-1">
                Поддерживаются отчеты 1С:Предприятие (до {formatFileSize(MAX_FILE_SIZE)})
              </p>
            </div>
          ) : (
            <div className="flex items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60">
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 shrink-0">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate">
                    {file.name}
                  </p>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    {formatFileSize(file.size)}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setFile(null)}
                disabled={isSubmitting}
                className="min-h-[44px] min-w-[44px] flex items-center justify-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                aria-label="Удалить файл"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>

        {/* Target Folder on Google Drive */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1.5">
            <Folder className="h-3.5 w-3.5 text-slate-400" />
            <span>Целевая папка на Google Диске</span>
          </label>
          <select
            value={targetFolder}
            onChange={(e) => setTargetFolder(e.target.value)}
            disabled={isSubmitting}
            className="w-full min-h-[42px] px-3 py-2 text-xs bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            id="accountant-target-folder"
          >
            {DEFAULT_TARGET_FOLDERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        {/* Related Contract / Object */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1.5">
            <Building2 className="h-3.5 w-3.5 text-slate-400" />
            <span>Привязка к объекту СМР</span>
          </label>
          <select
            value={contract}
            onChange={(e) => setContract(e.target.value)}
            disabled={isSubmitting}
            className="w-full min-h-[42px] px-3 py-2 text-xs bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            id="accountant-contract-select"
          >
            {CONTRACT_OPTIONS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        {/* Comment for Manager */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
            Комментарий и поручение менеджеру
          </label>
          <textarea
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={isSubmitting}
            className="w-full p-2.5 text-xs bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
            placeholder="Укажите детали согласования или сроки ответа заказчика..."
            id="accountant-comment-textarea"
          />
        </div>

        {/* Error message */}
        {error && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form Actions */}
        <div className="pt-2 flex items-center justify-end gap-2.5 border-t border-slate-200 dark:border-slate-800">
          <Button
            type="button"
            variant="ghost"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            Отмена
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={!file || isSubmitting}
            className="flex items-center gap-2 min-h-[44px]"
            id="accountant-submit-btn"
          >
            {isSubmitting ? (
              <>
                <div className="h-3.5 w-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Передача...</span>
              </>
            ) : (
              <>
                <FileCheck className="h-4 w-4" />
                <span>Подписать и передать менеджеру</span>
              </>
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
