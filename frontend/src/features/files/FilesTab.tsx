import { useEffect, useState } from 'react';
import { Upload, FileSpreadsheet, Clock, CheckCircle2 } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import { formatFileSize, formatDate } from '@/utils/format';
import type { FileListItem } from '@/types';

interface FilesTabProps {
  onUploadClick: () => void;
  onFileSelect: (fileId: string, fileName: string) => void;
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

export function FilesTab({ onUploadClick, onFileSelect }: FilesTabProps) {
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
        <div className="h-6 w-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Upload button */}
      <div className="flex justify-end">
        <Button onClick={onUploadClick} id="upload-file-btn">
          <Upload className="h-4 w-4" />
          Загрузить файл
        </Button>
      </div>

      {/* Files list */}
      {files.length === 0 ? (
        <Card className="text-center py-12">
          <FileSpreadsheet className="h-10 w-10 mx-auto text-slate-300 dark:text-slate-600 mb-3" />
          <p className="text-sm text-slate-500 dark:text-slate-400">Файлы не загружены</p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
            Нажмите «Загрузить файл» для начала работы
          </p>
        </Card>
      ) : (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" id="files-table">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/50">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Файл
                  </th>
                  <th className="text-right px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Размер
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Загрузил
                  </th>
                  <th className="text-right px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Дата
                  </th>
                  <th className="text-center px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Статус
                  </th>
                </tr>
              </thead>
              <tbody>
                {files.map((file) => (
                  <tr
                    key={file.id}
                    className="border-t border-slate-200 dark:border-slate-800 hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors cursor-pointer"
                    onClick={() => {
                      if (file.status === 'awaiting_confirmation') {
                        onFileSelect(file.id, file.original_name);
                      }
                    }}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <FileSpreadsheet className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                        <span className="font-medium text-slate-900 dark:text-slate-100 truncate max-w-xs">
                          {file.original_name}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-600 dark:text-slate-400">
                      {formatFileSize(file.file_size_bytes)}
                    </td>
                    <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                      {file.uploaded_by}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-600 dark:text-slate-400">
                      {formatDate(file.created_at)}
                    </td>
                    <td className="px-4 py-3 text-center">
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
