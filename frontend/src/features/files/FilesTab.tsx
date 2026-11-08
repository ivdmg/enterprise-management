import { useEffect, useState } from 'react';
import { apiClient } from '@/api/client';
import { DataLoading } from '@/components/DataLoading';
import { DriveTree, FileRow, flattenDrive, useDriveCatalog } from './DriveCatalog';
import type { FileListItem } from '@/types';

export function FilesTab({ showDrive, onFileSelect }: {
  showDrive: boolean;
  onFileSelect?: (fileId: string, fileName: string) => void;
}) {
  const { nodes, error: driveError } = useDriveCatalog(showDrive);
  const [files, setFiles] = useState<FileListItem[]>();
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    apiClient.getFiles(controller.signal)
      .then(setFiles)
      .catch((failure: Error) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, []);

  const driveFiles = flattenDrive(nodes ?? []);
  const driveIds = new Set(driveFiles.map(node => node.id));
  const attached = new Map<string, FileListItem>();
  const local = [];
  for (const file of files ?? []) {
    if (file.google_drive_id && driveIds.has(file.google_drive_id)) {
      if (!attached.has(file.google_drive_id)) attached.set(file.google_drive_id, file);
    } else {
      local.push(file);
    }
  }
  const loading = (!files && !error) || (showDrive && !nodes && !driveError);

  return <section className="workspace-panel">
    <h2>Каталог файлов</h2>
    {loading ? <DataLoading /> : <>
      {driveError && <p role="alert">{driveError}</p>}
      {error && <p role="alert">{error}</p>}
      {nodes && nodes.length > 0 && <DriveTree nodes={nodes} files={attached} onFileSelect={onFileSelect} />}
      {local.map(file => <FileRow key={file.id} file={file} onFileSelect={onFileSelect} />)}
      {!nodes?.length && !local.length && !driveError && !error && <p>В каталоге пока нет файлов.</p>}
    </>}
  </section>;
}
