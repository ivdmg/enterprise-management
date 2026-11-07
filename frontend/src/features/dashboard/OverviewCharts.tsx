import { useEffect, useState } from 'react';
import { Activity, ArrowUpRight, PieChart as PieIcon, Wallet } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { apiClient } from '@/api/client';
import type { FinanceData } from '@/types';

const compact = new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 1 });
const shortDay = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const colors = ['var(--chart-primary)', 'var(--chart-secondary)', 'var(--chart-tertiary)', 'var(--chart-muted)'];
const tooltipStyle = { background: 'var(--card-bg)', borderColor: 'var(--card-border)', borderRadius: 12, color: 'var(--text-main)' };

export function OverviewCharts({ statuses, onFinance, onRegistry, obligations, onMonitoring }: {
  statuses: { name: string; value: number }[];
  onFinance: () => void;
  onRegistry: () => void;
  obligations: { id: string; title: string; subtitle: string; date: string; label: string; action: () => void }[];
  onMonitoring: () => void;
}) {
  const [period, setPeriod] = useState('month');
  const [finance, setFinance] = useState<FinanceData | null>();
  useEffect(() => {
    let active = true;
    apiClient.getFinanceData(period).then(data => { if (active) setFinance(data); })
      .catch(() => { if (active) setFinance(null); });
    return () => { active = false; };
  }, [period]);

  const total = statuses.reduce((sum, status) => sum + status.value, 0);
  return <><div className="workspace-analytics">
    <section className="workspace-panel workspace-chart">
      <div className="workspace-chart-head">
        <div className="workspace-chart-title"><span><Activity size={17} /></span><div><h2>Движение средств</h2><p>Поступления и расходы</p></div></div>
        <div className="workspace-chart-controls">
          <div className="workspace-segment" role="group" aria-label="Период графика">
            {[['month', 'Месяц'], ['quarter', '90 дней'], ['year', 'Год']].map(([id, label]) =>
              <button key={id} aria-pressed={period === id} onClick={() => { if (period !== id) { setFinance(undefined); setPeriod(id); } }}>{label}</button>,
            )}
          </div>
          <button className="workspace-icon-button" aria-label="Открыть финансы" onClick={onFinance}><ArrowUpRight size={17} /></button>
        </div>
      </div>
      {finance?.dynamics.length ? <>
        <div className="workspace-chart-legend"><span><i /> Поступления <b>{compact.format(finance.total_incoming)} ₽</b></span><span><i /> Расходы <b>{compact.format(finance.total_outgoing)} ₽</b></span></div>
        <div className="workspace-plot" role="img" aria-label="График поступлений и расходов по датам">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <AreaChart data={finance.dynamics} margin={{ left: -8, right: 10, top: 8, bottom: 0 }}>
              <defs><linearGradient id="overview-inflow" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="var(--chart-primary)" stopOpacity={0.32} /><stop offset="100%" stopColor="var(--chart-primary)" stopOpacity={0.02} /></linearGradient></defs>
              <CartesianGrid vertical={false} stroke="var(--card-border)" strokeDasharray="4 4" />
              <XAxis dataKey="date" tickFormatter={date => shortDay.format(new Date(date))} minTickGap={28} tick={{ fill: 'var(--text-sub)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={value => compact.format(value)} tick={{ fill: 'var(--text-sub)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip labelFormatter={date => typeof date === 'string' ? shortDay.format(new Date(date)) : ''} formatter={value => `${Number(value).toLocaleString('ru-RU')} ₽`} contentStyle={tooltipStyle} />
              <Area isAnimationActive="auto" animationDuration={1100} type="monotone" dataKey="incoming" name="Поступления" stroke="var(--chart-primary)" strokeWidth={2.4} fill="url(#overview-inflow)" />
              <Area isAnimationActive="auto" animationDuration={1100} type="monotone" dataKey="outgoing" name="Расходы" stroke="var(--chart-secondary)" strokeWidth={2} strokeDasharray="5 4" fill="transparent" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </> : <div className="workspace-chart-empty"><Wallet size={24} /><p>{finance === undefined ? 'Загружаем операции…' : finance === null ? 'Не удалось загрузить операции' : 'За этот период операций нет'}</p></div>}
    </section>
    <section className="workspace-panel workspace-chart">
      <div className="workspace-chart-head">
        <div className="workspace-chart-title"><div><h2>Ближайшие обязательства</h2></div></div>
        <button className="workspace-icon-button" aria-label="Открыть мониторинг" onClick={onMonitoring}><ArrowUpRight size={17} /></button>
      </div>
      {obligations.length ? <ul className="workspace-obligations">{obligations.map(item =>
        <li key={item.id}>
          <span className="workspace-obligation-avatar" aria-hidden="true">{item.title.trim().charAt(0)}</span>
          <div><small>{item.subtitle}</small><b>{item.title}</b></div>
          <div className="workspace-obligation-date"><small>{item.label}</small><b>{shortDay.format(new Date(item.date))}</b></div>
          <button className="workspace-icon-button" onClick={item.action} aria-label={`Открыть сроки: ${item.title}`}><ArrowUpRight size={15} /></button>
        </li>
      )}</ul> : <div className="workspace-chart-empty"><p>Нет обязательств с подтверждённой близкой датой.</p></div>}
    </section>
  </div>
  <div className="workspace-analytics workspace-analytics-secondary">
    <section className="workspace-panel workspace-chart">
      <div className="workspace-chart-head">
        <div className="workspace-chart-title"><span><PieIcon size={17} /></span><div><h2>Портфель контрактов</h2><p>По статусам реестра</p></div></div>
        <button className="workspace-icon-button" aria-label="Открыть контракты" onClick={onRegistry}><ArrowUpRight size={17} /></button>
      </div>
      <div className="workspace-donut" role="img" aria-label={statuses.map(status => `${status.name}: ${status.value}`).join(', ')}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <PieChart><Pie isAnimationActive="auto" animationDuration={1100} data={statuses} dataKey="value" nameKey="name" innerRadius="65%" outerRadius="93%" paddingAngle={statuses.length > 1 ? 4 : 0} stroke="none">
            {statuses.map((status, index) => <Cell key={status.name} fill={colors[index % colors.length]} />)}
          </Pie><Tooltip contentStyle={tooltipStyle} /></PieChart>
        </ResponsiveContainer>
        <div className="workspace-donut-label"><strong>{total}</strong><span>контрактов</span></div>
      </div>
      <ul className="workspace-donut-legend">{statuses.map((status, index) => <li key={status.name}><i style={{ background: colors[index % colors.length] }} />{status.name}<b>{status.value}</b></li>)}</ul>
    </section>
  </div></>;
}
