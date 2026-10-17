import { useEffect, useState } from 'react';
import { Upload, FileSpreadsheet } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import { formatFileSize, formatDate } from '@/utils/format';
import type { FileListItem } from '@/types';

interface FilesTabProps {
  onUploadClick: () => void;
  onFileSelect: (fileId: string, fileName: string) => void;
  onAccountantUploadClick?: () => void;
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'processed':
      return <Badge variant="success">Обработан</Badge>;
    case 'awaiting_confirmation':
      return <Badge variant="warning">Ожидает подтверждения</Badge>;
    case 'processing':
      return <Badge variant="info">Обработка...</Badge>;
    default:
      return <Badge variant="neutral">{status}</Badge>;
  }
}

export function FilesTab({ onUploadClick, onFileSelect, onAccountantUploadClick }: FilesTabProps) {
  const [files, setFiles] = useState<FileListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .getFiles()
      .then(setFiles)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-[var(--text-main)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header & Upload buttons */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[var(--text-main)] flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-[var(--text-main)]" />
            Файлы и Google Диск
          </h2>
          <p className="text-xs text-[var(--text-sub)]">
            Корпоративный реестр выгрузок 1С, актов КС-2 и проектной документации
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {onAccountantUploadClick && (
            <button
              type="button"
              onClick={onAccountantUploadClick}
              className="min-h-[40px] px-3.5 py-2 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer"
              id="accountant-upload-btn"
            >
              <Upload className="h-4 w-4" />
              <span>Передать отчет 1С менеджеру</span>
            </button>
          )}

          <Button onClick={onUploadClick} id="upload-file-btn">
            <Upload className="h-4 w-4" />
            Загрузить файл
          </Button>
        </div>
      </div>

      {/* Files list */}
      {files.length === 0 ? (
        <Card className="text-center py-12">
          <FileSpreadsheet className="h-10 w-10 mx-auto text-[var(--text-muted)] mb-3" />
          <p className="text-sm text-[var(--text-sub)]">Файлы не загружены</p>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Нажмите «Загрузить файл» для начала работы
          </p>
        </Card>
      ) : (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" id="files-table">
              <thead>
                <tr className="bg-[var(--card-subtle)] border-b border-[var(--card-border)]">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                    Файл
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                    Размер
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                    Загрузил
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                    Дата
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                    Статус
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--card-border)]">
                {files.map((file) => (
                  <tr
                    key={file.id}
                    className="hover:bg-[var(--card-subtle)] transition-colors cursor-pointer"
                    onClick={() => {
                      if (file.status === 'awaiting_confirmation') {
                        onFileSelect(file.id, file.original_name);
                      }
                    }}
                  >
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <FileSpreadsheet className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                        <span className="font-semibold text-[var(--text-main)] truncate max-w-xs">
                          {file.original_name}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-right font-mono text-[var(--text-sub)]">
                      {formatFileSize(file.file_size_bytes)}
                    </td>
                    <td className="px-4 py-3.5 text-[var(--text-main)]">
                      {file.uploaded_by}
                    </td>
                    <td className="px-4 py-3.5 text-right text-[var(--text-sub)]">
                      {formatDate(file.created_at)}
                    </td>
                    <td className="px-4 py-3.5 text-center">
                      {getStatusBadge(file.status)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>

  );
}
