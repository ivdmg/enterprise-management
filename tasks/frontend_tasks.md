# Задачи для Frontend-разработчика: Устранение багов верстки, Плотная корпоративная палитра, Удаление селектора ролей и Мобильный адаптив (v2.1)
## Роль: Senior React / TypeScript Developer | Проект: Smart Enterprise Hub

---

## 🎯 Системный промпт для Frontend-агента (Скопируйте в новый чат)

> **Твоя роль**: Ты — ведущий Senior Frontend разработчик платформы Smart Enterprise Hub.
> **Твоя цель**: Устранить дефекты верстки таблиц (наезды колонок, горизонтальные скроллы, разнобой размеров плашек), полностью удалить селектор ролей из Header, заменить неоновые/розовые цвета бейджей на плотные благородные корпоративные оттенки, адаптировать ConfirmModal под тёмную тему и реализовать безупречный мобильный UX (Бургер-меню, Sticky Bottom Bar, адаптивные карточки и графики под iPhone 16 Pro Max / Pixel).
>
> **Стек и инструменты**:
> - **React 19 + TypeScript + Vite + Tailwind CSS v4 (`@tailwindcss/vite`) + Lucide React (`lucide-react`)**.
> - UI-архитектура: Модульный headless UI-кит на Tailwind CSS в стиле Shadcn/Radix ([frontend/src/components/](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/)).
>
> **Критические правила разработки**:
> 1. **НЕ трогать бэкенд (Python/FastAPI)**. Все правки ведутся строго внутри директории [`frontend/`](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend).
> 2. **Ликвидация неоновости и полупрозрачности**: Убрать все «неоновые», полупрозрачные и розовые оттенки из алертов и статусов. Использовать плотные, благородные, непрозрачные корпоративные цвета:
>    - 🔴 **Критический (Red/Danger)**: Плотный красный `#DC2626` / `#EF4444`, мягкий фон `bg-red-50 dark:bg-red-950/60`, граница `border-red-300 dark:border-red-800`, контрастный текст `text-red-700 dark:text-red-200`.
>    - 🟡 **Предупреждение (Amber/Warning)**: Плотный янтарный `#D97706` / `#F59E0B`, мягкий фон `bg-amber-50 dark:bg-amber-950/60`, граница `border-amber-300 dark:border-amber-800`, текст `text-amber-800 dark:text-amber-200`.
>    - 🟢 **Норма (Emerald/Success)**: Плотный изумрудно-зеленый `#16A34A` / `#22C55E`, фон `bg-emerald-50 dark:bg-emerald-950/60`, граница `border-emerald-300 dark:border-emerald-800`, текст `text-emerald-800 dark:text-emerald-200`.
> 3. **Никаких нативных селектов ОС**: Все выпадающие списки (`select`) только через кастомный стилизованный компонент [`Select.tsx`](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/Select.tsx).
> 4. **Полное отсутствие горизонтального скролла на десктопе**: Таблицы должны идеально вписываться в границы экрана с фиксированными или пропорциональными ширинами колонок (`table-fixed` или выверенный flex-grid).
> 5. **Защита от дурака**: Смена статусов обязательно запрашивает подтверждение через [`ConfirmModal.tsx`](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/ConfirmModal.tsx), который обязан безупречно выглядеть как в светлой, так и в тёмной теме.
> 6. **Качество адаптива**: Ориентир мобильной верстки — экраны от 375px до 440px (iPhone 16 Pro Max, Google Pixel) и планшеты (768px - 1024px). Ни один элемент не должен вываливаться за пределы экрана (`overflow-x-hidden`).

---

## 📚 Контекст и файлы для изучения

1. [frontend/src/components/Header.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/Header.tsx) — верхняя шапка (удаление селектора роли, добавление мобильного Бургер-меню).
2. [frontend/src/components/TabNav.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/TabNav.tsx) — навигация (на мобильном превращается в Sticky Bottom Bar).
3. [frontend/src/components/ConfirmModal.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/ConfirmModal.tsx) — модальное окно подтверждения (доработка стилей под Dark Mode).
4. [frontend/src/components/Badge.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/Badge.tsx) — статусные плашки и бейджи (замена неоновых оттенков).
5. [frontend/src/features/dashboard/ProjectsTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dashboard/ProjectsTab.tsx) — реестр объектов (наезд степпера на БГ, скролл колонки Риск).
6. [frontend/src/features/procurement/ProcurementTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/procurement/ProcurementTab.tsx) — таблица снабжения (горизонтальный скролл, вылезание статуса «Счет на оплате»).
7. [frontend/src/features/dispatch/DispatchTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dispatch/DispatchTab.tsx) — диспетчерская (разнобой плашек «На объекте», «В ремонте», «Простой»).
8. [frontend/src/features/tasks/TasksTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/tasks/TasksTab.tsx) — смарт-реестр задач (горизонтальный скролл, статусы, модалка).
9. [frontend/src/features/dashboard/FinanceTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dashboard/FinanceTab.tsx) — график финансов (мобильная адаптация Recharts).

