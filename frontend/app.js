import { createClient } from './api.js';
import { icon } from './icons.js';
import { renderLanding } from './landing.js';
import { shell, view, pages, vaultResults, filteredItems, activityResults } from './views.js';
import { escape as esc, button, iconButton, badge, loading, date, modal, passwordField } from './ui.js';
import { initMotion } from './motion.js';
import { generatePassword, passwordStrength, accountPasswordError } from './security.js';

const $ = selector => document.querySelector(selector);
const api = createClient();
const state = {
  user:null, page:'dashboard', items:[], logs:[], sessions:[], localEvents:[], errors:{}, health:null, integrity:null,
  query:'', sort:'newest', activityFilter:'all', activityLimit:30, generated:'',
  generator:{length:20,upper:true,lower:true,numbers:true,symbols:true}, lockMinutes:5, reduceMotion:false,
};
let sessionEpoch=0, detailEpoch=0, detail=null, editing=null, locking=false, scanning=false;
let lockTimer, hideTimer, lastActivity=Date.now(), authMode='login', confirmAction=null;
let observer, stopMotion;

function toast(message, error=false) {
  const element=document.createElement('div'); element.className='toast'+(error?' toast-error':'');
  element.innerHTML=icon(error?'circle-alert':'check');
  const text=document.createElement('span'); text.textContent=message; element.append(text);
  $('#toasts').append(element); setTimeout(()=>element.remove(),6500);
}
function initLanding() {
  $('#landing').innerHTML=renderLanding();
  observer?.disconnect();
  observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('visible');observer.unobserve(entry.target);}}),{threshold:.08});
  document.querySelectorAll('.reveal-section').forEach(section=>observer.observe(section));
  stopMotion?.(); stopMotion=initMotion($('#landing'));
}
initLanding();

