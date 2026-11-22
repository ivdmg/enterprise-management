import type { Project, TaskItem } from '@/types';

export function overdueWorkflowTasks(tasks: TaskItem[]) {
  return tasks.filter(task => task.project_id && task.status !== 'approved_closed' &&
    (task.status === 'overdue' || (task.days_remaining ?? 0) < 0));
}

export function workflowRiskTest(overdueTasks: TaskItem[]) {
  const projectIds = new Set(overdueTasks.map(task => task.project_id));
  return (project: Project) => project.days_overdue > 0 || project.risk_level !== 'normal' ||
    projectIds.has(project.id);
}
