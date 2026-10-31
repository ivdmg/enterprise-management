import { useEffect, useState } from 'react';
import { apiClient } from '@/api/client';
type SourceRow = {key:string; source_row:number; values:(string|number|null)[]};
export type CustomerTender = {source_warnings:Record<string,string[]>;id:string;number:string;amount:number|null;link:string;registry:SourceRow|null;monitoring:SourceRow|null;registry_columns:string[];monitoring_columns:string[]};
export function CustomerTendersTab({view}:{view:'summary'|'registry'|'monitoring'}) {
 const [rows,setRows]=useState<CustomerTender[]>([]);const [error,setError]=useState('');const [loading,setLoading]=useState(true);const [search,setSearch]=useState('');
 useEffect(()=>{apiClient.getCustomerTenders().then(setRows).catch(e=>setError(String(e.message))).finally(()=>setLoading(false));},[]);
 if(loading)return <p>Загрузка реестра заказчика…</p>;
 if(error)return <p role="alert">{error}</p>;
 if(!rows.length)return <p>Реестр ещё не импортирован. Нажмите «Синхронизировать Диск».</p>;
 const mode=view==='monitoring'?'monitoring':'registry';
 const headers=rows[0][mode==='registry'?'registry_columns':'monitoring_columns'];
 const filtered=rows.filter(r=>r[mode]&&JSON.stringify(r[mode]?.values).toLocaleLowerCase('ru').includes(search.toLocaleLowerCase('ru')));
 const known=rows.filter(r=>r.amount!==null);
 return <section className="space-y-4">
 <div className="flex justify-between items-center gap-4"><h2 className="text-xl font-semibold">{view==='summary'?'Сводка по таблице заказчика':view==='registry'?'Реест Ольга':'Ежедневный мониторинг'}</h2><a className="text-emerald-600" href={rows[0].link} target="_blank" rel="noreferrer">Открыть исходную таблицу</a></div>
 {view==='summary'&&<><div className="grid grid-cols-1 sm:grid-cols-3 gap-4">{[['Записей реестра',rows.filter(r=>r.registry).length],['Записей мониторинга',rows.filter(r=>r.monitoring).length],['Сумма заполненных контрактов',known.length?known.reduce((s,r)=>s+(r.amount??0),0).toLocaleString('ru-RU')+' ₽':'Не указана']].map(([label,value])=><div key={label} className="p-5 border border-[var(--card-border)] bg-[var(--card-bg)] rounded-xl"><p>{label}</p><strong className="text-2xl">{value}</strong></div>)}</div><p className="text-sm text-[var(--text-sub)]">Суммы указаны у {known.length} из {rows.filter(r=>r.registry).length} записей. Пустые значения не считаются нулевыми оплатами или задолженностью. Мониторинг связан с реестром по внутреннему номеру.</p></>}
 {Object.entries(rows[0].source_warnings||{}).filter(([,warnings])=>warnings.length).map(([sheet,warnings])=><details key={sheet} className="p-3 border border-amber-500 rounded-xl"><summary>{sheet}: ошибки формул в {warnings.length} строках исходника</summary><p>Эти строки не импортированы: исправьте внутренний номер в Google Таблице и синхронизируйте повторно.</p>{warnings.map(w=><p key={w}>{w}</p>)}</details>)}
 <input aria-label="Поиск по реестру" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Заказчик, город, внутренний номер…" className="w-full p-3 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)]"/>
 <p className="text-sm">Найдено: {filtered.length}. Все поля исходного листа доступны в таблице; прокрутите её вправо.</p>
 <div className="overflow-auto max-h-[65vh] border border-[var(--card-border)] rounded-xl"><table className="text-xs w-full border-collapse"><thead className="sticky top-0 bg-[var(--card-bg)]"><tr>{headers.map((h,i)=><th key={i} className="min-w-44 p-3 text-left border-b border-[var(--card-border)]">{h}</th>)}</tr></thead><tbody>{filtered.map(r=><tr key={r.id} className="border-b border-[var(--card-border)]">{r[mode]!.values.map((v,i)=><td key={i} className="p-3 align-top max-w-80 whitespace-normal">{v===null||v===''?<span className="text-[var(--text-muted)]">—</span>:typeof v==='string'&&/^https?:\/\//.test(v)?<a href={v} target="_blank" rel="noreferrer" className="text-emerald-600">Документы</a>:String(v)}</td>)}</tr>)}</tbody></table></div></section>;
}
