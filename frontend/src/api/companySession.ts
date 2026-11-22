import { showcaseMode } from './mode';
import type { ApiResponse, UserProfile } from '@/types';

const apiOrigin = (import.meta.env.VITE_API_ORIGIN ?? '').trim().replace(/\/+$/, '');
export const companyClientEnabled = !showcaseMode && (import.meta.env.VITE_PLATFORM_CLIENT === 'true'
  || /^\/c\//.test(window.location.pathname));

export interface CompanyProfile extends UserProfile {
  company: { id: string; code: string; name: string };
  permissions: string[];
}

export type LoginStep =
  | { step: 'authenticated'; profile: CompanyProfile; recovery_codes?: string[] }
  | { step: 'mfa_required' | 'mfa_enrollment_required'; challenge_id: string; expires_at: string };

export class CompanyRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

let generation = 0;
let csrf: Promise<string> | undefined;
let refresh: Promise<CompanyProfile> | undefined;

export function resetCompanySession() {
  generation += 1;
  csrf = undefined;
  refresh = undefined;
}

async function send<T>(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (typeof options.body === 'string') headers.set('Content-Type', 'application/json');
  const response = await fetch(`${apiOrigin}/api/v1${path}`, {
    ...options,
    credentials: 'include',
    cache: 'no-store',
    headers,
  });
  const body: ApiResponse<T> | null = await response.json().catch(() => null);
  if (!response.ok || !body?.success) {
    throw new CompanyRequestError(response.status, body?.error?.code ?? '', body?.error?.message ?? 'Сервис недоступен.');
  }
  return body.data;
}

function csrfToken() {
  if (!csrf) {
    const pending = send<{ csrf_token: string }>('/auth/csrf').then(data => data.csrf_token);
    csrf = pending;
    void pending.catch(() => { if (csrf === pending) csrf = undefined; });
  }
  return csrf;
}

async function sendWithCsrf<T>(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (options.method && !['GET', 'HEAD', 'OPTIONS'].includes(options.method)) {
    const current = generation;
    headers.set('X-CSRF-Token', await csrfToken());
    if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
  }
  return send<T>(path, { ...options, headers });
}

export function refreshCompanySession() {
  if (!refresh) {
    const current = generation;
    const rotate = async () => {
      if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
      csrf = undefined;
      try {
        return await send<CompanyProfile>('/auth/me');
      } catch (failure) {
        if (!(failure instanceof CompanyRequestError) || failure.code !== 'SESSION_REQUIRED') throw failure;
      }
      try {
        return await sendWithCsrf<CompanyProfile>('/auth/refresh', { method: 'POST' });
      } catch (failure) {
        if (failure instanceof CompanyRequestError && failure.code === 'CSRF_FAILED') {
          throw new CompanyRequestError(401, 'SESSION_REQUIRED', 'Войдите в свой кабинет.');
        }
        throw failure;
      }
    };
    const pending = (navigator.locks ? navigator.locks.request('seh-company-refresh', rotate) : rotate()).then(profile => {
      if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
      csrf = undefined;
      return profile;
    });
    refresh = pending;
    const clear = () => { if (refresh === pending) refresh = undefined; };
    void pending.then(clear, clear);
  }
  return refresh;
}

export async function companyRequest<T>(path: string, options: RequestInit = {}) {
  const current = generation;
  try {
    let data: T;
    try {
      data = await sendWithCsrf<T>(path, options);
    } catch (error) {
      if (!(error instanceof CompanyRequestError) || error.code !== 'SESSION_REQUIRED' || current !== generation) throw error;
      await refreshCompanySession();
      if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
      data = await sendWithCsrf<T>(path, options);
    }
    if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
    return data;
  } catch (error) {
    if (current === generation && error instanceof CompanyRequestError
      && (error.code === 'SESSION_REQUIRED' || error.code === 'COMPANY_PAUSED')) {
      window.dispatchEvent(new Event('seh-company-session-ended'));
    }
    throw error;
  }
}

function authPost<T>(path: string, payload?: object) {
  return sendWithCsrf<T>(path, { method: 'POST', body: payload && JSON.stringify(payload) });
}

export const companyAuth = {
  profile: () => companyRequest<CompanyProfile>('/auth/me'),
  login: (company_code: string, email: string, password: string) =>
    authPost<LoginStep>('/auth/login', { company_code, email, password }),
  setupMfa: (challenge_id: string) => authPost<{ secret: string }>('/auth/mfa/setup', { challenge_id }),
  verifyMfa: (challenge_id: string, code: string) => authPost<LoginStep>('/auth/mfa/verify', { challenge_id, code }),
  accept: (token: string, password: string, full_name: string) =>
    authPost('/auth/invitation/accept', { token, password, full_name }),
  forgot: (company_code: string, email: string) => authPost('/auth/password/forgot', { company_code, email }),
  reset: (token: string, password: string) => authPost('/auth/password/reset', { token, password }),
  confirmEmail: (token: string) => authPost('/auth/email-change/confirm', { token }),
  logout: () => authPost('/auth/logout'),
};
