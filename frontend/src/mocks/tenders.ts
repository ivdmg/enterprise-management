import { mockData } from './index';
import type { CustomerTender } from '@/features/dashboard/CustomerTendersTab';

const day = 86_400_000;
const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Astrakhan', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());

export function demoDate(offset: number) {
  return new Date(Date.parse(today) + offset * day).toISOString().slice(0, 10);
}

export function demoTenders(): CustomerTender[] {
  const offsets = [-4, 2, 5, 9, 13];
  return mockData.projects.map((project, index) => {
    const values: (string | number | null)[] = Array(22).fill(null);
    const monitoring: (string | number | null)[] = Array(25).fill(null);
    const number = project.project_code ?? String(index + 101);
    values[0] = monitoring[0] = number;
    values[1] = monitoring[1] = project.customer_name ?? 'Демо-заказчик';
    values[3] = monitoring[3] = ['Астрахань', 'Казань', 'Самара'][index % 3];
    values[9] = project.project_name;
    values[15] = project.contract_sum;
    values[16] = index === 4 ? 'Завершен' : 'На исполнении';
    values[18] = demoDate(offsets[index % offsets.length]);
    monitoring[4] = demoDate(index - 6);
    if (index >= 3) monitoring[5] = demoDate(index - 4);
    return {
      id: project.id, number, amount: project.contract_sum, link: null, curator: project.curator_name,
      registry: { source_row: index + 4, values }, monitoring: { source_row: index + 4, values: monitoring },
      registry_columns: [], monitoring_columns: [], source_warnings: {},
    };
  });
}
