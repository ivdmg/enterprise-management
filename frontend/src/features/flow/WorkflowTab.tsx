import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ArrowRight, CircleAlert, Clock3, Layers3, ScanLine } from 'lucide-react';
import { apiClient } from '@/api/client';
import { DataLoading } from '@/components/DataLoading';
import { formatDate } from '@/utils/format';
import type { Project, TaskItem } from '@/types';
import './workflow.css';

const stages = {
  preparation: 'Подготовка', submitted: 'Заявка подана', bidding: 'Отбор',
  won: 'Согласовано', guarantee: 'Обеспечение', contract: 'Контракт',
  execution: 'Исполнение', acceptance: 'Приёмка',
};

const lanes = [
  { name: 'Подготовка', description: 'Уточнение и подача', stages: ['preparation', 'submitted'] },
  { name: 'Согласование', description: 'Отбор и оформление', stages: ['bidding', 'won', 'guarantee'] },
  { name: 'Исполнение', description: 'Контракт и работы', stages: ['contract', 'execution'] },
  { name: 'Приёмка', description: 'Завершение работ', stages: ['acceptance'] },
];

type FlowData = { projects: Project[]; tasks: TaskItem[] };

export default function WorkflowTab({ header, onProject }: {
  header: ReactNode;
  onProject: (id: string) => void;
}) {
  const [data, setData] = useState<FlowData>();
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [onlyRisks, setOnlyRisks] = useState(false);
  const [selectedId, setSelectedId] = useState<string>();
  const selectedDetail = useRef<HTMLElement>(null);

  useEffect(() => {
    let active = true;
    setError(false);
    Promise.all([apiClient.getProjects(), apiClient.getTasks()])
      .then(([projects, tasks]) => { if (active) setData({ projects, tasks }); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [attempt]);

  if (error) return <>{header}<div className="workspace-panel" role="alert">
    <p>Не удалось загрузить рабочий поток.</p>
    <button type="button" className="workspace-link" onClick={() => setAttempt(value => value + 1)}>Повторить</button>
  </div></>;
  if (!data) return <>{header}<DataLoading /></>;

  const overdueTasks = data.tasks.filter(task => task.project_id && task.status !== 'approved_closed' &&
    (task.status === 'overdue' || (task.days_remaining ?? 0) < 0));
  const atRisk = (project: Project) => project.days_overdue > 0 || project.risk_level !== 'normal' ||
    overdueTasks.some(task => task.project_id === project.id);
  const projects = [...data.projects].sort((a, b) => Number(atRisk(b)) - Number(atRisk(a)));
  const visible = onlyRisks ? projects.filter(atRisk) : projects;
  const selected = visible.find(project => project.id === selectedId) ?? visible[0];
  const groups = lanes.map(lane => ({
    ...lane, projects: visible.filter(project => project.tender_stage && lane.stages.includes(project.tender_stage)),
  }));
  const unassigned = visible.filter(project => !groups.some(lane => lane.projects.includes(project)));
  const tasks = selected ? overdueTasks.filter(task => task.project_id === selected.id) : [];

  function projectButton(project: Project) {
    const risk = atRisk(project);
    return <button type="button" key={project.id} className="flow-project" data-risk={risk}
      aria-pressed={selected?.id === project.id} onClick={() => {
        setSelectedId(project.id);
        if (window.matchMedia('(max-width: 560px)').matches) {
          window.requestAnimationFrame(() => selectedDetail.current?.focus());
        }
      }}>
      <span className="flow-project-code"><i aria-hidden="true" />{project.project_code ?? 'Объект'}
        {risk && <span className="flow-risk-label">Требует внимания</span>}</span>
      <strong>{project.project_name}</strong>
      <span className="flow-project-stage">{project.tender_stage ? stages[project.tender_stage] : 'Этап не указан'}</span>
    </button>;
  }

  return <section className="flow-page">
    {header}
    <div className="flow-board">
      <div className="flow-toolbar">
        <div><ScanLine size={20} aria-hidden="true" /><h2>Объекты по этапам</h2></div>
        <button type="button" className="workspace-catalog-button" aria-pressed={onlyRisks}
          onClick={() => setOnlyRisks(value => !value)}>
          <CircleAlert size={16} aria-hidden="true" /> Только риски · {projects.filter(atRisk).length}
        </button>
      </div>
      {!visible.length ? <p className="flow-empty">{onlyRisks ? 'Объектов с риском нет.' : 'Объектов пока нет.'}</p> :
        <div className="flow-lanes">{groups.map((lane, index) => <section className="flow-lane" key={lane.name}>
          <div className="flow-lane-heading">
            <span className="flow-node" aria-hidden="true"><Layers3 size={14} /></span>
            {index < groups.length - 1 && <span className="flow-track" aria-hidden="true"><ArrowRight size={14} /></span>}
            <h3>{lane.name} <span>{lane.projects.length}</span></h3>
            <p>{lane.description}</p>
          </div>
          <div className="flow-lane-cards">{lane.projects.length ? lane.projects.map(projectButton) : <p className="flow-empty">Нет объектов</p>}</div>
        </section>)}</div>}
      {unassigned.length > 0 && <section className="flow-unassigned"><h3>Этап не указан</h3><div>{unassigned.map(projectButton)}</div></section>}
    </div>
    {selected && <section className="flow-detail workspace-panel" key={selected.id} ref={selectedDetail} tabIndex={-1} aria-label="Выбранный объект">
      <div>
        <span className="flow-detail-code">{selected.project_code} {selected.customer_name && `· ${selected.customer_name}`}</span>
        <h2>{selected.project_name}</h2>
        <dl className="workspace-facts">
          <div><dt>Ответственный</dt><dd>{selected.curator_name ?? 'Не указан'}</dd></div>
          <div><dt>Срок</dt><dd>{selected.deadline_date ? formatDate(selected.deadline_date) : 'Не указан'}</dd></div>
        </dl>
      </div>
      <div className="flow-detail-risk">
        <h3><Clock3 size={16} aria-hidden="true" /> Что требует внимания</h3>
        {selected.days_overdue > 0 && <p className="flow-risk-label">Срок объекта просрочен на {selected.days_overdue} дн.</p>}
        {!!tasks.length && <ul>{tasks.slice(0, 3).map(task => <li key={task.id}>{task.task_title} · {task.responsible_person}</li>)}</ul>}
        {tasks.length > 3 && <p>Ещё просроченных задач: {tasks.length - 3}</p>}
        {!tasks.length && !selected.days_overdue && <p>{atRisk(selected) ? 'Объект отмечен в реестре как требующий внимания.' : 'Просроченных сроков и задач нет.'}</p>}
        <button type="button" className="workspace-link" onClick={() => onProject(selected.id)}>К объекту в реестре <ArrowRight size={16} /></button>
      </div>
    </section>}
  </section>;
}
