import { DataLoading } from '@/components/DataLoading';
import { useEffect, useState } from 'react';
import { Clock3, ExternalLink, FileStack, FileText, House, Search, UserRound } from 'lucide-react';
import { apiClient } from '@/api/client';
import { FieldBeam } from '@/components/FieldBeam';

interface Entry {
  label: string | null;
  value: string;
  is_date: boolean;
  display?: string;
}

interface DocumentRecord {
  title: string;
  entries: Entry[];
  attachments: { name: string; url: string }[];
}

export interface EngineerRegister {
  source_url: string;
  synced_at: string;
  people: { name: string; column: number; documents: DocumentRecord[] }[];
}

const dateFormat = new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC' });
const syncFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Astrakhan',
});
const calendar = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Astrakhan' });
const mark = (entry: Entry) => entry.value.trim().toLocaleLowerCase('ru');
const isMissing = (doc: DocumentRecord) => doc.entries.some(entry => mark(entry) === 'нет');

const hasPastDate = (doc: DocumentRecord, today: string) =>
  doc.entries.some(entry => entry.is_date && entry.value < today);
const hasNoFile = (doc: DocumentRecord) => doc.attachments.length === 0;
const hasNoData = (doc: DocumentRecord) =>
  isMissing(doc) || doc.entries.every(entry => ['', '-', '—'].includes(mark(entry)));

type Preset = 'all' | 'past' | 'missing' | 'noFile';

function DocumentCard({ doc, today }: { doc: DocumentRecord; today: string }) {
  const dates = doc.entries.filter(entry => entry.is_date);
  const notes = doc.entries.filter(entry => !entry.is_date && !['', 'да', 'нет', '-', '—'].includes(mark(entry)));
  const isGroup = (entry: Entry) => /гр(?:упп[а-я]*)?\.?$/iu.test(mark(entry));
  const groups = notes.filter(isGroup).map(entry => entry.value).join(' · ');
  const note = notes.filter(entry => !isGroup(entry)).map(entry => entry.value).join(' · ');

  return (
    <article className="engineer-document" data-missing={isMissing(doc)}>
      <h3 title={doc.title}>{doc.title}</h3>
      <div className="engineer-document-dates" data-past={hasPastDate(doc, today)}>
        {dates.map((entry, index) => (
          <time key={index} dateTime={entry.value}>{entry.display ?? dateFormat.format(new Date(entry.value))}</time>
        ))}
      </div>
      <div className="engineer-document-group" title={groups || undefined}>{groups}</div>
      <div className="engineer-document-note" title={note || undefined}>{note}</div>
      <div className="engineer-document-badges">
        {hasNoData(doc) && <span className="engineer-issue">Нет данных</span>}
        {hasNoFile(doc) && <span className="engineer-issue">Нет файла</span>}
      </div>
      <div className="engineer-files">
        {doc.attachments.map((file, index) => (
          <a key={file.url} href={file.url} target="_blank" rel="noopener noreferrer" title={file.name} aria-label={'Открыть ' + file.name}>
            <FileText size={15} aria-hidden="true" />
            {doc.attachments.length === 1 ? 'Открыть документ' : 'Документ ' + (index + 1)}
          </a>
        ))}
      </div>
    </article>
  );
}

