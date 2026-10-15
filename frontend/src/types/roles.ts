export type EnterpriseRoleId =
  | 'ceo'
  | 'coo'
  | 'tender'
  | 'engineer'
  | 'dispatcher'
  | 'manager'
  | 'lawyer'
  | 'procurement'
  | 'accountant';

export interface EnterpriseRoleDefinition {
  id: EnterpriseRoleId;
  name: string;
  shortName: string;
  department: string;
  description: string;
  primaryTab: string;
  focusTabs: string[];
  iconName: string;
}

export const ENTERPRISE_ROLES: EnterpriseRoleDefinition[] = [
  {
    id: 'ceo',
    name: 'Генеральный директор (CEO)',
    shortName: 'Гендиректор',
    department: 'Руководство',
    description: 'Стратегический контроль за 60 секунд, предотвращение кассовых разрывов и рисков РНП.',
    primaryTab: 'summary',
    focusTabs: ['summary', 'finance', 'tenders'],
    iconName: 'Crown',
  },
  {
    id: 'coo',
    name: 'Зам. генерального директора (COO)',
    shortName: 'Зам. гендиректора',
    department: 'Руководство',
    description: 'Оперативное управление всеми отделами, снятие межфункциональных блокировок.',
    primaryTab: 'summary',
    focusTabs: ['summary', 'tenders', 'tasks', 'dispatch'],
    iconName: 'ShieldCheck',
  },
  {
    id: 'tender',
    name: 'Тендерный специалист',
    shortName: 'Тендерщик',
    department: 'Тендерный отдел',
    description: 'Ведение воронки тендеров, соблюдение сроков подачи, торгов и банковских гарантий.',
    primaryTab: 'tenders',
    focusTabs: ['tenders', 'tasks', 'files'],
    iconName: 'Briefcase',
  },
  {
    id: 'engineer',
    name: 'Инженер ПТО / Главный инженер',
    shortName: 'Инженер ПТО',
    department: 'Производство / ПТО',
    description: 'Сдача физических объемов на объектах, подписанные акты КС-2/КС-3, исполнительная документация.',
    primaryTab: 'tenders',
    focusTabs: ['tenders', 'dispatch', 'files'],
    iconName: 'HardHat',
  },
  {
    id: 'dispatcher',
    name: 'Диспетчер (Техника и логистика)',
    shortName: 'Диспетчер',
    department: 'Логистика',
    description: 'Координация суточных смен, перемещение спецтехники и бригад, фиксация простоев и поломок.',
    primaryTab: 'dispatch',
    focusTabs: ['dispatch', 'tasks'],
    iconName: 'Radio',
  },
  {
    id: 'manager',
    name: 'Менеджер проектов / Координатор',
    shortName: 'Менеджер проектов',
    department: 'Управление проектами',
    description: 'Связующее звено: получение документов от бухгалтерии/ПТО и оперативная передача заказчику.',
    primaryTab: 'tasks',
    focusTabs: ['tasks', 'tenders', 'files'],
    iconName: 'Layers',
  },
  {
    id: 'lawyer',
    name: 'Корпоративный юрист',
    shortName: 'Юрист',
    department: 'Юридический отдел',
    description: 'Контроль условий контрактов 44/223-ФЗ, протоколы разногласий до 5 дней, претензионная работа.',
    primaryTab: 'tasks',
    focusTabs: ['tasks', 'tenders', 'files'],
    iconName: 'Scale',
  },
  {
    id: 'procurement',
    name: 'Закупщик / Снабженец',
    shortName: 'Снабженец',
    department: 'Снабжение',
    description: 'Своевременная поставка материалов под график СМР, реестр счетов и долги поставщикам.',
    primaryTab: 'procurement',
    focusTabs: ['procurement', 'finance', 'tasks'],
    iconName: 'ShoppingBag',
  },
  {
    id: 'accountant',
    name: 'Главный бухгалтер / Бухгалтер',
    shortName: 'Бухгалтер',
    department: 'Бухгалтерия',
    description: 'Движение денежных средств, экспорт отчетов 1С, проведение платежей, контроль ФОТ.',
    primaryTab: 'finance',
    focusTabs: ['finance', 'files', 'tasks'],
    iconName: 'Receipt',
  },
];
