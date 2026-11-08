import { useEffect, useState } from 'react';
import { ExternalLink, File, Folder } from 'lucide-react';
import { apiClient } from '@/api/client';
import { Badge } from '@/components/Badge';
import { formatDate, formatFileSize } from '@/utils/format';
import type { FileListItem } from '@/types';

export interface DriveNode {
  id: string;
  name: string;
  url: string;
  active_source: boolean;
  size_bytes: number | null;
  created_at: string | null;
  owner: string | null;
  children: DriveNode[] | null;
}

export function flattenDrive(nodes: DriveNode[]): DriveNode[] {
  return [
    ...nodes.filter(node => !node.children),
    ...nodes.flatMap(node => node.children ? flattenDrive(node.children) : []),
  ];
}

export function useDriveCatalog(enabled: boolean) {
  const [nodes, setNodes] = useState<DriveNode[]>();
  const [error, setError] = useState('');
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    apiClient.getDriveCatalog(controller.signal)
      .then(setNodes)
      .catch((failure: Error) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [enabled]);
  return { nodes, error };
}

const importStatuses: Record<string, string> = {
  processed: 'Обработан', error: 'Ошибка импорта', failed: 'Ошибка импорта',
  awaiting_confirmation: 'Ожидает подтверждения', processing: 'Обработка', uploaded: 'Загружен',
};

export function FileRow({ node, file, onFileSelect }: {
  node?: DriveNode; file?: FileListItem;
  onFileSelect?: (id: string, name: string) => void;
}) {
  const date = node?.created_at ?? file?.created_at;
  const size = node?.size_bytes ?? file?.file_size_bytes;
  const name = node?.name ?? file?.original_name;
  const link = node?.url ?? file?.google_drive_link;
  const status = file && importStatuses[file.status];

  return <div className="workspace-catalog-file">
    <div className="workspace-catalog-name"><File size={17} aria-hidden="true" /><strong>{name}</strong></div>
    <div className="workspace-catalog-meta">
      <span>{file?.uploaded_by ? 'Загрузил · ' + file.uploaded_by : node?.owner ? 'Владелец · ' + node.owner : 'Загрузивший не указан'}</span>
      <span>{date ? formatDate(date) : 'Дата недоступна'}</span>
      {size != null && <span>{formatFileSize(size)}</span>}
    </div>
    <div className="workspace-catalog-actions">
      {node && (node.active_source ? <Badge variant="success">Подключён к импорту</Badge> :
        <Badge variant="warning">Парсер не подключён</Badge>)}
      {status && (!node || node.active_source) && <Badge variant={file.status === 'processed' ? 'success' : 'neutral'}>{status}</Badge>}
      {file?.status === 'awaiting_confirmation' && onFileSelect && <button type="button" className="workspace-link" onClick={() => onFileSelect(file.id, file.original_name)}>Настроить импорт</button>}
      {link && <a className="workspace-link" href={link} target="_blank" rel="noreferrer">Открыть на Google Диске <ExternalLink size={14} /></a>}
    </div>
  </div>;
}

export function DriveTree({ nodes, files, onFileSelect }: {
  nodes: DriveNode[]; files: Map<string, FileListItem>;
  onFileSelect?: (id: string, name: string) => void;
}) {
  return <ul className="workspace-drive-tree">
    {nodes.map(node => <li key={node.id}>
      {node.children ? <details>
        <summary><Folder size={16} /> {node.name}</summary>
        <a className="workspace-link" href={node.url} target="_blank" rel="noreferrer">Открыть папку <ExternalLink size={14} /></a>
        <DriveTree nodes={node.children} files={files} onFileSelect={onFileSelect} />
      </details> : <FileRow node={node} file={files.get(node.id)} onFileSelect={onFileSelect} />}
    </li>)}
  </ul>;
}