function setFormBusy(form,busy) {
  form.setAttribute('aria-busy',String(busy));
  form.querySelectorAll('input,textarea,select,button').forEach(control=>control.disabled=busy);
  const dialog=form.closest('dialog'); if(dialog) {dialog.dataset.busy=String(busy);dialog.querySelector('.dialog-close').disabled=busy;}
}
function auth(next='login',message='') {
  authMode=next; const register=next==='register';
  modal('auth-dialog',`<div class="dialog-brand">${icon('shield')}</div><p class="eyebrow">${register?'YOUR PRIVATE SPACE STARTS HERE':'WELCOME BACK'}</p><h2 id="dialog-title">${register?'Create your vault.':'Your vault awaits.'}</h2><p class="dialog-description">${register?'A little more control over your digital life.':'Sign in to pick up where you left off.'}</p><form id="auth-form"><div class="field"><label for="email">Email address</label><input id="email" type="email" autocomplete="username" placeholder="you@example.com" required maxlength="254"></div>${passwordField('password','Password',{required:true,autocomplete:register?'new-password':'current-password',hint:register?'12+ characters with uppercase, lowercase, a number, and a symbol.':'',max:1024})}${register?passwordField('confirm-password','Confirm password',{required:true,autocomplete:'new-password',max:1024}):''}<p class="form-error ${message?'success':''}" role="status">${esc(message)}</p><button type="submit" class="button primary full">${register?'Create vault':'Open vault'} ${icon('arrow-right')}</button></form><div class="auth-switch">${register?'Already have a vault?':'New to SecureVault?'} <button data-action="${register?'login':'register'}">${register?'Sign in':'Create an account'}</button></div><p class="dialog-note">${icon('lock-keyhole')} Your session stays in this tab’s memory.</p>`);
  $('#email').focus();
}
async function submitAuth(form) {
  const credentials={email:$('#email').value.trim(),password:$('#password').value};
  const error=form.querySelector('.form-error'); error.classList.remove('success');
  if(authMode==='register') {
    const issue=accountPasswordError(credentials.password);
    if(issue){error.textContent=issue;return;}
    if(credentials.password!==$('#confirm-password').value){error.textContent='The passwords don’t match.';$('#confirm-password').focus();return;}
  }
  setFormBusy(form,true);error.textContent=authMode==='register'?'Creating your vault…':'Opening your vault…';
  try {
    if(authMode==='register') {await api.register(credentials);setFormBusy(form,false);auth('login','Your account is ready. Sign in to open your vault.');$('#email').value=credentials.email;$('#password').focus();}
    else {await api.login(credentials);const user=await api.request('/auth/me');setFormBusy(form,false);closeDialog($('#auth-dialog'));state.user=user;sessionEpoch++;$('#landing').hidden=true;stopMotion?.();$('#workspace').hidden=false;$('#workspace').innerHTML=shell(user);$('.skip-link').href='#app-main';$('#app-main').innerHTML=loading();lastActivity=Date.now();startLockTimer();await refreshData();}
  } catch(failure){api.clear();error.textContent=failure.message;setFormBusy(form,false);}
}
async function refreshData() {
  const epoch=sessionEpoch;
  const [items,logs,sessions]=await Promise.allSettled([api.request('/vault/items'),api.request('/audit/logs'),api.request('/auth/sessions')]);
  if(epoch!==sessionEpoch||!state.user)return;
  if(items.status==='rejected'){handleError(items.reason);$('#app-main').innerHTML=`<div class="page-error">${icon('circle-alert')}<h1>Your vault couldn’t load.</h1><p>${esc(items.reason.message)}</p>${button('Try again','refresh','refresh-cw','primary')}</div>`;return;}
  state.items=items.value;
  state.errors={logs:logs.status==='rejected',sessions:sessions.status==='rejected'};
  if(logs.status==='fulfilled')state.logs=logs.value;
  if(sessions.status==='fulfilled')state.sessions=sessions.value;
  render();
}
function render() {
  if(!state.user)return;
  document.querySelectorAll('.nav-item').forEach(item=>{const active=item.dataset.page===state.page;item.classList.toggle('active',active);if(active)item.setAttribute('aria-current','page');else item.removeAttribute('aria-current');});
  $('#nav-count').textContent=state.items.filter(item=>item.item_type!=='note').length;
  $('#breadcrumb-page').textContent=pages[state.page][0];
  $('#app-main').innerHTML=view(state);
  if(state.page==='generator') {if(!state.generated)regenerate();else updateStrength();}
  if(['notes','passwords'].includes(state.page))updateResultCount();
}
function navigate(page) {
  if(!pages[page]||!state.user)return;
  state.page=page;state.query='';state.activityLimit=30;closeMenu();render();window.scrollTo({top:0});$('#app-main').focus();
}
function handleError(error) {
  if(error.status===401&&state.user){clearWorkspace();toast('Your session ended. Sign in again to continue.',true);auth();}
  else toast(error.message||'Something went wrong. Please try again.',true);
}
function closeDialog(dialog) {
  if(dialog.dataset.busy==='true')return;
  dialog.close(); dialog.replaceChildren();
  if(dialog.id==='detail-dialog'){detail=null;detailEpoch++;clearTimeout(hideTimer);}
  if(dialog.id==='edit-dialog')editing=null;
  if(dialog.id==='confirm-dialog')confirmAction=null;
}
document.querySelectorAll('dialog').forEach(dialog=>{
  dialog.addEventListener('cancel',event=>{event.preventDefault();closeDialog(dialog);});
});
function clearWorkspace(clearApi=true) {
  sessionEpoch++;detailEpoch++;scanning=false;state.user=null;state.items=[];state.logs=[];state.sessions=[];state.localEvents=[];state.health=null;state.integrity=null;state.generated='';state.page='dashboard';
  detail=null;editing=null;if(clearApi)api.clear();clearTimeout(lockTimer);clearTimeout(hideTimer);
  document.querySelectorAll('dialog').forEach(dialog=>{dialog.dataset.busy='false';dialog.close();dialog.replaceChildren();});
  $('#workspace').replaceChildren();$('#workspace').hidden=true;$('#landing').hidden=false;$('.skip-link').href='#main';$('#toasts').replaceChildren();window.scrollTo(0,0);
}
async function lockVault() {
  if(locking||!state.user)return;locking=true;
  // Clear visible secrets immediately; the network call only revokes the refresh session.
  const revoke=api.logout();clearWorkspace(false);
  toast('Vault locked. Sign in when you’re ready.');
  try{await revoke;}
  catch{toast('Your vault is locked here. SecureVault couldn’t confirm server sign-out; try again after reconnecting.',true);}
  finally{locking=false;}
}
function startLockTimer() {
  clearTimeout(lockTimer);
  if(!state.user)return;
  const remaining=state.lockMinutes*60000-(Date.now()-lastActivity);
  if(remaining<=0){void lockVault();return;}
  lockTimer=setTimeout(startLockTimer,remaining);
}
function activity() {if(state.user){const previous=lastActivity;lastActivity=Date.now();if(lastActivity-previous>1000)startLockTimer();}}
['pointerdown','keydown','scroll'].forEach(event=>document.addEventListener(event,activity,{passive:true}));
document.addEventListener('visibilitychange',()=>{hideSecrets();if(!document.hidden)startLockTimer();});
window.addEventListener('blur',hideSecrets);
function hideSecrets() {
  document.querySelectorAll('[data-action="reveal"][aria-pressed="true"]').forEach(control=>{
    const field=document.getElementById(control.dataset.target);if(field)field.type='password';control.setAttribute('aria-pressed','false');control.innerHTML=icon('eye');control.setAttribute('aria-label','Show password');
  });
}
function localEvent(action,id=null) {state.localEvents.unshift({action,resource_type:id?'VAULT_ITEM':'AUTH',resource_id:id,created_at:new Date().toISOString(),local:true});}
async function copyText(text,control,action=null,id=null) {
  try {
    await navigator.clipboard.writeText(text);
    if(action)localEvent(action,id);
    const previous=control.innerHTML;control.innerHTML=icon('check')+'<span>Copied</span>';control.classList.add('copied');
    setTimeout(()=>{if(control.isConnected){control.innerHTML=previous;control.classList.remove('copied');}},1700);
    toast('Copied to clipboard. Paste only where you intend to use it.');
  }catch{toast('Clipboard access wasn’t available. Reveal and select the text to copy it manually.',true);}
}
async function openDetail(id) {
  const epoch=sessionEpoch;const requestId=++detailEpoch;detail=null;
  modal('detail-dialog',`<h2 id="detail-title">Opening entry</h2>${loading('Decrypting your entry')}`,{drawer:true,label:'detail-title'});
  try {
    const item=await api.request('/vault/items/'+id);
    if(epoch!==sessionEpoch||requestId!==detailEpoch||!$('#detail-dialog').open)return;
    detail=item;const note=item.item_type==='note';
    modal('detail-dialog',`<span class="detail-service">${note?icon('sticky-note'):esc(item.title[0]?.toUpperCase()||'S')}</span><p class="eyebrow">${note?'SECURE NOTE':'PASSWORD'}</p><h2 id="detail-title">${esc(item.title)}</h2>${badge('Encrypted at rest','positive','lock-keyhole')}<div class="detail-content">${note?`<div class="field"><label for="detail-note">Note content</label><textarea readonly id="detail-note" rows="12">${esc(item.notes)}</textarea></div>${button('Copy note','copy-note','copy','secondary')}`:`<div class="detail-label">Username / email</div><div class="detail-value"><span>${esc(item.username||'Not added')}</span>${item.username?iconButton('Copy username','copy-username','copy'):''}</div>${passwordField('detail-password','Password',{value:item.password,readonly:true})}<div class="detail-actions">${button('Copy password','copy-password','copy','secondary')}${badge(passwordStrength(item.password).label,passwordStrength(item.password).weak?'warning':'positive')}</div><p class="field-hint">Strength is a composition estimate. Revealed passwords hide after 30 seconds.</p><div class="detail-label">Website</div><div class="detail-value">${item.website?`<a href="${esc(item.website)}" target="_blank" rel="noopener noreferrer">${esc(item.website)} ${icon('arrow-up-right')}</a>`:'Not added'}</div>${item.notes?`<div class="detail-label">Private notes</div><p class="note-content">${esc(item.notes)}</p>`:''}`}</div><dl class="detail-metadata"><div><dt>Created</dt><dd>${date(item.created_at)}</dd></div><div><dt>Last updated</dt><dd>${date(item.updated_at)}</dd></div></dl><div class="drawer-footer">${button('Edit entry','edit','pencil','secondary')}${button('Delete','delete','trash-2','danger ghost')}</div>`,{drawer:true,label:'detail-title'});
  }catch(error){if(requestId!==detailEpoch||epoch!==sessionEpoch)return;closeDialog($('#detail-dialog'));handleError(error);}
}
function editEntry(type='password',item=null,generated='') {
  editing=item?{id:item.id,item_type:item.item_type}:null;
  closeDialog($('#detail-dialog'));const note=(item?.item_type||type)==='note';
  modal('edit-dialog',`<p class="eyebrow">${item?'MAKE IT CURRENT':'YOUR VAULT, GROWING'}</p><h2 id="edit-title">${item?'Edit': 'New'} ${note?'secure note':'password'}.</h2><p class="dialog-description">${note?'Keep these words in your own private space.':'The details you need, when you need them.'}</p><form id="entry-form" data-type="${note?'note':'password'}"><div class="field"><label for="entry-title">${note?'Note title':'Service / title'}</label><input id="entry-title" value="${esc(item?.title||'')}" placeholder="${note?'A private thought':'e.g. Personal email'}" required maxlength="255"></div>${note?'':`<div class="field"><label for="entry-username">Username / email <span>Optional</span></label><input id="entry-username" value="${esc(item?.username||'')}" autocomplete="off" maxlength="255"></div>${passwordField('entry-password','Password',{value:generated||item?.password||'',required:true,autocomplete:'off'})}<div class="field-inline">${button('Generate a strong password','fill-generated','wand-sparkles','ghost compact')}</div><div class="field"><label for="entry-website">Website <span>Optional</span></label><input id="entry-website" type="url" placeholder="https://example.com" value="${esc(item?.website||'')}" maxlength="500"></div>`}<div class="field"><label for="entry-notes">${note?'Note content':'Private notes <span>Optional</span>'}</label><textarea id="entry-notes" rows="${note?9:3}" maxlength="10000" ${note?'required':''}>${esc(item?.notes||'')}</textarea></div><p class="form-error" role="status"></p><div class="form-footer">${button('Cancel','close-dialog','','ghost')}<button type="submit" class="button primary">${item?'Save changes':'Save to vault'} ${icon('check')}</button></div></form>`,{label:'edit-title'});
}
async function saveEntry(form) {
  const title=$('#entry-title').value.trim();const notes=$('#entry-notes').value.trim();const note=form.dataset.type==='note';
  const error=form.querySelector('.form-error');
  if(!title||note&&!notes){error.textContent=note?'Add a title and note content.':'Add a title for this entry.';return;}
  const body={title,notes:notes||null};
  if(!note)Object.assign(body,{username:$('#entry-username').value.trim()||null,password:$('#entry-password').value,website:$('#entry-website').value.trim()||null});
  if(!editing)body.item_type=form.dataset.type;
  const epoch=sessionEpoch;const id=editing?.id;setFormBusy(form,true);error.textContent='Saving securely…';
  try{
    await api.request('/vault/items'+(id?'/'+id:''),{method:id?'PATCH':'POST',body});
    if(epoch!==sessionEpoch)return;
    setFormBusy(form,false);closeDialog($('#edit-dialog'));state.health=null;toast(id?'Changes saved.':'Entry added to your vault.');await refreshData();
  }catch(failure){if(epoch!==sessionEpoch)return;setFormBusy(form,false);if(failure.status===401)handleError(failure);else error.textContent=failure.message;}
}
function confirm(title,description,label,action) {
  confirmAction=action;
  modal('confirm-dialog',`<div class="confirmation-icon">${icon('circle-alert')}</div><h2 id="confirm-title">${title}</h2><p class="dialog-description">${description}</p><p class="form-error" role="status"></p><div class="form-footer">${button('Cancel','close-dialog','','ghost')}${button(label,'confirm','','danger')}</div>`,{label:'confirm-title'});
}
async function runConfirmation(control) {
  if(!confirmAction)return;const dialog=$('#confirm-dialog');const action=confirmAction;dialog.dataset.busy='true';dialog.querySelectorAll('button').forEach(button=>button.disabled=true);
  try {await action();dialog.dataset.busy='false';closeDialog(dialog);}
  catch(error){dialog.dataset.busy='false';dialog.querySelectorAll('button').forEach(button=>button.disabled=false);if(error.status===401)handleError(error);else dialog.querySelector('.form-error').textContent=error.message;}
}
function updateResultCount() {const node=$('#filtered-count');const count=filteredItems(state,state.page==='notes').length;if(node)node.textContent=count+(count===1?' entry':' entries');}
function regenerate() {
  try {state.generated=generatePassword(state.generator.length,state.generator);if($('#generated-password'))$('#generated-password').textContent=state.generated;if($('#generator-error'))$('#generator-error').textContent='';updateStrength();}
  catch(error){state.generated='';$('#generated-password').textContent='Choose a character type';$('#generator-error').textContent=error.message;updateStrength();}
}
function updateStrength() {
  if(!$('#strength-track'))return;
  const result=passwordStrength(state.generated);$('#strength-label').textContent=state.generated?result.label:'Not generated';
  $('#strength-track').dataset.score=state.generated?result.score:-1;
  $('#strength-track').querySelectorAll('i').forEach((segment,index)=>segment.classList.toggle('filled',!!state.generated&&index<=result.score));
  document.querySelectorAll('[data-action="copy-generated"],[data-action="save-generated"]').forEach(button=>button.disabled=!state.generated);
}
async function scan() {
  if(scanning)return;scanning=true;const epoch=sessionEpoch;
  if(state.page!=='security')navigate('security');
  const controls=document.querySelectorAll('[data-action="scan"]');controls.forEach(control=>control.disabled=true);
  const status=$('#scan-status');status.innerHTML=loading('Checking passwords');
  const health={items:{},checked:0,weak:0,reused:0,checkedAt:null};const hashes=new Map();
  try {
    for(const item of state.items.filter(item=>item.item_type!=='note')) {
      if(epoch!==sessionEpoch)return;
      let content=await api.request('/vault/items/'+item.id);
      const strength=passwordStrength(content.password);
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(content.password))),byte=>byte.toString(16).padStart(2,'0')).join('');
      content=null;
      hashes.set(hash,[...(hashes.get(hash)||[]),item.id]);health.items[item.id]={...strength,reused:false};health.checked++;if(strength.weak)health.weak++;
      if(status.isConnected)status.textContent=`Checking passwords · ${health.checked} of ${state.items.filter(item=>item.item_type!=='note').length}`;
    }
    for(const ids of hashes.values())if(ids.length>1)for(const id of ids){health.items[id].reused=true;health.reused++;}
    if(epoch!==sessionEpoch)return;
    health.checkedAt=new Date().toISOString();state.health=health;localEvent('SCAN');toast('Password health check complete.');render();
  }catch(error){if(epoch===sessionEpoch){handleError(error);if(status.isConnected)status.textContent='The check could not finish. Try again when your connection is available.';}}
  finally{hashes.clear();scanning=false;controls.forEach(control=>control.disabled=false);}
}
async function verify(control) {
  const epoch=sessionEpoch;control.disabled=true;
  try{const result=await api.request('/audit/verify');if(epoch!==sessionEpoch)return;state.integrity=result;toast(result.valid?'Audit chain integrity verified.':'An audit integrity issue needs review.',!result.valid);render();}
  catch(error){if(epoch===sessionEpoch)handleError(error);}finally{control.disabled=false;}
}
async function changePassword(form) {
  const current=$('#current-password').value;const next=$('#new-password').value;const error=form.querySelector('.form-error');
  const issue=accountPasswordError(next);if(issue){error.textContent=issue;return;}
  if(next!==$('#confirm-new').value){error.textContent='The new passwords don’t match.';return;}
  if(next===current){error.textContent='Choose a password different from your current one.';return;}
  setFormBusy(form,true);const epoch=sessionEpoch;
  try{await api.request('/auth/me');await api.request('/auth/change-password',{method:'POST',body:{current_password:current,new_password:next},refresh:false});if(epoch!==sessionEpoch)return;clearWorkspace();auth('login','Password updated. Sign in with your new password.');}
  catch(failure){if(epoch===sessionEpoch){error.textContent=failure.message;setFormBusy(form,false);}}
}
function closeMenu(){const wasOpen=$('.sidebar')?.classList.contains('open');$('.sidebar')?.classList.remove('open');if($('.app-content'))$('.app-content').inert=false;if($('.sidebar-backdrop'))$('.sidebar-backdrop').hidden=true;const toggle=document.querySelector('[data-action="menu"]');toggle?.setAttribute('aria-expanded','false');if(wasOpen)toggle?.focus();}
matchMedia('(max-width:700px)').addEventListener('change',()=>closeMenu());

