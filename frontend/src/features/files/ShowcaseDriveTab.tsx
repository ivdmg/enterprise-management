import { DataLoading } from '@/components/DataLoading';
import { DriveTree, useDriveCatalog } from './DriveCatalog';

const noUploads = new Map();

export default function ShowcaseDriveTab({ refreshAt }: { refreshAt?: string | null }) {
  const { nodes, error } = useDriveCatalog(true, refreshAt);
  return (
    <section>
      {error && <p role="alert">{error}</p>}
      {!nodes && !error && <DataLoading />}
      {nodes && (nodes.length
        ? <DriveTree nodes={nodes} files={noUploads} />
        : <p>В каталоге пока нет файлов.</p>)}
    </section>
  );
}
