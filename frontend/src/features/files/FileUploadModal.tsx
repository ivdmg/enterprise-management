import { useState, useCallback, useRef } from 'react';
import { Upload, FileSpreadsheet, X, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Modal } from '@/components/Modal';
import { Button } from '@/components/Button';
import { apiClient } from '@/api/client';
import { formatFileSize } from '@/utils/format';
import type { FileUploadData } from '@/types';

const ALLOWED_EXTENSIONS = ['.xlsx', '.xls', '.csv'];
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB

interface FileUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadComplete: (data: FileUploadData) => void;
}

export function FileUploadModal({ isOpen, onClose, onUploadComplete }: FileUploadModalProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (f: File): string | null => {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Неподдерживаемый формат. Допустимы: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }
    if (f.size > MAX_FILE_SIZE) {
      return `Файл слишком большой. Максимум: ${formatFileSize(MAX_FILE_SIZE)}`;
    }
    return null;
  };

  const handleFile = useCallback((f: File) => {
    setError('');
    const validationError = validateFile(f);
    if (validationError) {
      setError(validationError);
      return;
    }
    setFile(f);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) handleFile(droppedFile);
    },
    [handleFile],
  );

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setProgress(0);

    // Simulate progress
    const interval = setInterval(() => {
      setProgress((p) => Math.min(p + 15, 90));
    }, 200);

    try {
      const data = await apiClient.uploadFile(file);
      clearInterval(interval);
      setProgress(100);
      setTimeout(() => {
        onUploadComplete(data);
        resetState();
      }, 300);
    } catch (err: any) {
      clearInterval(interval);
      setError(err.message || 'Ошибка загрузки');
      setUploading(false);
      setProgress(0);
    }
  };

  const resetState = () => {
    setFile(null);
    setUploading(false);
    setProgress(0);
    setError('');
  };

  const handleClose = () => {
    if (!uploading) {
      resetState();
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Загрузка файла" size="md">
      <div className="space-y-4">
        {/* Drop zone */}
        {!file && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragging
                ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/5'
                : 'border-slate-300 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-600'
            }`}
            id="file-drop-zone"
          >
            <Upload className="h-8 w-8 mx-auto mb-3 text-slate-400 dark:text-slate-500" />
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Перетащите файл сюда
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              или нажмите для выбора (.xlsx, .xls, .csv, до 25 МБ)
            </p>
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
                e.target.value = '';
              }}
            />
          </div>
        )}

        {/* Selected file */}
        {file && !uploading && (
          <div className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
            <FileSpreadsheet className="h-8 w-8 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                {file.name}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {formatFileSize(file.size)}
              </p>
            </div>
            <button
              onClick={() => setFile(null)}
              className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
              aria-label="Удалить файл"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Progress */}
        {uploading && (
          <div className="space-y-2">
            <div className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
              <FileSpreadsheet className="h-8 w-8 text-indigo-600 dark:text-indigo-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                  {file?.name}
                </p>
                <div className="mt-1.5 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-600 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
              {progress === 100 && (
                <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
              )}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 px-3 py-2 rounded-md bg-rose-500/10 border border-rose-500/20">
            <AlertTriangle className="h-4 w-4 text-rose-600 dark:text-rose-400 mt-0.5 shrink-0" />
            <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
          <Button variant="secondary" onClick={handleClose} disabled={uploading}>
            Отмена
          </Button>
          <Button onClick={handleUpload} disabled={!file || uploading}>
            {uploading ? 'Загрузка...' : 'Загрузить'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
