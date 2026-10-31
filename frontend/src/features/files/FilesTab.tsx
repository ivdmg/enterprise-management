import { useEffect, useState } from 'react';
import { Upload, FileSpreadsheet, ExternalLink } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import { formatFileSize, formatDate } from '@/utils/format';
import type { FileListItem } from '@/types';

interface FilesTabProps {
  readOnly?: boolean;
  onUploadClick: () => void;
  onFileSelect: (fileId: string, fileName: string) => void;
  onAccountantUploadClick?: () => void;
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'processed':
      return <Badge variant="success">Обработан</Badge>;
    case 'failed':
      return <Badge variant="danger">Ошибка импорта</Badge>;
    case 'awaiting_confirmation':
      return <Badge variant="warning">Ожидает подтверждения</Badge>;
    case 'processing':
      return <Badge variant="info">Обработка...</Badge>;
    default:
      return <Badge variant="neutral">{status}</Badge>;
  }
}

export function FilesTab({ onUploadClick, onFileSelect, onAccountantUploadClick, readOnly = false }: FilesTabProps) {
  const [files, setFiles] = useState<FileListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [driveLink, setDriveLink] = useState<string>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    apiClient.getDriveSyncStatus().then((status) => setDriveLink(status.root_folder_link)).catch(() => {});
    apiClient
      .getFiles()
      .then(setFiles)
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить файлы'))
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
            Исходная таблица заказчика: реестр контрактов и ежедневный мониторинг
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {driveLink && <a href={driveLink} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold text-emerald-600 inline-flex items-center gap-1.5 min-h-[40px] px-3 border border-[var(--card-border)] rounded-xl"><ExternalLink className="h-4 w-4" />Папка Google Диска</a>}
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

          {!readOnly && <Button onClick={onUploadClick} id="upload-file-btn">
            <Upload className="h-4 w-4" />
            Загрузить файл
          </Button>}
        </div>
      </div>

      {/* Files list */}
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
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
          {/* Mobile View: Vertical cards list (md:hidden) */}
          <div className="md:hidden divide-y divide-[var(--card-border)]" id="files-mobile-list">
            {files.map((file) => (
              <div
                key={file.id}
                onClick={() => {
                  if (file.status === 'awaiting_confirmation') {
                    onFileSelect(file.id, file.original_name);
                  } else {
                    if (file.google_drive_link) window.open(
                      file.google_drive_link,
                      '_blank',
                      'noopener,noreferrer'
                    );
                  }
                }}
                className="p-3.5 sm:p-4 transition-colors cursor-pointer active:bg-[var(--card-subtle)] bg-[var(--card-bg)] hover:bg-[var(--card-subtle)]/60"
              >
                {/* Top Row: File icon + Date on the left, Status Badge on the right */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/40 shrink-0">
                      <FileSpreadsheet className="h-4 w-4" />
                    </div>
                    <span className="text-[11px] font-mono text-[var(--text-muted)] truncate">
                      {formatDate(file.created_at)}
                    </span>
                  </div>
                  <div className="shrink-0 max-w-[55%] flex justify-end">
                    {getStatusBadge(file.status)}
                  </div>
                </div>

                {/* Full Width File Name */}
                <h4 className="font-semibold text-sm text-[var(--text-main)] break-words leading-snug mb-2.5">
                  {file.original_name}
                </h4>

                {/* Meta details row: Size & Uploader */}
                <div className="grid grid-cols-2 gap-2 text-xs text-[var(--text-sub)] pt-2 border-t border-[var(--card-border)]/60">
                  <div>
                    <span className="text-[10px] text-[var(--text-muted)] block uppercase tracking-wider">
                      Размер
                    </span>
                    <span className="font-mono text-[var(--text-main)] font-medium">
                      {formatFileSize(file.file_size_bytes)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-[var(--text-muted)] block uppercase tracking-wider">
                      Загрузил
                    </span>
                    <span className="text-[var(--text-main)] font-medium truncate block">
                      {file.uploaded_by}
                    </span>
                  </div>
                </div>

                {/* Actions row: Direct Google Drive link + Mapping hint */}
                <div className="mt-2.5 pt-2 border-t border-[var(--card-border)]/60 flex items-center justify-between gap-2">
                  <a
                    href={file.google_drive_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] hover:bg-[var(--card-bg)] text-xs font-semibold text-[var(--text-main)] transition-colors shadow-2xs"
                    title="Открыть файл в Google Диск"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                    <span>Открыть на Диске</span>
                    <ExternalLink className="h-3 w-3 text-[var(--text-muted)]" />
                  </a>

                  {file.status === 'awaiting_confirmation' && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onFileSelect(file.id, file.original_name);
                      }}
                      className="text-xs font-semibold text-amber-700 dark:text-amber-400 underline flex items-center gap-1 cursor-pointer"
                    >
                      <span>Сопоставить</span>
                      <span>&rarr;</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Desktop View: Full Data Table (hidden md:block) */}
          <div className="hidden md:block overflow-x-auto">
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
                  <th className="text-right px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                    Google Диск
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
                      } else {
                        if (file.google_drive_link) window.open(
                          file.google_drive_link,
                          '_blank',
                          'noopener,noreferrer'
                        );
                      }
                    }}
                  >
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <FileSpreadsheet className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                        <span className="font-semibold text-[var(--text-main)] truncate max-w-xs hover:underline">
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
                    <td className="px-4 py-3.5 text-right">
                      <a
                        href={file.google_drive_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-[var(--card-border)] bg-[var(--card-subtle)] hover:bg-[var(--card-bg)] text-xs font-semibold text-[var(--text-main)] transition-colors shadow-2xs"
                        title="Открыть файл в Google Диск"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                        <span>Диск</span>
                        <ExternalLink className="h-3 w-3 text-[var(--text-muted)]" />
                      </a>
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