---

## 🚦 Правила ведения статуса задач в этом документе

Разработчик обязан вести статус по мере выполнения:
- `[ ] ⏳ В очереди` — задача ожидает старта.
- `[-] 🔄 В работе` — ведется разработка и тестирование.
- `[x] ✅ Завершено (Краткий отчет)` — задача готова, верстка проверена на десктопе и мобильном.
- `[!] ⚠️ Блокер` — обнаружена зависимость или критический баг.

---

## 🛠️ Backlog задач для Frontend-разработчика

### ФАЗА 1: Устранение дефектов верстки десктопных таблиц (P0)

- [x] ✅ **Задача FE-1.1: Разделение колонок «Степпер закупки» и «Банковская гарантия» в ProjectsTab**
  - Файл: [frontend/src/features/dashboard/ProjectsTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dashboard/ProjectsTab.tsx)
  - Выполнено: переведено на `table-fixed` с пропорциями (Объект 25%, Степпер 28% min-w-[240px], БГ 20% min-w-[170px], Сумма 12%, Срок 9%, Риск 6%) и защитными отступами `px-3`, исключающими наложение ячеек.

- [x] ✅ **Задача FE-1.2: Устранение горизонтального скролла и обрезки колонки «Риск» в ProjectsTab**
  - Файл: [frontend/src/features/dashboard/ProjectsTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dashboard/ProjectsTab.tsx)
  - Выполнено: заменен `overflow-x-auto` на `overflow-x-hidden`, бейдж риска сцентрирован с `max-w-[80px]`, горизонтальный скролл на десктопе устранен.

- [x] ✅ **Задача FE-1.3: Ликвидация горизонтального скролла в таблице «Снабжение и закупки» (ProcurementTab)**
  - Файл: [frontend/src/features/procurement/ProcurementTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/procurement/ProcurementTab.tsx)
  - Выполнено: колонка статуса зафиксирована `w-[10%] min-w-[170px]`, кнопка статуса ограничена `max-w-[170px]` с `truncate`, `overflow-x-hidden` на десктопе, сбалансированы ширины ТМЦ/Объекта/Поставщика.

- [x] ✅ **Задача FE-1.4: Унификация плашек статусов в Диспетчерской (DispatchTab)**
  - Файл: [frontend/src/features/dispatch/DispatchTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dispatch/DispatchTab.tsx)
  - Выполнено: кнопки быстрого переключения статусов приведены к единообразному размеру `min-w-[85px] py-1 px-2 text-center text-xs`, отцентрированы в ячейке; таблица переведена на `table-fixed` и `overflow-x-hidden`.

- [x] ✅ **Задача FE-1.5: Разграничение колонок и устранение скролла в Смарт-реестре задач (TasksTab)**
  - Файл: [frontend/src/features/tasks/TasksTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/tasks/TasksTab.tsx)
  - Выполнено: заданы пропорции колонок 30% / 18% / 14% / 14% / 16% / 8%, селектор статуса зафиксирован с `truncate` (`max-w-[170px]`), скролл устранен через `overflow-x-hidden`.

---

## ФАЗА 2: Цветовая палитра — Отказ от неоновости и переход на плотные корпоративные цвета (P0)

- [x] ✅ **Задача FE-2.1: Рефакторинг палитры статусов в Badge.tsx и index.css**
  - Файлы: [frontend/src/components/Badge.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/Badge.tsx), [frontend/src/index.css](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/index.css)
  - Выполнено: заменены все неоновые и полупрозрачные rose/amber/emerald стили на плотные благородные корпоративные оттенки:
    - Danger: `bg-red-50 text-red-800 border-red-300 dark:bg-red-950/70 dark:text-red-200 dark:border-red-800/80`
    - Warning: `bg-amber-50 text-amber-900 border-amber-300 dark:bg-amber-950/70 dark:text-amber-200 dark:border-amber-800/80`
    - Success: `bg-emerald-50 text-emerald-900 border-emerald-300 dark:bg-emerald-950/70 dark:text-emerald-200 dark:border-emerald-800/80`
  - Обновлены глобальные CSS-токены `--semantic-*` в светлой и тёмной теме без розовых и неоновых примесей.

- [x] ✅ **Задача FE-2.2: Обновление карточек алертов экрана «Где горит?» (DashboardTab / FireDetailView)**
  - Файлы: [frontend/src/features/dashboard/DashboardTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dashboard/DashboardTab.tsx), [frontend/src/features/dashboard/components/FirePanel.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dashboard/components/FirePanel.tsx), [frontend/src/features/dashboard/components/FireDetailView.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dashboard/components/FireDetailView.tsx)
  - Выполнено: ключевые 3 карточки сводки («Критические риски», «Внимание и предупреждения», «Штрафы и просрочки») и KPI карточки «Свободная касса» перекрашены в благородные солидные цвета.
  - Детальные карточки в `FireDetailView` оформлены с плотными левыми акцентными полосами (`border-l-4 border-l-red-600` / `border-l-amber-500`) и сдержанными непрозрачными подложками.

