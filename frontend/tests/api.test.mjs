import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createClient } from '../api.js';
const response = (status, data) => ({ ok: status < 400, status, json: async () => data });
test('concurrent expired requests share one rotation and logout revokes the latest token', async () => {
  let refreshes = 0; let revoked;
  const api = createClient(async (url, options) => {
    if (url.endsWith('/login')) return response(200, { access_token: 'old', refresh_token: 'r1' });
    if (url.endsWith('/refresh')) { refreshes++; await new Promise(resolve => setTimeout(resolve, 5)); return response(200, { access_token: 'new', refresh_token: 'r2' }); }
    if (url.endsWith('/logout')) { revoked = JSON.parse(options.body).refresh_token; return response(200, {}); }
    return options.headers.Authorization === 'Bearer new' ? response(200, []) : response(401, {});
  });
  await api.login({}); await Promise.all([api.request('/vault/items'), api.request('/auth/me')]);
  assert.equal(refreshes, 1); await api.logout(); assert.equal(revoked, 'r2');
  await assert.rejects(api.request('/auth/me'), error => error.status === 401);
});
test('failed refresh clears session and rate limiting produces useful feedback', async () => {
  const api = createClient(async url => url.endsWith('/login') ? response(200, { access_token: 'a', refresh_token: 'r' }) : response(401, {}));
  await api.login({}); await assert.rejects(api.request('/auth/me')); await assert.rejects(api.request('/auth/me'));
  const limited = createClient(async () => response(429, {}));
  await assert.rejects(limited.login({}), /Wait a minute/);
});
test('network failures are actionable and server messages are not interpreted as markup', async () => {
  const offline = createClient(async () => { throw new Error('network'); });
  await assert.rejects(offline.login({}), /local service is running/);
  const invalid = createClient(async () => response(400, { detail: '<script>bad</script>' }));
  await assert.rejects(invalid.register({}), error => error.message === '<script>bad</script>');
});

test('a response arriving after session clear cannot resurrect private data', async()=>{
  let resolve;
  const api=createClient(async url=>url.endsWith('/login')?response(200,{access_token:'a',refresh_token:'r'}):new Promise(done=>{resolve=done;}));
  await api.login({});const pending=api.request('/vault/items');api.clear();resolve(response(200,[{title:'private'}]));
  await assert.rejects(pending,error=>error.status===401);
});
test('password-change validation errors do not rotate the session; mutations preserve their body', async()=>{
  let refreshes=0;let body;
  const api=createClient(async(url,options)=>{
    if(url.endsWith('/login'))return response(200,{access_token:'a',refresh_token:'r'});
    if(url.endsWith('/refresh'))refreshes++;
    body=JSON.parse(options.body);return response(401,{detail:'Current password is incorrect'});
  });
  await api.login({});await assert.rejects(api.request('/auth/change-password',{method:'POST',body:{current_password:'bad'},refresh:false}),/password doesn’t match/);
  assert.equal(refreshes,0);assert.deepEqual(body,{current_password:'bad'});
});

test('known server errors are translated into calm, helpful guidance', async()=>{
  const login=createClient(async()=>response(401,{detail:'Invalid email or password'}));
  await assert.rejects(login.login({}),/doesn’t match\. Try again/);
  const existing=createClient(async()=>response(409,{detail:'Email is already registered'}));
  await assert.rejects(existing.register({}),/Try signing in instead/);
});
