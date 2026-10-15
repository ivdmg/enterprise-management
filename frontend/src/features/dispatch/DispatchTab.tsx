import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { Radio, Truck } from 'lucide-react';

export function DispatchTab() {
  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Radio className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            Диспетчерская служба
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Суточный график, координация спецтехники, смен и фиксация инцидентов
          </p>
        </div>
        <div>
          <Badge variant="neutral">Оперативный контроль</Badge>
        </div>
      </div>

      <Card padding="md">
        <div className="py-12 text-center space-y-3">
          <div className="mx-auto w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-400">
            <Truck className="h-6 w-6" />
          </div>
          <h3 className="text-base font-medium text-slate-900 dark:text-slate-100">
            Суточный реестр техники и смен
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            Мобильный чеклист для прорабов и диспетчера: фиксация простоев, поломок и распределение бригад.
          </p>
        </div>
      </Card>
    </div>
  );
}
