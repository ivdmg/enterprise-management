import type {
  ApiResponse,
  AuthTokens,
  UserProfile,
  LoginRequest,
  RegisterRequest,
  FileUploadData,
  FileListItem,
  MappingPreviewData,
  MappingConfirmRequest,
  MappingConfirmData,
  DashboardSummary,
  FinanceData,
  Project,
  Alert,
  PayrollData,
  TelegramSettings,
  DriveSyncResult,
  DriveSyncStatus,
  TaskItem,
  TaskWorkflowStatus,
  UploadAndAssignPayload,
  UploadAndAssignResult,
  TenderStage,
  ProcurementItemData,
  ProcurementStatus,
  DispatchRecordData,
  DispatchStatus,
} from '@/types';
import { mockData } from '@/mocks';

const USE_MOCKS = true; // Switch to false when backend is ready
const BASE_URL = '/api/v1';

function getToken(): string | null {
  const saved = localStorage.getItem('seh-tokens');
  if (!saved) return null;
  try {
    return JSON.parse(saved).access_token;
  } catch {
    return null;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData?.error?.message || `HTTP Error ${response.status}`);
  }

  const json: ApiResponse<T> = await response.json();
  if (!json.success) {
    throw new Error(json.error?.message || 'Unknown error');
  }
  return json.data;
}

