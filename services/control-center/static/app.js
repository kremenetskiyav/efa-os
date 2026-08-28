const stateText=(online,ok='Online',bad='Offline')=>({text:online?ok:bad,cls:online?'state-online':'state-offline'});
function setState(id,value,ok,bad){const el=document.getElementById(id);const state=stateText(value,ok,bad);el.textContent=state.text;el.className=state.cls;}
function setToggle(id,value){const el=document.getElementById(id);if(value===null){el.textContent='Нет данных';el.className='';return;}setState(id,value,'ON','OFF');}
function formatSnapshot(value){if(!value)return 'Нет данных';const parsed=new Date(value);if(Number.isNaN(parsed.getTime()))return String(value);return new Intl.DateTimeFormat('ru-RU',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Moscow'}).format(parsed)+' МСК';}
function renderCompetitor(summary){
  const panel=document.getElementById('competitor-panel');const content=document.getElementById('competitor-content');const badge=document.getElementById('competitor-badge');
  if(!summary||!summary.available){panel.classList.add('degraded');content.hidden=true;document.getElementById('competitor-status').textContent='Данные недоступны';document.getElementById('competitor-snapshot').textContent='Последний снимок: нет данных';document.getElementById('competitor-headline').textContent='Данные мониторинга сейчас недоступны.';badge.textContent='Недоступно';badge.className='badge';return;}
  panel.classList.remove('degraded');content.hidden=false;const labels={IMPORTANT:'Требует внимания',WATCH:'Наблюдать',NORMAL:'Без изменений'};document.getElementById('competitor-status').textContent=labels[summary.status]||summary.status;badge.textContent=summary.status;badge.className=`badge ${summary.status==='NORMAL'?'active':'watch-badge'}`;
  document.getElementById('competitor-snapshot').textContent=`Последний снимок: ${formatSnapshot(summary.snapshot&&summary.snapshot.reference_at)}`;
  const counts=summary.counts||{};const total=counts.total_findings;
  document.getElementById('competitor-headline').textContent=total===0?'Изменений, соответствующих правилам Finding Engine v1, не обнаружено.':((summary.headline&&summary.headline.message)||'Нет событий уровня WATCH или IMPORTANT.');
  const coverage=summary.coverage||{};document.getElementById('competitor-coverage').textContent=`${coverage.active_monitored_sku_count} из ${coverage.portfolio_sku_count} SKU`;
  const own=summary.own||{};document.getElementById('competitor-own').textContent=`${own.own_watch_count} наблюдать · ${own.own_restored_count} восстановлено`;
  const competitors=summary.competitors||{};document.getElementById('competitor-visibility').textContent=`−${competitors.visibility_lost_count} / +${competitors.visibility_restored_count}`;
  const prices=summary.prices||{};document.getElementById('competitor-prices').textContent=`${prices.price_changes_count} изменение`;
  document.getElementById('competitor-important').textContent=counts.important_count;document.getElementById('competitor-watch').textContent=counts.watch_count;document.getElementById('competitor-info').textContent=counts.info_count;
}
function render(data){
  document.getElementById('generated-at').textContent=`Обновлено: ${data.generated_at}`;
  setState('postgresql',data.system.postgresql);setState('n8n',data.system.n8n);setState('mcp',data.system.mcp);setState('collectors',data.system.collectors_ok,'OK','Проблема');
  document.getElementById('last-data').textContent=data.last_data_update;
  document.getElementById('analyst-last').textContent=data.analyst.last;
  document.getElementById('analyst-next').textContent=data.analyst.next;
  document.getElementById('analyst-schedule').textContent=data.analyst.schedule;
  document.getElementById('delivery-next').textContent=data.delivery.next;
  document.getElementById('delivery-schedule').textContent=data.delivery.schedule;
  document.getElementById('delivery-last').textContent=data.delivery.last.label;
  setToggle('delivery-email',data.delivery.email_on);
  setToggle('delivery-telegram',data.delivery.telegram_on);
  setToggle('old-brief',data.delivery.old_brief_on);
  const a=data.attention;
  document.getElementById('count-attention').textContent=a.counts.attention;
  document.getElementById('count-watch').textContent=a.counts.watch;
  document.getElementById('count-leave').textContent=a.counts.leave;
  const signals=document.getElementById('signals');signals.textContent='';
  if(!a.available||!a.signals.length){signals.innerHTML='<p class="muted">Текущие сигналы недоступны.</p>';}else{a.signals.forEach(item=>{const row=document.createElement('div');row.className='signal';const sku=document.createElement('b');sku.textContent=item.sku;const signal=document.createElement('em');signal.textContent=item.signal;const reason=document.createElement('p');reason.textContent=item.reason;row.append(sku,signal,reason);signals.append(row);});}
  renderCompetitor(data.competitor_monitor);
}
async function refresh(){try{const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw new Error('status');render(await response.json());}catch(_){document.getElementById('generated-at').textContent='Статус временно недоступен';}}
refresh();setInterval(refresh,60000);
