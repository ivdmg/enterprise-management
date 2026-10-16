import { useState } from 'react';
import { Modal } from '@/components/Modal';
import { Button } from '@/components/Button';
import type { DispatchRecordData, DispatchStatus } from '@/types';
import { Wrench, Clock } from 'lucide-react';

interface LogIncidentModalProps {
  isOpen: boolean;
  onClose: () => void;
  record: DispatchRecordData | null;
  onSubmit: (
    recordId: string,
    payload: {
      status: DispatchStatus;
      downtime_reason: string;
      downtime_hours: number;
      incident_notes?: string;
    }
  ) => Promise<void>;
}

const COMMON_REASONS = [
  'Поломка гидравлической системы / подъемника',
  'Неисправность двигателя / ходовой части',
  'Задержка подачи самосвалов / подвоза смеси',
  'Погодные условия (ливень, гололед, шквал)',
  'Ожидание допуска / наряда / геодезической разбивки',
  'Отсутствие фронта работ по вине смежников',
];

export function LogIncidentModal({
  isOpen,
  onClose,
  record,
  onSubmit,
}: LogIncidentModalProps) {
  const [incidentType, setIncidentType] = useState<DispatchStatus>('repair');
  const [reason, setReason] = useState(COMMON_REASONS[0]);
  const [customReason, setCustomReason] = useState('');
  const [hours, setHours] = useState('2.0');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!record) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const finalReason = reason === 'custom' ? customReason.trim() : reason;
    if (!finalReason) return;

    setSubmitting(true);
    try {
      await onSubmit(record.id, {
        status: incidentType,
        downtime_reason: finalReason,
        downtime_hours: parseFloat(hours) || 1,
        incident_notes: notes.trim() || undefined,
      });
      onClose();
    } catch (err) {
      console.error('Failed to log incident:', err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Зафиксировать поломку / простой"
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Resource info card */}
        <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200/80 dark:border-slate-800 text-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-semibold text-slate-400">Ресурс / Объект:</span>
            <span className="font-mono text-slate-500">{record.shift_date}</span>
          </div>
          <p className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
            {record.unit_name}
          </p>
          <p className="text-slate-500 dark:text-slate-400">
            {record.target_object} · Отв.: {record.responsible_person}
          </p>
        </div>

        {/* Incident Type Selector */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
            Категория инцидента
          </label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setIncidentType('repair')}
              className={`p-3 rounded-lg border text-xs font-semibold flex items-center justify-center gap-2 transition-all min-h-[44px] ${
                incidentType === 'repair'
                  ? 'bg-rose-50 border-rose-300 text-rose-700 dark:bg-rose-950/40 dark:border-rose-800 dark:text-rose-300 ring-1 ring-rose-400'
                  : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400'
              }`}
            >
              <Wrench className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" />
              <span>Поломка / Ремонт</span>
            </button>

            <button
              type="button"
              onClick={() => setIncidentType('downtime')}
              className={`p-3 rounded-lg border text-xs font-semibold flex items-center justify-center gap-2 transition-all min-h-[44px] ${
                incidentType === 'downtime'
                  ? 'bg-amber-50 border-amber-300 text-amber-700 dark:bg-amber-950/40 dark:border-amber-800 dark:text-amber-300 ring-1 ring-amber-400'
                  : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400'
              }`}
            >
              <Clock className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <span>Технический простой</span>
            </button>
          </div>
        </div>

        {/* Common Reasons Dropdown */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
            Типовая причина
          </label>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {COMMON_REASONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
            <option value="custom">Другая причина (ввести вручную)</option>
          </select>

          {reason === 'custom' && (
            <input
              type="text"
              value={customReason}
              onChange={(e) => setCustomReason(e.target.value)}
              placeholder="Укажите точную причину..."
              required
              className="w-full mt-2 px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          )}
        </div>

        {/* Downtime Hours */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
            Продолжительность простоя (часов)
          </label>
          <input
            type="number"
            step="0.5"
            min="0.5"
            max="24"
            value={hours}
            onChange={(e) => setHours(e.target.value)}
            required
            className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
          />
        </div>

        {/* Notes / Action Taken */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
            Принятые меры / комментарий диспетчера
          </label>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Например: Вызвана выездная ремонтная бригада, запчасти со склада выданы..."
            className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500 placeholder:text-slate-400"
          />
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
          <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
            Отмена
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Сохранение...' : 'Зафиксировать инцидент'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
