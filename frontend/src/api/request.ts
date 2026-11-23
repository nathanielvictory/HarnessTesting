interface ApiError {
  detail?: string | { msg: string }[];
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Harness could not complete the request.';
}

export async function request<T>(path: string, body?: object, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, {
    signal,
    ...(body === undefined ? {} : {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  });

  if (!response.ok) {
    const error: ApiError | null = await response.json().catch(() => null);
    const detail = error?.detail;
    const message = Array.isArray(detail) ? detail.map(issue => issue.msg).join(' ') : detail;
    throw new Error(message || `Harness could not complete the request (${response.status}).`);
  }
  return response.json();
}