---

## ФАЗА 3: Очистка Header и стилизация ConfirmModal в Dark Mode (P0)

- [x] ✅ **Задача FE-3.1: Удаление дропдауна выбора роли из Header (Десктоп и Мобайл)**
  - Файл: [frontend/src/components/Header.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/Header.tsx)
  - Выполнено: селектор роли, модальное окно переключения ролей и связанные с ним иконки/логика полностью удалены из Header на всех брейкпоинтах. Освобожденное пространство отдано под логотип, название системы и статус синхронизации Google Диска.

- [x] ✅ **Задача FE-3.2: Адаптация ConfirmModal под тёмную тему (Dark Mode)**
  - Файл: [frontend/src/components/ConfirmModal.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/ConfirmModal.tsx)
  - Выполнено: фон оверлея настроен как `bg-black/60 backdrop-blur-xs`, карточка диалога — `bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl rounded-2xl`, виджет перехода статусов стилизован для тёмной темы (`dark:bg-slate-800/80 border-slate-700`), статусные иконки переведены на плотную корпоративную гамму без розовых/неоновых оттенков.

---

## ФАЗА 4: Полноценный мобильный адаптив (iPhone 16 Pro Max, Pixel, Tablets) (P0)

- [x] ✅ **Задача FE-4.1: Мобильное Бургер-меню (Navigation Drawer)**
  - Файл: [frontend/src/components/Header.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/Header.tsx)
  - Выполнено: добавлена кнопка Бургера в мобильный Header (`< 768px`). Реализован плавный выезжающий Drawer справа: полный список всех 7 разделов с иконками, переключатель периода отчетов, кнопка синхронизации Google Диска, профиль и кнопка выхода.

- [x] ✅ **Задача FE-4.2: Прилипающая нижняя панель навигации (Sticky Bottom Bar)**
  - Файл: [frontend/src/components/TabNav.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/components/TabNav.tsx)
  - Выполнено: панель зафиксирована внизу экрана `fixed bottom-0 left-0 right-0 z-50 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md pb-[max(0.75rem,env(safe-area-inset-bottom))]`. Выведены 4 ключевые вкладки и кнопка «Разделы», в `App.tsx` добавлен защитный отступ контента `pb-24 md:pb-6`.

- [x] ✅ **Задача FE-4.3: Адаптация карточек и устранение переполнения экрана (No Overflow-X)**
  - Файлы: [frontend/src/App.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/App.tsx), все модули `src/features/*`
  - Выполнено: на корневом контейнере `App.tsx` установлен `max-w-full overflow-x-hidden`. Все таблицы на мобильных устройствах (`< 768px`) скрываются и заменяются на мобильные Bento-карточки и аккордеоны. Исключены вылезания за пределы экранов 375px–440px (iPhone 16 Pro Max, Google Pixel).

- [x] ✅ **Задача FE-4.4: Адаптация финансового графика (Recharts) под мобильные экраны**
  - Файл: [frontend/src/features/dashboard/FinanceTab.tsx](file:///c:/Users/Ivan/Desktop/enterprise%20management/frontend/src/features/dashboard/FinanceTab.tsx)
  - Выполнено: график адаптирован через `h-60 sm:h-72 w-full`, отступы оптимизированы, размер шрифтов меток `10px`, `minTickGap={20}` предотвращает наложение дат, тултип стилизован под компактный тач-виджет, линии и заливки приведены к корпоративным плотным изумрудным и красным тонам (`#16A34A` / `#DC2626`).

---

## 📋 Чек-лист приемки для System Analyst / Tech Lead

Перед сдачей этапа убедиться в выполнении критериев:
1. `ProjectsTab`: степпер и банковская гарантия имеют чёткие независимые границы, колонка «Риск» не вылазит, горизонтальный скролл на экранах $\ge 1280px$ отсутствует.
2. `ProcurementTab`: плашка «Счёт на оплате» аккуратно вписана в ширину ячейки, таблица не скроллится горизонтально.
3. `DispatchTab`: статусы «На объекте», «В ремонте», «Простой» имеют строго одинаковые размеры и центрирование.
4. `TasksTab`: селекторы статусов компактны, таблица вписана в рамки контейнера.
5. `ConfirmModal`: в тёмном режиме фон модалки темный (`bg-slate-900`), контрастный, без белых артефактов.
6. `Header`: селектор роли («Гендиректор...») полностью удален из верстки десктопа и мобайла.
7. Палитра: красные, желтые и зеленые статусы плотные, не неоновые, без розовых оттенков.
8. Мобильная версия (iPhone 16 Pro Max / 430px, Pixel / 412px):
   - Бургер-меню открывает Drawer с навигацией и сервисами.
   - Нижняя навигация прилипает к низу экрана (`fixed bottom-0`).
   - Горизонтальный скролл страницы отсутствует (`overflow-x` чистый).
   - График финансов читаем и не ломает контейнер.