export function EngineerDocumentsTab({ refreshAt, onHome }: { refreshAt?: string; onHome: () => void }) {
  const [data, setData] = useState<EngineerRegister | null | undefined>();
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [preset, setPreset] = useState<Preset>('all');
  const [selectedColumn, setSelectedColumn] = useState<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiClient.getEngineerDocuments(controller.signal)
      .then(result => {
        if (!controller.signal.aborted) {
          setError('');
          setData(result.register);
        }
      })
      .catch((failure: Error) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [refreshAt]);

  const today = calendar.format(new Date());
  const register = data?.people ?? [];
  const documents = register.flatMap(person => person.documents);
  const checks = {
    past: (doc: DocumentRecord) => hasPastDate(doc, today),
    missing: isMissing,
    noFile: hasNoFile,
  };
  const needsReview = (doc: DocumentRecord) => hasNoData(doc) || hasNoFile(doc) || checks.past(doc);
  const metrics = [
    { id: 'all', count: register.length, label: 'Всего сотрудников' },
    { id: 'past', count: documents.filter(checks.past).length, label: 'Позиций с прошедшей датой' },
    { id: 'missing', count: documents.filter(checks.missing).length, label: 'Позиций с отметкой «нет»' },
    { id: 'noFile', count: documents.filter(checks.noFile).length, label: 'Позиций без привязанного файла' },
  ] as const;
  const surname = query.trim().toLocaleLowerCase('ru');
  const people = register.filter(person => person.name.toLocaleLowerCase('ru').includes(surname))
    .map(person => ({
      ...person,
      visible: person.documents.filter(doc =>
        preset === 'all' || checks[preset](doc)),
    }))
    .filter(person => preset === 'all' || person.visible.length > 0);
  const selected = people.find(person => person.column === selectedColumn);

  return (
    <section className="engineer-register">
      <header className="workspace-heading workspace-pagebar engineer-pagebar">
        <div className="engineer-title">
          <div>
            <div className="workspace-eyebrow"><FileStack size={15} /> ENTERPRISE HUB</div>
            <h1>Документы инженеров</h1>
          </div>
          <button type="button" className="workspace-icon-button workspace-home-button" aria-label="К обзору" title="К обзору" onClick={onHome}><House size={17} /></button>
        </div>
        {data && <div className="engineer-toolbar">
          <div className="engineer-source">
            <a className="workspace-sheet-link" href={data.source_url} target="_blank" rel="noopener noreferrer"><ExternalLink size={15} /> Открыть таблицу в Google</a>
            <div className="engineer-updated"><Clock3 size={15} /><span>Обновлено <time dateTime={data.synced_at}>{syncFormat.format(new Date(data.synced_at))}</time></span></div>
          </div>
          <FieldBeam className="engineer-search-beam">
            <label className="engineer-search">
              <Search size={16} />
              <input aria-label="Поиск по фамилии" placeholder="Поиск по фамилии" value={query} onChange={event => setQuery(event.target.value)} />
            </label>
          </FieldBeam>
        </div>}
      </header>
      {error && <p role="alert">{error}</p>}
      {!error && data === undefined && <DataLoading />}
      {!error && data === null && <p>Реестр ещё не загружен. Запустите синхронизацию Google Диска.</p>}
      {data && <>
        <div className="engineer-metrics">
          {metrics.map(metric => (
            <button type="button" key={metric.id} aria-pressed={preset === metric.id} onClick={() => {
              setPreset(metric.id === preset ? 'all' : metric.id);
            }}>
              <strong>{metric.count}</strong>{metric.label}
            </button>
          ))}
        </div>
        <div className="engineer-people">
          {people.map(person => {
            const missing = person.documents.filter(isMissing);
            const reviewCount = person.documents.filter(needsReview).length;
            return <button type="button" key={person.column} className="engineer-person" data-missing={missing.length > 0}
              aria-expanded={selected?.column === person.column} aria-controls="engineer-details"
              onClick={() => setSelectedColumn(selectedColumn === person.column ? null : person.column)}>
              <UserRound size={19} aria-hidden="true" />
              <strong>{person.name}</strong>
              {missing.length > 0 && <small>{missing.map(doc => doc.title).join(', ')}</small>}
              {missing.length === 0 && reviewCount > 0 && <small>На проверку · {reviewCount}</small>}
            </button>;
          })}
        </div>
        {people.length === 0 && <p>Сотрудники по этому фильтру не найдены.</p>}
        <div id="engineer-details" hidden={!selected}>
          {selected && <section className="workspace-panel engineer-details" aria-label={'Документы · ' + selected.name}>
            <h2>{selected.name}</h2>
            <div className="engineer-documents">
              {selected.visible.map(doc => <DocumentCard key={doc.title} doc={doc} today={today} />)}
            </div>
          </section>}
        </div>
      </>}
    </section>
  );
}
