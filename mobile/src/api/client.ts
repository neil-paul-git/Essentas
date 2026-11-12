// The only place the app talks to the network. Everything goes through our backend.

const API_URL = process.env.EXPO_PUBLIC_API_URL;

// fetch() in React Native has no default timeout, so a wrong IP would hang for a long time.
const TIMEOUT_MS = 5000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function apiBaseUrl(): string {
  if (!API_URL) {
    throw new ApiError('EXPO_PUBLIC_API_URL is not set. Copy mobile/.env.example to mobile/.env.');
  }
  return `${API_URL.replace(/\/+$/, '')}/api/v1`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const url = `${apiBaseUrl()}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new ApiError(`${response.status} from ${url}`, response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const reason = controller.signal.aborted ? 'timed out' : 'could not connect';
    throw new ApiError(`Request to ${url} ${reason}.`);
  } finally {
    clearTimeout(timer);
  }
}

// Mirrors HealthResponse in backend/app/schemas/health.py.
export type HealthResponse = {
  status: 'ok';
  version: string;
  environment: string;
};

export function getHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/health');
}
