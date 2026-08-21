const stateText=(online,ok='Online',bad='Offline')=>({text:online?ok:bad,cls:online?'state-online':'state-offline'});
function setState(id,value,ok,bad){const el=document.getElementById(id);const state=stateText(value,ok,bad);el.textContent=state.text;el.className=state.cls;}
function render(data){
  document.getElementById('generated-at').textContent=`Обновлено: ${data.generated_at}`;
  setState('postgresql',data.system.postgresql);setState('n8n',data.system.n8n);setState('mcp',data.system.mcp);setState('collectors',data.system.collectors_ok,'OK','Проблема');
  document.getElementById('last-data').textContent=data.last_data_update;
  document.getElementById('analyst-last').textContent=data.analyst.last;
  document.getElementById('analyst-next').textContent=data.analyst.next;
  document.getElementById('analyst-schedule').textContent=data.analyst.schedule;
  document.getElementById('email-last').textContent=data.email.label;
  const a=data.attention;
  document.getElementById('count-attention').textContent=a.counts.attention;
  document.getElementById('count-watch').textContent=a.counts.watch;
  document.getElementById('count-leave').textContent=a.counts.leave;
  const signals=document.getElementById('signals');signals.textContent='';
  if(!a.available||!a.signals.length){signals.innerHTML='<p class="muted">Текущие сигналы недоступны.</p>';return;}
  a.signals.forEach(item=>{const row=document.createElement('div');row.className='signal';const sku=document.createElement('b');sku.textContent=item.sku;const signal=document.createElement('em');signal.textContent=item.signal;const reason=document.createElement('p');reason.textContent=item.reason;row.append(sku,signal,reason);signals.append(row);});
}
async function refresh(){try{const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw new Error('status');render(await response.json());}catch(_){document.getElementById('generated-at').textContent='Статус временно недоступен';}}
refresh();setInterval(refresh,60000);
