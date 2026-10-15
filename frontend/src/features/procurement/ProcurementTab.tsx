import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { ShoppingBag, Truck } from 'lucide-react';

export function ProcurementTab() {
  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <ShoppingBag className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            Снабжение и закупки
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Реестр счетов, закупка ТМЦ по объектам строительства и статус поставок
          </p>
        </div>
        <div>
          <Badge variant="neutral">Модуль снабжения</Badge>
        </div>
      </div>

      <Card padding="md">
        <div className="py-12 text-center space-y-3">
          <div className="mx-auto w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-400">
            <Truck className="h-6 w-6" />
          </div>
          <h3 className="text-base font-medium text-slate-900 dark:text-slate-100">
            Реестр ТМЦ и график поставок
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            Здесь будут отображаться позиции счетов поставщиков, привязка к сметам объектов и статусы движения материалов.
          </p>
        </div>
      </Card>
    </div>
  );
}
