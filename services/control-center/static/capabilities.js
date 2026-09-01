'use strict';

const STATUS_ORDER = ['READY', 'CONTROLLED', 'PARTIAL', 'NOT READY'];
const STATUS_LABELS = {
  'ALL': 'Все',
  'READY': 'Ready',
  'CONTROLLED': 'Controlled',
  'PARTIAL': 'Partial',
  'NOT READY': 'Not ready',
};

let catalog = null;
let selectedStatus = 'ALL';
let searchTerm = '';

function node(tag, className, text) {
  const value = document.createElement(tag);
  if (className) value.className = className;
  if (text !== undefined) value.textContent = text;
  return value;
}

function statusClass(status) {
  return status.toLowerCase().replaceAll(' ', '-');
}

function statusBadge(status) {
  return node('span', `catalog-badge ${statusClass(status)}`, status);
}

function renderSummary(summary) {
  const container = document.getElementById('maturity-summary');
  container.replaceChildren();
  STATUS_ORDER.forEach((status) => {
    const item = node('div', `maturity-item ${statusClass(status)}`);
    item.append(node('b', '', String(summary[status])), node('span', '', STATUS_LABELS[status]));
    container.append(item);
  });
}

function renderSafety(safety) {
  document.getElementById('safety-title').textContent = safety.title;
  document.getElementById('safety-message').textContent = safety.message;
  document.getElementById('safety-details').textContent = safety.details;
  document.getElementById('safety-fallback').textContent = safety.fallback;
  document.getElementById('write-policy').textContent = safety.write_policy;
  document.getElementById('write-policy-details').textContent = safety.write_policy_details;
}

function renderFilters(summary) {
  const container = document.getElementById('status-filters');
  container.replaceChildren();
  ['ALL', ...STATUS_ORDER].forEach((status) => {
    const count = status === 'ALL'
      ? Object.values(summary).reduce((total, value) => total + value, 0)
      : summary[status];
    const button = node('button', status === selectedStatus ? 'active' : '', `${STATUS_LABELS[status]} · ${count}`);
    button.type = 'button';
    button.dataset.status = status;
    button.setAttribute('aria-pressed', String(status === selectedStatus));
    button.addEventListener('click', () => {
      selectedStatus = status;
      renderFilters(catalog.summary);
      renderCapabilities();
    });
    container.append(button);
  });
}

function detail(label, value) {
  const item = node('div', 'capability-detail');
  item.append(node('dt', '', label), node('dd', '', value));
  return item;
}

function copyButton(command) {
  const button = node('button', 'copy-command', 'Копировать');
  button.type = 'button';
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(command);
      button.textContent = 'Скопировано';
      window.setTimeout(() => { button.textContent = 'Копировать'; }, 1400);
    } catch (_) {
      button.textContent = 'Выделите текст';
    }
  });
  return button;
}

function capabilityCard(item) {
  const article = node('article', `capability-card status-${statusClass(item.status)}`);
  const head = node('div', 'capability-card-head');
  const title = node('h3', '', item.name);
  head.append(title, statusBadge(item.status));

  const description = node('p', 'capability-does', item.does);
  const command = node('div', 'capability-command');
  command.append(node('code', '', item.example_command), copyButton(item.example_command));

  const details = node('dl', 'capability-details');
  details.append(
    detail('Trigger', item.trigger),
    detail('Read / write scope', item.read_write_scope),
    detail('Ограничения', item.limitations),
  );
  article.append(head, description, command, details);
  return article;
}

function renderCapabilities() {
  const container = document.getElementById('capability-list');
  const normalized = searchTerm.trim().toLocaleLowerCase('ru');
  const matches = catalog.capabilities.filter((item) => {
    const statusMatches = selectedStatus === 'ALL' || item.status === selectedStatus;
    const haystack = Object.values(item).join(' ').toLocaleLowerCase('ru');
    return statusMatches && (!normalized || haystack.includes(normalized));
  });

  container.replaceChildren(...matches.map(capabilityCard));
  if (!matches.length) container.append(node('p', 'catalog-empty', 'По этому фильтру ничего не найдено.'));
  document.getElementById('catalog-result').textContent = `Показано: ${matches.length} из ${catalog.capabilities.length}`;
}

function ownerCommand(item, index) {
  const article = node('article', 'owner-command');
  const head = node('div', 'owner-command-head');
  head.append(node('span', 'command-number', String(index + 1).padStart(2, '0')), node('h3', '', item.title), statusBadge(item.status));
  const body = node('div', 'owner-command-body');
  body.append(node('code', '', item.command), copyButton(item.command));
  article.append(head, body);
  return article;
}

function renderCommands(commands) {
  document.getElementById('owner-commands').replaceChildren(...commands.map(ownerCommand));
}

async function loadCatalog() {
  try {
    const response = await fetch('/static/capabilities.json', {cache: 'no-store'});
    if (!response.ok) throw new Error('catalog unavailable');
    catalog = await response.json();
    document.getElementById('audit-meta').textContent = `Inventory snapshot: ${catalog.inventory_snapshot} · ${catalog.snapshot_type} · ${catalog.runtime_note}`;
    renderSummary(catalog.summary);
    renderSafety(catalog.safety);
    renderFilters(catalog.summary);
    renderCapabilities();
    renderCommands(catalog.daily_commands);
  } catch (_) {
    document.getElementById('audit-meta').textContent = 'Каталог временно недоступен';
    document.getElementById('capability-list').replaceChildren(node('p', 'catalog-empty', 'Не удалось загрузить статический каталог.'));
  }
}

document.getElementById('catalog-search').addEventListener('input', (event) => {
  searchTerm = event.target.value;
  renderCapabilities();
});

loadCatalog();