// Mock delay to simulate network
function delay(ms = 400): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const apiClient = {
  // --- Auth ---
  async login(data: LoginRequest): Promise<AuthTokens> {
    if (USE_MOCKS) {
      await delay();
      return mockData.authTokens;
    }
    return request<AuthTokens>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async register(data: RegisterRequest): Promise<AuthTokens> {
    if (USE_MOCKS) {
      await delay();
      return mockData.authTokens;
    }
    return request<AuthTokens>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getProfile(): Promise<UserProfile> {
    if (USE_MOCKS) {
      await delay(200);
      return mockData.userProfile;
    }
    return request<UserProfile>('/auth/me');
  },

  // --- Files ---
  async uploadFile(file: File): Promise<FileUploadData> {
    if (USE_MOCKS) {
      await delay(1500);
      return mockData.fileUpload;
    }
    const formData = new FormData();
    formData.append('file', file);
    return request<FileUploadData>('/files/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async uploadAndAssignFile(payload: UploadAndAssignPayload): Promise<UploadAndAssignResult> {
    if (USE_MOCKS) {
      await delay(1200);
      const fileId = `c1000000-0000-0000-0000-${Date.now().toString().slice(-12)}`;
      const taskId = `t0000000-0000-0000-0000-${Date.now().toString().slice(-12)}`;
      const driveLink = `https://docs.google.com/spreadsheets/d/mock-accounting-${Date.now()}/edit`;

      const newFile: FileListItem = {
        id: fileId,
        original_name: payload.file.name,
        file_size_bytes: payload.file.size,
        status: 'processed',
        uploaded_by: 'Сидоров А.П. (Бухгалтер)',
        created_at: new Date().toISOString(),
      };
      mockData.filesList.unshift(newFile);

      const newTask: TaskItem = {
        id: taskId,
        task_title: `Согласование с заказчиком: ${payload.file.name}`,
        description:
          payload.comment ||
          'Отчет по взаиморасчетам от бухгалтерии для согласования с заказчиком.',
        related_contract: payload.contract_id_or_name || 'ТЭП-101 / Кислородный цех №101',
        responsible_role: payload.assignee_role || 'manager',
        responsible_person: 'Иванов И.И. (Менеджер проектов)',
        due_date: new Date(Date.now() + 3 * 86400 * 1000).toISOString().split('T')[0],
        days_remaining: 3,
        is_urgent: true,
        source: 'accounting',
        source_label: 'От бухгалтерии',
        status: 'transferred_to_manager',
        priority: 'high',
        document_name: payload.file.name,
        google_drive_link: driveLink,
        created_at: new Date().toISOString(),
      };
      mockData.tasks.unshift(newTask);

      return {
        file_id: fileId,
        task_id: taskId,
        file_name: payload.file.name,
        google_drive_folder: payload.target_folder,
        google_drive_link: driveLink,
        assigned_to_role: payload.assignee_role || 'manager',
        status: 'transferred_to_manager',
        message: 'Файл успешно загружен на Google Диск и передан менеджеру проектов',
      };
    }

    const formData = new FormData();
    formData.append('file', payload.file);
    formData.append('target_folder', payload.target_folder);
    formData.append('comment', payload.comment);
    if (payload.assignee_role) formData.append('assignee_role', payload.assignee_role);
    if (payload.contract_id_or_name)
      formData.append('contract_id_or_name', payload.contract_id_or_name);

    return request<UploadAndAssignResult>('/files/upload-and-assign', {
      method: 'POST',
      body: formData,
    });
  },

  async getFiles(): Promise<FileListItem[]> {
    if (USE_MOCKS) {
      await delay();
      return mockData.filesList;
    }
    return request<FileListItem[]>('/files');
  },

  async getMappingPreview(fileId: string, sheetName?: string): Promise<MappingPreviewData> {
    if (USE_MOCKS) {
      await delay(600);
      return mockData.mappingPreview;
    }
    const params = sheetName ? `?sheet_name=${encodeURIComponent(sheetName)}` : '';
    return request<MappingPreviewData>(`/files/${fileId}/mapping-preview${params}`);
  },

  async confirmMapping(fileId: string, data: MappingConfirmRequest): Promise<MappingConfirmData> {
    if (USE_MOCKS) {
      await delay(800);
      return mockData.mappingConfirm;
    }
    return request<MappingConfirmData>(`/files/${fileId}/mapping-confirm`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // --- Dashboard ---
  async getDashboardSummary(): Promise<DashboardSummary> {
    if (USE_MOCKS) {
      await delay();
      return mockData.dashboardSummary;
    }
    return request<DashboardSummary>('/dashboard/summary');
  },

  async getFinanceData(period?: string): Promise<FinanceData> {
    if (USE_MOCKS) {
      await delay();
      return mockData.financeData;
    }
    const params = period ? `?period=${period}` : '';
    return request<FinanceData>(`/dashboard/finance${params}`);
  },

  async getProjects(status?: string, riskLevel?: string): Promise<Project[]> {
    if (USE_MOCKS) {
      await delay();
      return mockData.projects;
    }
    const searchParams = new URLSearchParams();
    if (status) searchParams.set('status', status);
    if (riskLevel) searchParams.set('risk_level', riskLevel);
    const qs = searchParams.toString();
    return request<Project[]>(`/dashboard/projects${qs ? `?${qs}` : ''}`);
  },

  async getPayroll(period?: string): Promise<PayrollData> {
    if (USE_MOCKS) {
      await delay();
      return mockData.payrollData;
    }
    const params = period ? `?period=${period}` : '';
    return request<PayrollData>(`/dashboard/payroll${params}`);
  },

  // --- Alerts ---
  async getAlerts(severity?: string, isResolved = false): Promise<Alert[]> {
    if (USE_MOCKS) {
      await delay();
      return mockData.alerts;
    }
    const searchParams = new URLSearchParams();
    if (severity) searchParams.set('severity', severity);
    searchParams.set('is_resolved', String(isResolved));
    const qs = searchParams.toString();
    return request<Alert[]>(`/alerts?${qs}`);
  },

  async resolveAlert(alertId: string, comment: string): Promise<void> {
    if (USE_MOCKS) {
      await delay();
      return;
    }
    await request(`/alerts/${alertId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution_comment: comment }),
    });
  },

  // --- Integrations & Settings ---
  async getTelegramSettings(): Promise<TelegramSettings> {
    if (USE_MOCKS) {
      await delay();
      return mockData.telegramSettings;
    }
    return request<TelegramSettings>('/integrations/telegram');
  },

  async updateTelegramSettings(settings: Partial<TelegramSettings>): Promise<void> {
    if (USE_MOCKS) {
      await delay();
      Object.assign(mockData.telegramSettings, settings);
      return;
    }
    await request('/integrations/telegram', {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
  },

  async testTelegramSend(): Promise<{ status: string; message: string }> {
    if (USE_MOCKS) {
      await delay(600);
      return {
        status: 'delivered',
        message: 'Тестовое уведомление успешно доставлено в Telegram!',
      };
    }
    return request<{ status: string; message: string }>('/integrations/telegram/test-send', {
      method: 'POST',
    });
  },

  // --- Google Drive Sync ---
  async syncDriveNow(): Promise<DriveSyncResult> {
    if (USE_MOCKS) {
      await delay(1200);
      const updatedTimestamp = new Date().toISOString();
      mockData.driveSyncStatus.last_synced_at = updatedTimestamp;
      mockData.driveSyncStatus.status = 'idle';
      mockData.driveSyncResult.last_synced_at = updatedTimestamp;
      return {
        ...mockData.driveSyncResult,
        last_synced_at: updatedTimestamp,
      };
    }
    return request<DriveSyncResult>('/sync/drive-now', {
      method: 'POST',
    });
  },

  async getDriveSyncStatus(): Promise<DriveSyncStatus> {
    if (USE_MOCKS) {
      await delay(200);
      return mockData.driveSyncStatus;
    }
    return request<DriveSyncStatus>('/sync/status');
  },

  // --- Tasks & Smart Register ---
  async getTasks(params?: {
    role?: string;
    urgent?: boolean;
    source?: string;
    status?: string;
  }): Promise<TaskItem[]> {
    if (USE_MOCKS) {
      await delay(300);
      let list = [...mockData.tasks];
      if (params?.role && params.role !== 'all') {
        list = list.filter((t) => t.responsible_role === params.role);
      }
      if (params?.urgent) {
        list = list.filter(
          (t) => (t.days_remaining !== undefined && t.days_remaining <= 5) || t.is_urgent
        );
      }
      if (params?.source) {
        list = list.filter((t) => t.source === params.source);
      }
      if (params?.status) {
        list = list.filter((t) => t.status === params.status);
      }
      return list;
    }
    const searchParams = new URLSearchParams();
    if (params?.role && params.role !== 'all') searchParams.set('role', params.role);
    if (params?.urgent) searchParams.set('urgent', 'true');
    if (params?.source) searchParams.set('source', params.source);
    if (params?.status) searchParams.set('status', params.status);
    const qs = searchParams.toString();
    return request<TaskItem[]>(`/tasks${qs ? `?${qs}` : ''}`);
  },

  async updateTaskStatus(
    taskId: string,
    status: TaskWorkflowStatus
  ): Promise<{ id: string; status: TaskWorkflowStatus }> {
    if (USE_MOCKS) {
      await delay(150);
      const item = mockData.tasks.find((t) => t.id === taskId);
      if (item) {
        (item as TaskItem).status = status;
      }
      return { id: taskId, status };
    }
    return request<{ id: string; status: TaskWorkflowStatus }>(`/tasks/${taskId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  },

  async updateProjectTenderStage(
    projectId: string,
    tender_stage: TenderStage
  ): Promise<{ id: string; tender_stage: TenderStage }> {
    if (USE_MOCKS) {
      await delay(150);
      const project = mockData.projects.find((p) => p.id === projectId);
      if (project) {
        project.tender_stage = tender_stage;
      }
      return { id: projectId, tender_stage };
    }
    return request<{ id: string; tender_stage: TenderStage }>(
      `/dashboard/projects/${projectId}/stage`,
      {
        method: 'PATCH',
        body: JSON.stringify({ tender_stage }),
      }
    );
  },

  // --- Procurement & Supply (FE-5.2) ---
  async getProcurementItems(params?: {
    project_name?: string;
    status?: ProcurementStatus;
  }): Promise<ProcurementItemData[]> {
    if (USE_MOCKS) {
      await delay(200);
      let list = [...mockData.procurementItems];
      if (params?.project_name && params.project_name !== 'all') {
        list = list.filter((item) => item.project_name === params.project_name);
      }
      if (params?.status) {
        list = list.filter((item) => item.status === params.status);
      }
      return list;
    }
    const searchParams = new URLSearchParams();
    if (params?.project_name && params.project_name !== 'all') {
      searchParams.set('project_name', params.project_name);
    }
    if (params?.status) searchParams.set('status', params.status);
    const qs = searchParams.toString();
    return request<ProcurementItemData[]>(`/procurement/items${qs ? `?${qs}` : ''}`);
  },

  async updateProcurementStatus(
    itemId: string,
    status: ProcurementStatus
  ): Promise<{ id: string; status: ProcurementStatus }> {
    if (USE_MOCKS) {
      await delay(150);
      const item = mockData.procurementItems.find((p) => p.id === itemId);
      if (item) {
        item.status = status;
      }
      return { id: itemId, status };
    }
    return request<{ id: string; status: ProcurementStatus }>(
      `/procurement/items/${itemId}/status`,
      {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }
    );
  },

  // --- Dispatch & Fleet (FE-5.3) ---
  async getDispatchRecords(params?: {
    status?: DispatchStatus;
    resource_type?: 'machinery' | 'crew';
  }): Promise<DispatchRecordData[]> {
    if (USE_MOCKS) {
      await delay(200);
      let list = [...mockData.dispatchRecords];
      if (params?.status) {
        list = list.filter((rec) => rec.status === params.status);
      }
      if (params?.resource_type) {
        list = list.filter((rec) => rec.resource_type === params.resource_type);
      }
      return list;
    }
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.resource_type) searchParams.set('resource_type', params.resource_type);
    const qs = searchParams.toString();
    return request<DispatchRecordData[]>(`/dispatch/records${qs ? `?${qs}` : ''}`);
  },

  async updateDispatchStatus(
    recordId: string,
    status: DispatchStatus
  ): Promise<{ id: string; status: DispatchStatus }> {
    if (USE_MOCKS) {
      await delay(150);
      const record = mockData.dispatchRecords.find((r) => r.id === recordId);
      if (record) {
        record.status = status;
        if (status === 'on_site') {
          record.downtime_hours = undefined;
          record.downtime_reason = undefined;
        }
      }
      return { id: recordId, status };
    }
    return request<{ id: string; status: DispatchStatus }>(`/dispatch/records/${recordId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  },

  async logDispatchIncident(
    recordId: string,
    payload: {
      status?: DispatchStatus;
      downtime_reason: string;
      downtime_hours: number;
      incident_notes?: string;
    }
  ): Promise<DispatchRecordData> {
    if (USE_MOCKS) {
      await delay(250);
      const record = mockData.dispatchRecords.find((r) => r.id === recordId);
      if (record) {
        record.status = payload.status || 'repair';
        record.downtime_reason = payload.downtime_reason;
        record.downtime_hours = payload.downtime_hours;
        if (payload.incident_notes) {
          record.incident_notes = payload.incident_notes;
        }
        return { ...record };
      }
      throw new Error('Record not found');
    }
    return request<DispatchRecordData>(`/dispatch/records/${recordId}/incident`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};


