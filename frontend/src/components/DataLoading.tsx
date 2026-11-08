import { LoaderCircle } from 'lucide-react';

export function DataLoading({ className = '' }: { className?: string }) {
  return <div className={'workspace-data-loading ' + className} role="status">
    <LoaderCircle size={19} aria-hidden="true" />
    <span>Загружаем данные…</span>
  </div>;
}
