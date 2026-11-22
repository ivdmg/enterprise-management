import { useState } from 'react';
import { DataLoading } from '@/components/DataLoading';
import { DriveTree, useDriveCatalog } from './DriveCatalog';

const noUploads = new Map();

export default function ShowcaseDriveTab({ refreshAt }: { refreshAt?: string | null }) {
  const [attempt, setAttempt] = useState(0);
  const { nodes, error } = useDriveCatalog(true, refreshAt, attempt);
  return (
    <section>
      {error && <div><p role="alert">{error}</p><button className="workspace-link" onClick={() => setAttempt(value => value + 1)}>Повторить</button></div>}
      {!nodes && !error && <DataLoading />}
      {nodes && (nodes.length
        ? <DriveTree nodes={nodes} files={noUploads} />
        : <p>В каталоге пока нет файлов.</p>)}
    </section>
  );
}
