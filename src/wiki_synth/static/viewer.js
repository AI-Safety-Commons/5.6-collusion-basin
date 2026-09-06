const $ = id => document.getElementById(id);
const json = value => JSON.stringify(value, null, 2);
const display = value => value === null || value === undefined ? '—' : String(value);
let generation = 0;
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
async function get(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Unable to load run');
  return data;
}
function disclosure(title, text) {
  const details = node('details');
  details.append(node('summary', title), node('pre', text));
  return details;
}
function metric(label, value) {
  const box = node('div', undefined, 'metric');
  box.append(node('span', label), node('strong', display(value)));
  return box;
}
function message({record, request}) {
  const article = node('article');
  const header = node('div', undefined, 'message-header');
  const tags = node('div', undefined, 'tags');
  const choice = record.response?.choices?.[0] || {};
  const termination = record.termination || (choice.finish_reason === 'length' ? 'token_limit' : 'unconfirmed');
  tags.append(node('span', termination.replaceAll('_', ' '), 'tag ' + (termination === 'delimiter' ? 'good' : 'warn')));
  for (const flag of record.quality_flags || []) tags.append(node('span', flag.replaceAll('_', ' '), 'tag'));
  header.append(node('h2', record.id), tags);
  const usage = record.response?.usage || {};
  const meta = node('div', undefined, 'message-meta');
  for (const [label, value] of [['Seed', request.seed], ['Input tokens', usage.prompt_tokens], ['Output tokens', usage.completion_tokens], ['Finish', choice.finish_reason], ['Stop reason', choice.stop_reason]]) {
    meta.append(node('span', `${label}: ${display(value)}`));
  }
  const detail = node('div', undefined, 'message-details');
  const {prompt, ...settings} = request;
  const {response, body, ...provenance} = record;
  detail.append(disclosure('Exact input prompt', prompt), disclosure('Request settings', json(settings)), disclosure('Message metadata', json(provenance)), disclosure('Provider response', json(response)));
  article.append(header, node('p', record.body || '(Empty output)', 'body'), meta, detail);
  return article;
}
async function selectRun() {
  const token = ++generation;
  const name = $('runs').value;
  $('content').hidden = true;
  $('status').textContent = name ? 'Loading run…' : 'No generation runs found. Generate a batch, then refresh.';
  if (!name) return;
  try {
    const run = await get('/api/run?name=' + encodeURIComponent(name));
    if (token !== generation) return;
    $('run-name').textContent = run.name;
    $('model').textContent = `${run.config.model} · ${run.provider} · schema ${run.config.schema_version}`;
    $('progress').textContent = `${run.completed} / ${run.planned} saved`;
    $('metrics').replaceChildren(metric('Temperature', run.config.temperature), metric('Top p', run.config.top_p), metric('Token ceiling / sample', run.config.max_tokens), metric('Created', run.created_at ? new Date(run.created_at).toLocaleString() : null));
    $('config').textContent = json(run.config);
    $('source').textContent = json(run.sources);
    $('run-errors').textContent = run.errors.join('\n');
    $('messages').replaceChildren(...run.samples.map(message));
    if (!run.samples.length) $('messages').append(node('p', 'No samples saved yet. Refresh once generation has produced a result.', 'hint'));
    $('status').textContent = '';
    $('content').hidden = false;
  } catch (error) { if (token === generation) $('status').textContent = error.message; }
}
async function refresh() {
  const selected = $('runs').value;
  $('refresh').disabled = true;
  try {
    const data = await get('/api/runs');
    $('runs').replaceChildren(...data.runs.map(run => {
      const option = node('option', `${run.name} · ${run.completed}/${run.planned}`);
      option.value = run.name;
      return option;
    }));
    if (data.runs.some(run => run.name === selected)) $('runs').value = selected;
    else if (data.runs.length) $('runs').selectedIndex = 0;
    $('list-errors').textContent = data.errors.join('\n');
    await selectRun();
  } catch (error) { $('status').textContent = error.message; }
  finally { $('refresh').disabled = false; }
}
$('runs').addEventListener('change', selectRun);
$('refresh').addEventListener('click', refresh);
refresh();