document.addEventListener('submit',event=>{
  event.preventDefault();const form=event.target;if(form.getAttribute('aria-busy')==='true')return;
  if(form.id==='auth-form')void submitAuth(form);if(form.id==='entry-form')void saveEntry(form);if(form.id==='change-password-form')void changePassword(form);
});
document.addEventListener('click',async event=>{
  const control=event.target.closest('[data-action]');if(!control||control.disabled)return;
  const action=control.dataset.action;
  try{
    if(action==='login'||action==='register'){if($('#auth-dialog').dataset.busy!=='true')auth(action);}
    else if(action==='navigate')navigate(control.dataset.page);
    else if(action==='menu'){$('.sidebar').classList.add('open');$('.sidebar-backdrop').hidden=false;control.setAttribute('aria-expanded','true');$('.app-content').inert=true;$('.sidebar .nav-item').focus();}
    else if(action==='menu-close')closeMenu();
    else if(action==='close-dialog')closeDialog(control.closest('dialog'));
    else if(action==='lock')await lockVault();
    else if(action==='refresh'){control.disabled=true;await refreshData();control.disabled=false;}
    else if(action==='new'||action==='new-password')editEntry('password');
    else if(action==='new-note')editEntry('note');
    else if(action==='detail')await openDetail(Number(control.dataset.id));
    else if(action==='edit'&&detail){const item=detail;editEntry(item.item_type,item);}
    else if(action==='reveal'){
      const field=document.getElementById(control.dataset.target);const visible=field.type==='password';field.type=visible?'text':'password';control.innerHTML=icon(visible?'eye-off':'eye');control.setAttribute('aria-label',visible?'Hide password':'Show password');control.setAttribute('aria-pressed',String(visible));
      clearTimeout(hideTimer);if(visible)hideTimer=setTimeout(hideSecrets,30000);
    }
    else if(action==='copy-password'&&detail)await copyText(detail.password,control,'COPY',detail.id);
    else if(action==='copy-note'&&detail)await copyText(detail.notes||'',control,'COPY_NOTE',detail.id);
    else if(action==='copy-username'&&detail)await copyText(detail.username||'',control);
    else if(action==='delete'&&detail){const id=detail.id;const title=detail.title;confirm('Delete this entry?',`“${esc(title)}” will be permanently removed from your vault. This cannot be undone.`,'Delete entry',async()=>{await api.request('/vault/items/'+id,{method:'DELETE'});closeDialog($('#detail-dialog'));state.health=null;toast('Entry deleted.');await refreshData();});}
    else if(action==='confirm')await runConfirmation(control);
    else if(action==='logout-all')confirm('Sign out all sessions?','Every session will need to sign in again, including this one. Saved entries will stay in your vault.','Sign out all',async()=>{await api.request('/auth/logout-all',{method:'POST'});clearWorkspace();toast('All sessions signed out.');});
    else if(action==='generate')regenerate();
    else if(action==='copy-generated'&&state.generated)await copyText(state.generated,control);
    else if(action==='save-generated'&&state.generated)editEntry('password',null,state.generated);
    else if(action==='fill-generated'){$('#entry-password').value=generatePassword(24,{upper:true,lower:true,numbers:true,symbols:true});toast('A new random password is ready. Save the entry to keep it.');}
    else if(action==='scan')await scan();
    else if(action==='verify')await verify(control);
    else if(action==='clear-search'){state.query='';$('#vault-search').value='';$('#vault-results').innerHTML=vaultResults(state,state.page==='notes');updateResultCount();}
    else if(action==='activity-filter'){state.activityFilter=control.dataset.filter;state.activityLimit=30;render();}
    else if(action==='more-activity'){state.activityLimit+=30;$('#activity-results').innerHTML=activityResults(state);}
  }catch(error){handleError(error);}
});
document.addEventListener('input',event=>{
  const control=event.target;
  if(control.id==='vault-search'){state.query=control.value;$('#vault-results').innerHTML=vaultResults(state,state.page==='notes');updateResultCount();}
  if(control.id==='password-length'){state.generator.length=Number(control.value);$('#length-output').textContent=control.value;regenerate();}
});
document.addEventListener('change',event=>{
  const control=event.target;
  if(control.dataset.generator){state.generator[control.dataset.generator]=control.checked;regenerate();}
  if(control.id==='sort-items'){state.sort=control.value;$('#vault-results').innerHTML=vaultResults(state,state.page==='notes');updateResultCount();}
  if(control.id==='auto-lock'){state.lockMinutes=Number(control.value);startLockTimer();toast('Auto-lock updated for this session.');}
  if(control.id==='reduce-motion'){state.reduceMotion=control.checked;document.documentElement.classList.toggle('reduce-motion',control.checked);}
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape')closeMenu();
  if(event.key==='/'&&!event.target.matches('input,textarea,select')&&!document.querySelector('dialog[open]')&&$('#vault-search')){event.preventDefault();$('#vault-search').focus();}
});
