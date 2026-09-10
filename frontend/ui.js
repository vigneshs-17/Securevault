import { icon } from './icons.js';
export const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
export const button = (label, action, glyph, variant = '', attributes = '') => `<button type="button" class="button ${variant}" data-action="${action}" ${attributes}>${glyph ? icon(glyph) : ''}<span>${label}</span></button>`;
export const iconButton = (label, action, glyph, attributes = '') => `<button type="button" class="icon-button" aria-label="${label}" title="${label}" data-action="${action}" ${attributes}>${icon(glyph)}</button>`;
export const badge = (label, tone = '', glyph = '') => `<span class="badge ${tone}">${glyph ? icon(glyph) : ''}${escape(label)}</span>`;
export const brand = () => `<a href="#" class="brand" aria-label="SecureVault home"><span class="brand-mark">${icon('shield')}</span>SecureVault<span class="brand-period">.</span></a>`;
export const empty = (title, description, action = '') => `<div class="empty-state">${icon('shield')}<h3>${title}</h3><p>${description}</p>${action}</div>`;
export const loading = (label = 'Loading your vault') => `<div class="loading" role="status">${icon('loader-circle')}<span>${label}…</span></div>`;
export const date = value => value ? new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z')) : 'Not recorded';
export const eventLabels = {
  LOGIN_SUCCESS: 'Signed in to SecureVault', LOGIN_FAILED: 'Unsuccessful sign-in', CREATE: 'Vault entry created', UPDATE: 'Vault entry updated', DELETE: 'Vault entry deleted', READ: 'Vault entry opened', LOGOUT: 'Signed out', LOGOUT_ALL: 'All sessions signed out', TOKEN_REFRESH: 'Session renewed', PASSWORD_CHANGED: 'Account password changed', ACCESS_DENIED_READ: 'Entry access denied', ACCESS_DENIED_UPDATE: 'Entry update denied', ACCESS_DENIED_DELETE: 'Entry deletion denied', COPY: 'Password copied', SCAN: 'Password health checked', COPY_NOTE: 'Secure note copied',
};
export function timeline(events, limit = 10) {
  if (!events.length) return empty('A fresh start.', 'Your account and vault activity will appear here.');
  return `<ol class="timeline">${events.slice(0, limit).map(event => `<li><span class="timeline-icon">${icon(event.action.includes('LOGIN') ? 'log-out' : event.action === 'COPY' ? 'copy' : 'shield-check')}</span><div><strong>${escape(eventLabels[event.action] || event.action.replaceAll('_', ' ').toLowerCase())}</strong><span>${event.local ? 'This tab · ' : 'Server record · '}${date(event.created_at)}${event.resource_type === 'VAULT_ITEM' ? ` · Entry #${event.resource_id}` : ''}</span></div>${event.action.includes('FAILED') || event.action.includes('DENIED') ? badge('Review', 'warning') : ''}</li>`).join('')}</ol>`;
}
export function passwordField(id, label, { value = '', autocomplete = 'off', required = false, readonly = false, hint = '', max = 4096 } = {}) {
  return `<div class="field"><label for="${id}">${label}</label><div class="password-field"><input id="${id}" type="password" value="${escape(value)}" autocomplete="${autocomplete}" ${required ? 'required' : ''} ${readonly ? 'readonly' : ''} maxlength="${max}" ${hint ? `aria-describedby="${id}-help"` : ''}>${iconButton('Show ' + label.toLowerCase(), 'reveal', 'eye', `data-target="${id}" aria-pressed="false"`)}</div>${hint ? `<p class="field-hint" id="${id}-help">${hint}</p>` : ''}</div>`;
}
export function modal(id, content, { drawer = false, label = 'dialog-title' } = {}) {
  const dialog = document.getElementById(id);
  dialog.className = drawer ? 'dialog drawer' : 'dialog';
  dialog.setAttribute('aria-labelledby', label);
  dialog.innerHTML = `<button type="button" class="icon-button dialog-close" aria-label="Close dialog" data-action="close-dialog">${icon('x')}</button>${content}`;
  if (!dialog.open) dialog.showModal();
  return dialog;
}
