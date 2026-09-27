'use strict';
const $ = (id) => document.getElementById(id);
const sessionMeta = document.querySelector('meta[name="pgos-session"]');
const session = sessionMeta.content;
sessionMeta.remove();
const state = { kinds: {}, kind: '', current: null, dirty: false, guideDirty: false,
  selected: new Set(), prepared: null, busy: false, saving: false, listVersion: 0, openVersion: 0 };
const icons = { '': '◷', goals: '◎', learning: '▤', habits: '✓', knowledge: '◇', journal: '◌', reflections: '▦' };
const guideFields = ['事件', '事实（用户自述）', '感受', '解释（待验证）', '反例与其他解释', '下一步'];
let notificationTimer;

function notify(text) {
  $('notification').textContent = text;
  $('notification').hidden = false;
  clearTimeout(notificationTimer);
  notificationTimer = setTimeout(() => { $('notification').hidden = true; }, 7000);
}
async function api(path, data) {
  const options = { headers: { 'X-PGOS-Session': session }, cache: 'no-store' };
  if (data !== undefined) {
    options.method = 'POST';
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(data);
  }
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error('无法连接本地服务。请确认启动窗口仍在运行；编辑内容暂留在此窗口。'); }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '本地操作失败。');
  return result;
}
function today() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}
function allowNavigate() {
  if (state.saving) { notify('正在保存，请稍候。'); return false; }
  return !(state.dirty || state.guideDirty) || confirm('还有未保存的内容。离开将丢弃本次修改，是否继续？');
}
function updateDirty() {
  state.dirty = true;
  $('save-state').textContent = '未保存';
  $('word-count').textContent = `${$('content').value.length} 字符`;
}
function buildNavigation() {
  const navigation = $('navigation');
  navigation.replaceChildren();
  for (const [key, label] of [['', '最近记录'], ...Object.entries(state.kinds)]) {
    const button = document.createElement('button');
    button.dataset.kind = key;
    button.classList.toggle('active', state.kind === key);
    const icon = document.createElement('span'); icon.className = 'nav-icon'; icon.textContent = icons[key];
    const name = document.createElement('span'); name.textContent = label;
    const count = document.createElement('span'); count.className = 'nav-count'; count.dataset.countKind = key;
    button.append(icon, name, count);
    button.addEventListener('click', () => {
      state.kind = key;
      $('page-title').textContent = label;
      navigation.querySelectorAll('button').forEach((el) => el.classList.toggle('active', el === button));
      refresh().catch((error) => notify(error.message));
    });
    navigation.append(button);
  }
  for (const [kind, label] of Object.entries(state.kinds)) {
    const option = document.createElement('option'); option.value = kind; option.textContent = label;
    $('new-kind').append(option);
    $('search-kind').append(option.cloneNode(true));
  }
}
function updateSelection() {
  $('selected-count').textContent = state.selected.size ? `已选 ${state.selected.size} 条（含筛选外）` : '未选择记录';
  $('open-ai').disabled = state.selected.size === 0;
}
function clearSearchFields() {
  $('search').value = ''; $('search-kind').value = ''; $('date-from').value = '';
  $('date-to').value = ''; $('tag-filter').value = '';
}
function renderRecords(result, searched = false) {
  if (result.counts) {
    const total = Object.values(result.counts).reduce((a, b) => a + b, 0);
    $('total').textContent = total;
    document.querySelectorAll('[data-count-kind]').forEach((el) => {
      el.textContent = el.dataset.countKind ? result.counts[el.dataset.countKind] : total;
    });
  }
  $('result-count').textContent = searched
    ? `显示 ${result.records.length} / ${result.matches} 条匹配${result.scan_limited ? ' · 仅扫描前 500 个文件' : ''}`
    : `${result.records.length} 条记录`;
  const list = $('records'); list.replaceChildren();
  let day = null;
  for (const record of result.records) {
    if (day !== record.date && $('sort').value === 'date') {
      const heading = document.createElement('div'); heading.className = 'day-label';
      heading.textContent = record.date === today() ? `${record.date} · 今天` : record.date;
      list.append(heading); day = record.date;
    }
    const card = document.createElement('article'); card.className = 'record-card';
    card.dataset.id = record.id; card.classList.toggle('active', state.current?.id === record.id);
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = state.selected.has(record.id);
    checkbox.setAttribute('aria-label', `选择用于 AI：${record.title}`);
    checkbox.addEventListener('change', () => {
      if (checkbox.checked && state.selected.size >= 5) { checkbox.checked = false; notify('一次最多选择五条记录。'); return; }
      if (checkbox.checked) state.selected.add(record.id); else state.selected.delete(record.id);
      updateSelection();
    });
    const open = document.createElement('button'); open.className = 'record-open';
    const title = document.createElement('h3'); title.textContent = record.title;
    const preview = document.createElement('p'); preview.textContent = record.preview;
    const type = document.createElement('span'); type.className = 'card-type'; type.textContent = `${state.kinds[record.kind]} · ${record.date}`;
    open.append(title, preview, type);
    open.addEventListener('click', () => openRecord(record.id).catch((error) => notify(error.message)));
    card.append(checkbox, open); list.append(card);
  }
  if (!result.records.length) {
    const empty = document.createElement('p'); empty.className = 'empty-list';
    empty.textContent = searched ? '没有匹配记录。可调整条件后重新搜索。' : '这里还没有记录。点击「新建记录」，从一个小行动开始。';
    list.append(empty);
  }
  if (result.skipped) notify(`${result.skipped} 个文件无法读取或超过大小限制，已跳过；原文件未修改。`);
}
async function refresh() {
  clearSearchFields();
  $('page-title').textContent = state.kind ? state.kinds[state.kind] : '最近记录';
  const version = ++state.listVersion;
  const params = new URLSearchParams({ kind: state.kind, order: $('sort').value });
  const result = await api('/api/records?' + params);
  if (version === state.listVersion) renderRecords(result);
}
async function runSearch(event) {
  event.preventDefault();
  const version = ++state.listVersion;
  const params = new URLSearchParams({ query: $('search').value, kind: $('search-kind').value,
    date_from: $('date-from').value, date_to: $('date-to').value,
    tag: $('tag-filter').value, order: $('sort').value });
  const result = await api('/api/search?' + params);
  if (version !== state.listVersion) return;
  $('page-title').textContent = '搜索结果';
  renderRecords(result, true);
}
function showRecord(record) {
  state.current = record; state.dirty = false; state.guideDirty = false;
  $('welcome').hidden = true; $('editor').hidden = false;
  $('title').value = record.title; $('content').value = record.content;
  $('record-type').textContent = state.kinds[record.kind]; $('record-date').textContent = record.date;
  $('record-location').textContent = 'private/workspace/' + record.relative;
  $('save-state').textContent = '已保存'; $('word-count').textContent = `${record.content.length} 字符`;
  $('reflection-guide').hidden = record.kind !== 'journal';
  $('reflection-guide').open = record.kind === 'journal';
  document.querySelectorAll('#guide-fields textarea').forEach((el) => { el.value = ''; });
  $('action-state').value = 'Suggested';
  document.querySelectorAll('.record-card').forEach((el) => el.classList.toggle('active', el.dataset.id === record.id));
}
async function openRecord(id) {
  if (!allowNavigate()) return;
  const version = ++state.openVersion;
  const record = await api('/api/record?' + new URLSearchParams({ id }));
  if (version === state.openVersion) showRecord(record);
}
function insertGuide() {
  const fields = [...document.querySelectorAll('#guide-fields textarea')];
  if (!fields.some((field) => field.value.trim())) return;
  const text = fields.map((field, i) => `## ${guideFields[i]}\n${field.value.trim() || '未知／未报告'}\n`).join('\n');
  $('content').value += '\n\n## 本次引导补充\n\n' + text + '\n行动状态：' + $('action-state').value + '\n';
  fields.forEach((field) => { field.value = ''; });
  state.guideDirty = false; updateDirty();
}
async function saveRecord() {
  if (!state.current || $('save').disabled) return;
  if (!$('title').value.trim()) { notify('标题不能为空。'); return; }
  if (state.guideDirty) insertGuide();
  const title = $('title').value.trim();
  let content = $('content').value;
  content = /^# .+$/m.test(content) ? content.replace(/^# .+$/m, () => '# ' + title) : '# ' + title + '\n\n' + content;
  $('content').value = content;
  $('word-count').textContent = `${content.length} 字符`;
  $('save').disabled = true; state.saving = true;
  try {
    const record = await api('/api/save', { id: state.current.id, revision: state.current.revision, content });
    // Keep later keystrokes if the user edited while the save was in flight.
    state.current = record;
    if ($('content').value === content && $('title').value.trim() === title && !state.guideDirty) {
      state.dirty = false; $('save-state').textContent = '已保存';
    }
    await refresh(); notify('已保存到本地 Markdown 文件。');
  } finally { $('save').disabled = false; state.saving = false; }
}
function openNew() {
  if (!allowNavigate()) return;
  $('new-kind').value = state.kind || 'goals'; $('new-title').value = ''; $('new-date').value = today();
  $('new-dialog').showModal(); $('new-title').focus();
}
function openDelete() {
  if (!state.current || state.saving) return;
  if (state.dirty || state.guideDirty) { notify('请先保存当前修改，再删除记录；回收站保留的是已保存内容。'); return; }
  state.deleteTarget = { id: state.current.id, revision: state.current.revision };
  $('delete-title').textContent = state.current.title;
  $('delete-dialog').showModal();
}
async function deleteRecord() {
  if (!state.deleteTarget || state.saving) return;
  const target = state.deleteTarget;
  state.saving = true; $('confirm-delete').disabled = true; $('save').disabled = true;
  try {
    await api('/api/delete', { ...target, confirmed: true });
    state.openVersion += 1;
    state.current = null; state.dirty = false; state.guideDirty = false;
    state.selected.delete(target.id); updateSelection();
    state.prepared = null; $('draft').value = ''; $('draft-area').hidden = true;
    $('editor').hidden = true; $('welcome').hidden = false;
    $('title').value = ''; $('content').value = '';
    $('delete-dialog').close(); state.deleteTarget = null;
    await refresh(); notify('已移到回收站，可在左侧「回收站」恢复。');
  } finally { state.saving = false; $('confirm-delete').disabled = false; $('save').disabled = false; }
}
async function openTrash() {
  const result = await api('/api/trash');
  const list = $('trash-records'); list.replaceChildren();
  for (const record of result.records) {
    const row = document.createElement('article'); row.className = 'trash-row';
    const details = document.createElement('div');
    const title = document.createElement('h3'); title.textContent = record.title;
    const meta = document.createElement('p'); meta.textContent = `${state.kinds[record.kind]} · ${record.date} · 移入 ${record.deleted_at.replace('T', ' ')}`;
    details.append(title, meta);
    const restore = document.createElement('button'); restore.textContent = '恢复';
    restore.setAttribute('aria-label', `恢复：${record.title}`);
    restore.addEventListener('click', async () => {
      if (state.saving || state.dirty || state.guideDirty) { notify('请先关闭回收站并保存当前编辑，再恢复记录。'); return; }
      restore.disabled = true;
      try {
        const restored = await api('/api/restore', { trash_id: record.trash_id });
        state.openVersion += 1;
        $('trash-dialog').close(); showRecord(restored);
        state.kind = ''; $('page-title').textContent = '最近记录';
        document.querySelectorAll('#navigation button').forEach((el) => el.classList.toggle('active', el.dataset.kind === ''));
        await refresh(); notify('记录已恢复到原位置。');
      } catch (error) { restore.disabled = false; notify(error.message); }
    });
    row.append(details, restore); list.append(row);
  }
  if (!result.records.length) {
    const empty = document.createElement('p'); empty.className = 'empty-list'; empty.textContent = '回收站是空的。'; list.append(empty);
  }
  if (result.skipped) notify(`${result.skipped} 个回收站项目无法读取，原文件已保留。`);
  $('trash-dialog').showModal();
}
async function createRecord(event) {
  event.preventDefault(); $('submit-new').disabled = true;
  try {
    const record = await api('/api/create', { kind: $('new-kind').value, title: $('new-title').value, date: $('new-date').value });
    $('new-dialog').close(); state.kind = record.kind;
    $('page-title').textContent = state.kinds[state.kind];
    document.querySelectorAll('#navigation button').forEach((el) => el.classList.toggle('active', el.dataset.kind === state.kind));
    showRecord(record); await refresh(); $('content').focus();
  } finally { $('submit-new').disabled = false; }
}
async function openAI() {
  if (state.busy) { notify('已有本机 AI 请求正在进行，请等待完成。'); return; }
  if (state.dirty || state.guideDirty) { notify('请先保存当前修改，再选择记录用于分析。'); return; }
  const prepared = await api('/api/ai/prepare', { ids: [...state.selected] });
  state.prepared = prepared; state.busy = false;
  $('scope-summary').textContent = `已选择 ${prepared.count} 条已保存记录 · 输入 ${prepared.characters} 字符 · 仅此快照 · 15 分钟有效`;
  $('ai-input').textContent = prepared.system + '\n\n所选记录：\n' + prepared.input;
  $('custom-prompt').value = '';
  $('draft-area').hidden = true; $('draft').value = ''; $('confirm-draft').checked = false;
  $('save-draft').disabled = true; $('generate').disabled = true;
  $('model').replaceChildren(new Option('先检测可用模型', ''));
  $('ai-status').textContent = '尚未调用 AI。检测模型不会发送记录内容。';
  $('ai-dialog').showModal();
}
async function loadModels() {
  $('load-models').disabled = true;
  try {
    const result = await api('/api/models');
    $('model').replaceChildren(new Option('请选择本地模型', ''));
    result.models.forEach((model) => $('model').append(new Option(model, model)));
    $('ai-status').textContent = result.models.length ? '已列出本机模型。请核对输入后明确点击发送。' : '没有可用的本地模型；普通记录与搜索仍可使用。';
  } finally { $('load-models').disabled = false; }
}
async function generate() {
  $('custom-prompt').disabled = true;
  state.busy = true; $('generate').disabled = true; $('load-models').disabled = true;
  $('draft-area').hidden = true; $('save-draft').disabled = true; $('confirm-draft').checked = false;
  $('ai-status').textContent = '本机模型正在生成，最多等待约 90 秒。此时尚未保存任何草稿。';
  try {
    const result = await api('/api/ai/generate', { id: state.prepared.id, model: $('model').value, custom_prompt: $('custom-prompt').value });
    $('draft').value = result.draft; $('draft-area').hidden = false;
    $('ai-status').textContent = '草稿仅保留在内存中，尚未写入文件。';
  } finally { state.busy = false; $('generate').disabled = !$('model').value; $('load-models').disabled = false; $('custom-prompt').disabled = false; }
}
async function saveDraft() {
  if (!$('confirm-draft').checked) return;
  $('save-draft').disabled = true;
  try {
    const record = await api('/api/ai/confirm', { id: state.prepared.id, confirmed: true, text: $('draft').value });
    $('ai-dialog').close(); showRecord(record); await refresh(); notify('已保存为新的助手草稿，原记录和长期模型未修改。');
  } catch (error) { $('save-draft').disabled = !$('confirm-draft').checked; throw error; }
}
function bind(id, event, action) {
  $(id).addEventListener(event, (evt) => Promise.resolve().then(() => action(evt)).catch((error) => {
    notify(error.message);
    if (['generate', 'load-models'].includes(id)) $('ai-status').textContent = error.message;
  }));
}
async function start() {
  const info = await api('/api/info'); state.kinds = info.kinds;
  $('mode').textContent = info.demo ? '演示空间 · 全部为虚构数据' : '本地工作空间';
  $('today').textContent = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
  buildNavigation();
  guideFields.forEach((name, index) => {
    const label = document.createElement('label'); label.textContent = name;
    const field = document.createElement('textarea'); field.id = `guide-${index}`;
    field.addEventListener('input', () => { state.guideDirty = true; $('save-state').textContent = '引导内容未保存'; });
    label.append(field); $('guide-fields').append(label);
  });
  bind('action-state', 'change', () => { state.guideDirty = true; });
  bind('insert-guide', 'click', insertGuide);
  bind('create', 'click', openNew); bind('welcome-create', 'click', openNew);
  bind('cancel-new', 'click', () => $('new-dialog').close()); bind('new-form', 'submit', createRecord);
  bind('save', 'click', saveRecord); bind('refresh', 'click', refresh);
  bind('delete-record', 'click', openDelete); bind('confirm-delete', 'click', deleteRecord);
  bind('cancel-delete', 'click', () => $('delete-dialog').close());
  bind('open-trash', 'click', openTrash); bind('close-trash', 'click', () => $('trash-dialog').close());
  bind('title', 'input', updateDirty); bind('content', 'input', updateDirty);
  bind('search-form', 'submit', runSearch);
  bind('reset-filter', 'click', refresh);
  for (const [id, text] of [['heading-insert', '\n## '], ['list-insert', '\n- '], ['check-insert', '\n- [ ] ']]) {
    bind(id, 'click', () => { const editor = $('content'); editor.setRangeText(text, editor.selectionStart, editor.selectionEnd, 'end'); editor.focus(); updateDirty(); });
  }
  bind('open-ai', 'click', openAI); bind('load-models', 'click', loadModels); bind('generate', 'click', generate);
  bind('model', 'change', () => { $('generate').disabled = state.busy || !$('model').value; });
  bind('confirm-draft', 'change', () => { $('save-draft').disabled = !$('confirm-draft').checked || state.busy; });
  bind('save-draft', 'click', saveDraft);
  const closeAI = () => { if (state.busy) { notify('请求仍在进行。即使关闭窗口，也不会自动保存草稿。'); } $('ai-dialog').close(); };
  bind('close-ai', 'click', closeAI);
  bind('exit', 'click', async () => { if (!allowNavigate()) return; await api('/api/shutdown', {}); state.dirty = false; state.guideDirty = false; document.body.replaceChildren(); const message = document.createElement('p'); message.textContent = '本地服务已停止，可以关闭此窗口。'; document.body.append(message); });
  window.addEventListener('beforeunload', (event) => { if (state.dirty || state.guideDirty) { event.preventDefault(); event.returnValue = ''; } });
  document.addEventListener('keydown', (event) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); saveRecord().catch((error) => notify(error.message)); } });
  await refresh();
}
start().catch((error) => notify(error.message));
