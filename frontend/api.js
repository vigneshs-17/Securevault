export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

const FRIENDLY_DETAILS = new Map([
  ['Invalid email or password', 'That email or password doesn’t match. Try again.'],
  ['Current password is incorrect', 'That password doesn’t match. Try again.'],
  ['New password must be different from current password', 'Choose a new password that is different from your current one.'],
  ['Email is already registered', 'An account already uses that email. Try signing in instead.'],
  ['Vault item not found', 'That item is no longer available. Refresh your vault and try again.'],
  ['A secure note cannot be empty', 'Add some content before saving this secure note.'],
]);
function friendlyDetail(detail) {
  const message = String(detail || '').replace(/^Value error,\s*/i, '');
  return FRIENDLY_DETAILS.get(message) || message;
}

// Session tokens are intentionally never persisted in browser storage.
// Local dev (port 3000) calls the API directly; a proxied deployment serves it under /api.
const defaultBase = () => typeof location !== 'undefined' && location.port !== '3000' ? '/api' : 'http://127.0.0.1:8000';
export function createClient(fetcher = fetch, base = defaultBase()) {
  let tokens = null;
  let generation = 0;
  let rotation = null;
  const expired = () => new ApiError('Your session ended. Please sign in again.', 401);
  async function send(path, method = 'GET', body, access) {
    let response;
    try {
      response = await fetcher(base + path, {
        method, headers: { 'Content-Type': 'application/json', ...(access ? { Authorization: `Bearer ${access}` } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: 'no-store', credentials: 'omit', signal: AbortSignal.timeout(15000),
      });
    } catch { throw new ApiError('SecureVault couldn’t connect. Make sure the local service is running, then try again.', 0); }
    let data;
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok) {
      const message = response.status === 429 ? 'Too many sign-in attempts. Wait a minute and try again.'
        : typeof data.detail === 'string' ? friendlyDetail(data.detail)
          : Array.isArray(data.detail) ? data.detail.map(item => friendlyDetail(item.msg)).join(' ')
            : 'This request could not be completed. Please try again.';
      throw new ApiError(message, response.status);
    }
    return data;
  }
  async function request(path, { method = 'GET', body, refresh = true } = {}) {
    if (!tokens) throw expired();
    const version = generation;
    const original = tokens;
    try {
      const data = await send(path, method, body, original.access_token);
      if (version !== generation) throw expired();
      return data;
    } catch (error) {
      if (error.status !== 401 || !refresh || version !== generation || !tokens) throw error;
      if (tokens === original) {
        if (!rotation) {
          rotation = send('/auth/refresh', 'POST', { refresh_token: original.refresh_token })
            .then(next => { if (version === generation) tokens = next; })
            .catch(failure => { if (version === generation && failure.status === 401) tokens = null; throw failure; })
            .finally(() => { rotation = null; });
        }
        await rotation;
      }
      if (version !== generation || !tokens) throw expired();
      const data = await send(path, method, body, tokens.access_token);
      if (version !== generation) throw expired();
      return data;
    }
  }
  return {
    register: credentials => send('/auth/register', 'POST', credentials),
    async login(credentials) {
      const version = ++generation;
      const next = await send('/auth/login', 'POST', credentials);
      if (version !== generation) throw expired();
      tokens = next;
    },
    request,
    async logout() {
      try { await rotation; } catch { /* Revoke the current token if it is still available. */ }
      const previous = tokens; tokens = null; generation++;
      if (previous) await send('/auth/logout', 'POST', { refresh_token: previous.refresh_token });
    },
    clear() { tokens = null; generation++; },
  };
}
