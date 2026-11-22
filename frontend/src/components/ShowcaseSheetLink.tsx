import { createContext, useContext } from 'react';
import { FileSpreadsheet } from 'lucide-react';

export const ShowcaseSheets = createContext<Record<string, string>>({});

export function ShowcaseSheetLink({ sheet }: { sheet: string }) {
  const href = useContext(ShowcaseSheets)[sheet];
  if (!href) return null;
  return <a className="workspace-sheet-link" href={href} target="_blank" rel="noreferrer">
    <FileSpreadsheet size={16} aria-hidden="true" /> Открыть таблицу
  </a>;
}
