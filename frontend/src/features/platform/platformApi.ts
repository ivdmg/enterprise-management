import type { ApiResponse } from '@/types';

const origin = (import.meta.env.VITE_PLATFORM_API_ORIGIN ?? '').trim().replace(/\/+$/, '');

export interface Operator {
  id: string;
  full_name: string;
  email: string;
  role: 'support' | 'owner';
  permissions: string[];
}

export type OperatorLogin =
  | { step: 'authenticated'; profile: Operator; recovery_codes?: string[] }
  | { step: 'mfa_required' | 'mfa_enrollment_required'; challenge_id: string; expires_at: string };

export class PlatformRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code = "") {
    super('Не удалось выполнить запрос.');
    this.status = status;
    this.code = code;
  }
}

let generation = 0;
let csrf: Promise<string> | undefined;
let refreshing: Promise<Operator> | undefined;

export function resetPlatformSession() {
  generation += 1;
  csrf = undefined;
  refreshing = undefined;
}

async function send<T>(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (typeof init.body === 'string') headers.set('Content-Type', 'application/json');
  const response = await fetch(`${origin}/api/v1/platform${path}`, { ...init, headers, credentials: 'include', cache: 'no-store' });
  const envelope: ApiResponse<T> | null = await response.json().catch(() => null);
  if (!response.ok || !envelope?.success) throw new PlatformRequestError(response.status, envelope?.error?.code);
  return envelope.data;
}

async function withCsrf<T>(path: string, init: RequestInit = {}) {
  const current = generation;
  const headers = new Headers(init.headers);
  if (init.method && !['GET', 'HEAD', 'OPTIONS'].includes(init.method)) {
    if (!csrf) {
      const pending = send<{ csrf_token: string }>('/auth/csrf').then(data => data.csrf_token);
      csrf = pending;
      void pending.catch(() => { if (csrf === pending) csrf = undefined; });
    }
    headers.set('X-CSRF-Token', await csrf);
    if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
  }
  return send<T>(path, { ...init, headers });
}

function refresh() {
  if (!refreshing) {
    const current = generation;
    const rotate = async () => {
      if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
      csrf = undefined;
      try {
        return await send<Operator>('/auth/me');
      } catch (failure) {
        if (!(failure instanceof PlatformRequestError) || failure.code !== 'SESSION_REQUIRED') throw failure;
      }
      try {
        return await withCsrf<Operator>('/auth/refresh', { method: 'POST' });
      } catch (failure) {
        if (failure instanceof PlatformRequestError && failure.code === 'CSRF_FAILED') {
          throw new PlatformRequestError(401, 'SESSION_REQUIRED');
        }
        throw failure;
      }
    };
    const pending = (navigator.locks ? navigator.locks.request('seh-platform-refresh', rotate) : rotate()).then(profile => {
      if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
      csrf = undefined;
      return profile;
    });
    refreshing = pending;
    const clear = () => { if (refreshing === pending) refreshing = undefined; };
    void pending.then(clear, clear);
  }
  return refreshing;
}

export async function platformRequest<T>(path: string, init: RequestInit = {}) {
  const current = generation;
  try {
    let result: T;
    try {
      result = await withCsrf<T>(path, init);
    } catch (failure) {
      if (!(failure instanceof PlatformRequestError) || failure.code !== 'SESSION_REQUIRED' || generation !== current) throw failure;
      await refresh();
      if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
      result = await withCsrf<T>(path, init);
    }
    if (current !== generation) throw new DOMException('Сессия изменилась', 'AbortError');
    return result;
  } catch (failure) {
    if (current === generation && failure instanceof PlatformRequestError && failure.code === 'SESSION_REQUIRED') {
      window.dispatchEvent(new Event('seh-platform-session-ended'));
    }
    throw failure;
  }
}

export function platformPost<T>(path: string, body: object, idempotencyKey?: string) {
  return platformRequest<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
    headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
  });
}

function authPost<T>(path: string, body?: object) {
  return withCsrf<T>(path, { method: 'POST', body: body && JSON.stringify(body) });
}

export const platformAuth = {
  profile: () => platformRequest<Operator>('/auth/me'),
  login: (email: string, password: string) => authPost<OperatorLogin>('/auth/login', { email, password }),
  setup: (challenge_id: string) => authPost<{ secret: string }>('/auth/mfa/setup', { challenge_id }),
  verify: (challenge_id: string, code: string) => authPost<OperatorLogin>('/auth/mfa/verify', { challenge_id, code }),
  invite: (token: string, full_name: string, password: string) => authPost('/auth/invitation/accept', { token, full_name, password }),
  logout: () => authPost('/auth/logout'),
};
