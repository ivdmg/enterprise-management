import { useEffect, useRef, useState } from 'react';
import { Database, FileUp, Plus, ReceiptText } from 'lucide-react';
import { Liquid } from 'liquid-gooey';

export default function QuickActions({ onUpload, onAccounting, driveLink }: {
  onUpload?: () => void; onAccounting?: () => void; driveLink?: string;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setOpen(false); trigger.current?.focus(); }
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return <div className="workspace-quick-actions" ref={root}>
    <Liquid blur={5} contrast={17} fill="var(--card-subtle)">
      <Liquid.Item>
        <button ref={trigger} type="button" className="workspace-quick-trigger" aria-expanded={open} aria-label={open ? 'Закрыть быстрые действия' : 'Быстрые действия'} onClick={() => setOpen(value => !value)}><Plus size={21} /></button>
      </Liquid.Item>
      {[
        { label: 'Загрузить файл', icon: FileUp, action: onUpload, x: -90, y: 48 },
        { label: 'Передать отчёт 1С', icon: ReceiptText, action: onAccounting, x: -44, y: 58 },
        { label: 'Открыть Google Диск', icon: Database, action: driveLink ? () => window.open(driveLink, '_blank', 'noopener,noreferrer') : undefined, x: 0, y: 49 },
      ].filter(item => item.action).map(({ label, icon: Icon, action, x, y }, index) =>
        <Liquid.Item key={label} className="workspace-quick-item" x={open ? x : 0} y={open ? y : 0} transition="bouncy" delay={index * 20}>
          <button type="button" disabled={!open} aria-hidden={!open} aria-label={label} title={label}
            onClick={() => { setOpen(false); action?.(); }}><Icon size={18} /></button>
        </Liquid.Item>,
      )}
    </Liquid>
  </div>;
}
