import {escapeHTML as e, filterParams, errorMessage, parseBatch, toggleSelection} from './utils.mjs';

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const state = {view:'orders', shops:[], selected:new Set(), orders:[], page:1, size:20, filters:new URLSearchParams(), financePage:1, financeFilters:new URLSearchParams(), syncPage:1, postponyIds:[]};
const sequences = {orders:0, finance:0, sync:0, detail:0, preview:0};
const labels = {shipped:'已发货', paid:'已付款', unshipped:'未发货', refunded:'已退款', cancelled:'已取消', payment:'收款', refund:'退款', fee:'费用', adjustment:'调整', payout:'提现', success:'成功', completed:'完成', failed:'失败', running:'进行中'};
const shopName = id => state.shops.find(shop => shop.id === id)?.name || `店铺 ${id}`;
const time = value => value ? new Date(value).toLocaleString('zh-CN', {hour12:false}) : '—';
const amount = (value, currency) => `${e(currency || '')} ${e(value ?? '—')}`;
const badge = status => `<span class="badge ${['shipped','success','completed','payment'].includes(status) ? 'green' : ['failed','cancelled','refund','refunded'].includes(status) ? 'red' : 'amber'}">${e(labels[status] || status || '未知')}</span>`;
const empty = (columns, text) => `<tr><td colspan="${columns}" class="empty">${e(text)}</td></tr>`;
function notify(text, error=false) { const box = $('#message'); box.textContent = text; box.className = `message${error ? ' error' : ''}`; box.hidden = false; }
function hideMessage() { $('#message').hidden = true; }
function dialogMessage(dialog, text, error=false) {
  let box=dialog.querySelector('[data-dialog-message]');
  if(!box){box=document.createElement('div');box.dataset.dialogMessage='1';box.setAttribute('role','status');dialog.querySelector('.dialog-heading').after(box);}
  box.className=error?'error-box':'success-box';box.textContent=text;
}

async function request(path, options={}) {
  let response;
  try { response = await fetch(`/api/v1${path}`, {cache:'no-store', ...options}); }
  catch { throw new Error('无法连接服务，请检查网络及后端是否仍在运行，然后重试。'); }
  if (!response.ok) {
    let body;
    try { body = await response.json(); } catch { body = {}; }
    throw new Error(errorMessage(body, response.status));
  }
  return response;
}
const json = async (path, options) => (await request(path, options)).json();
const post = body => ({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});

async function busy(button, task, onError = error => notify(error.message, true)) {
  if (button.dataset.busy) return;
  button.dataset.busy = '1';
  const original = button.innerHTML;
  button.disabled = true; button.textContent = '处理中…';
  try { await task(); } catch (error) { onError(error); }
  finally { delete button.dataset.busy; button.innerHTML = original; button.disabled = false; updateSelection(); }
}
async function download(path, options, filename) {
  const response = await request(path, options);
  if (!response.headers.get('Content-Type')?.includes('spreadsheetml.sheet')) throw new Error('服务器未返回 Excel 文件，请确认已上传最新后端代码。');
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = filename;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  notify(`已生成 ${filename}，请查看浏览器下载记录。`);
  const openDialogs=$$('dialog[open]');
  if(openDialogs.length)dialogMessage(openDialogs.at(-1),`已生成 ${filename}，请查看浏览器下载记录。`);
}

function updateSelection() {
  $('#selection-count').textContent = state.selected.size;
  $('#selected-label').textContent = state.selected.size;
  for (const id of ['clear-selection','export-selected','postpony-open']) {
    const button = $(`#${id}`); button.disabled = !state.selected.size || Boolean(button.dataset.busy);
  }
  const pageIds = state.orders.map(order => order.id);
  const selectedCount = pageIds.filter(id => state.selected.has(id)).length;
  $('#select-page').checked = pageIds.length > 0 && selectedCount === pageIds.length;
  $('#select-page').indeterminate = selectedCount > 0 && selectedCount < pageIds.length;
  $('#select-page').disabled = pageIds.length === 0;
  $$('[data-select-id]').forEach(input => { input.checked = state.selected.has(Number(input.dataset.selectId)); });
}
function pager(kind, page, size, total) {
  const pages = Math.max(1, Math.ceil(total / size));
  $(`#${kind}-page-info`).textContent = total ? `共 ${total} 条 · 当前 ${(page-1)*size+1}–${Math.min(page*size,total)} 条` : '共 0 条';
  $(`#${kind}-page-label`).textContent = `${page} / ${pages}`;
  $(`#${kind}-prev`).disabled = page <= 1;
  $(`#${kind}-next`).disabled = page >= pages;
}
function loading(kind, columns) {
  $(`#${kind}-rows`).innerHTML = empty(columns,'正在加载…');
  $(`#${kind}-prev`).disabled = true; $(`#${kind}-next`).disabled = true;
}

async function loadOrders() {
  const sequence = ++sequences.orders;
  loading('order',7); state.orders = []; updateSelection();
  const params = new URLSearchParams(state.filters); params.set('page',state.page); params.set('page_size',state.size);
  try {
    const result = await json(`/orders?${params}`);
    if (sequence !== sequences.orders) return;
    state.orders = result.items;
    $('#order-count').textContent = result.total; $('#list-total').textContent = result.total;
    $('#order-rows').innerHTML = result.items.length ? result.items.map(order => `<tr>
      <td class="check-col"><input type="checkbox" data-select-id="${order.id}" aria-label="选择订单 ${e(order.platform_order_id)}"></td>
      <td><button class="text-button order-number" data-detail-id="${order.id}">${e(order.platform_order_id)}</button><small>${e(shopName(order.shop_id))} · ID ${order.id}</small></td>
      <td>${e(order.receiver_name || '未填写')}<small>${e([order.receiver_country,order.receiver_state].filter(Boolean).join(' / '))}</small></td>
      <td>${badge(order.status)}</td><td class="money">${amount(order.total_amount,order.currency)}</td><td>${e(time(order.ordered_at))}</td>
      <td><button class="text-button" data-detail-id="${order.id}">查看详情 →</button></td></tr>`).join('') : empty(7, '没有匹配的订单。可重置筛选，或点击“同步模拟数据”初始化演示数据。');
    pager('order',state.page,state.size,result.total); updateSelection();
  } catch (error) {
    if (sequence !== sequences.orders) return;
    $('#order-rows').innerHTML = empty(7,error.message); $('#order-count').textContent = '—'; $('#list-total').textContent = '—';
    $('#order-page-info').textContent = '加载失败，请重新查询';
  }
}

async function loadFinance() {
  const sequence = ++sequences.finance; loading('finance',6);
  const params = new URLSearchParams(state.financeFilters); params.set('page',state.financePage); params.set('page_size',20);
  try {
    const result = await json(`/financial-transactions?${params}`);
    if (sequence !== sequences.finance) return;
    $('#finance-rows').innerHTML = result.items.length ? result.items.map(tx => `<tr><td>${e(tx.source_transaction_id)}<small>ID ${tx.id}</small></td><td>${e(shopName(tx.shop_id))}<small>${tx.order_id ? `<button class="text-button" data-detail-id="${tx.order_id}">订单 ID ${tx.order_id}</button>` : '店铺级流水 · 未关联订单'}</small></td><td>${badge(tx.type)}</td><td class="money ${String(tx.amount).startsWith('-') ? 'negative' : ''}">${amount(tx.amount,tx.currency)}</td><td>${e(time(tx.occurred_at))}</td><td>${e(tx.description)}</td></tr>`).join('') : empty(6,'没有匹配的财务流水');
    pager('finance',state.financePage,20,result.total);
  } catch (error) { if (sequence === sequences.finance) { $('#finance-rows').innerHTML = empty(6,error.message); $('#finance-page-info').textContent = '加载失败，请重新查询'; } }
}
async function loadSync() {
  const sequence = ++sequences.sync; loading('sync',8);
  try {
    const result = await json(`/sync-runs?page=${state.syncPage}&page_size=20`);
    if (sequence !== sequences.sync) return;
    $('#sync-rows').innerHTML = result.items.length ? result.items.map(run => `<tr><td>#${run.id}</td><td>${badge(run.status)}</td><td>${e(time(run.started_at))}</td><td>${run.added}</td><td>${run.updated}</td><td>${run.unchanged}</td><td>${run.failed}</td><td>${e(run.error_summary || '—')}</td></tr>`).join('') : empty(8,'尚无同步记录，点击“同步模拟数据”开始。');
    pager('sync',state.syncPage,20,result.total);
  } catch (error) { if (sequence === sequences.sync) { $('#sync-rows').innerHTML = empty(8,error.message); $('#sync-page-info').textContent = '加载失败，请刷新记录'; } }
}

function table(headers, rows) {
  return `<div class="table-wrap"><table><thead><tr>${headers.map(header=>`<th>${e(header)}</th>`).join('')}</tr></thead><tbody>${rows.length ? rows.map(row=>`<tr>${row.map(cell=>`<td>${cell}</td>`).join('')}</tr>`).join('') : empty(headers.length,'暂无记录')}</tbody></table></div>`;
}
const info = (label,value,cls='') => `<div class="${cls}"><span>${e(label)}</span><strong>${e(value ?? '—')}</strong></div>`;
async function showDetail(id) {
  const sequence = ++sequences.detail;
  $('#detail-title').textContent = '订单详情'; $('#detail-content').innerHTML = '<div class="empty">正在加载订单详情…</div>';
  if (!$('#detail-dialog').open) $('#detail-dialog').showModal();
  try {
    const order = await json(`/orders/${id}`);
    if (sequence !== sequences.detail) return;
    $('#detail-title').textContent = `订单 ${order.platform_order_id}`;
    $('#detail-content').innerHTML = `<div class="detail-grid">${info('店铺 / 数据库 ID',`${shopName(order.shop_id)} / ${order.id}`)}${info('状态',labels[order.status] || order.status)}${info('订单总额',`${order.currency} ${order.total_amount}`)}${info('下单时间',time(order.ordered_at))}${info('收件人 / 电话',`${order.receiver_name || '未填写'} / ${order.receiver_phone || '未填写'}`)}${info('邮编',order.receiver_zip)}${info('收件地址',[order.receiver_country,order.receiver_state,order.receiver_city,order.receiver_address1,order.receiver_address2].filter(Boolean).join(' · '),'detail-address')}${info('内部备注',order.internal_notes,'detail-address')}</div>
    <section class="detail-section"><h3>商品明细 · ${order.items.length} 项</h3>${table(['商品 / SKU','数量','单价','单位重量','原产国'],order.items.map(item=>[`${e(item.title)}<small>${e(item.sku)} · ID ${item.id}</small>`,e(item.quantity),amount(item.unit_price,order.currency),e(item.unit_weight ?? '—'),e(item.country_of_origin || '—')]))}</section>
    <section class="detail-section"><h3>包裹与物流 · ${order.shipments.length} 个</h3>${order.shipments.length ? order.shipments.map(shipment=>`<h3>${e(shipment.package_reference)}</h3><p>${e(shipment.carrier || '未填承运商')} · 物流单号：${e(shipment.tracking_number || '未填写')} · 发货日期：${e(shipment.shipping_date || '未发货')}</p><p>重量：${e(shipment.weight ?? '—')} · 尺寸：${e(shipment.length ?? '—')} × ${e(shipment.width ?? '—')} × ${e(shipment.height ?? '—')} · 单位：${e(shipment.measurement_unit || '未填写')}</p>${table(['装箱商品','SKU','装箱数量'],shipment.allocations.map(allocation=>{const item=order.items.find(item=>item.id===allocation.order_item_id);return [e(item?.title || `商品 ID ${allocation.order_item_id}`),e(item?.sku || '—'),e(allocation.quantity)];}))}`).join('') : '<p class="muted">暂无包裹</p>'}</section>
    <section class="detail-section"><h3>订单财务摘要</h3><p class="muted">按币种分别统计；净收款不含提现，也不代表利润。</p>${Object.entries(order.financial_summary).map(([currency,summary])=>`<h3>${e(currency)}</h3><div class="summary-grid">${[['payment','收款'],['refund','退款'],['fee','费用'],['adjustment','调整'],['net_receipts','净收款']].map(([key,label])=>`<div><span class="muted">${label}</span><strong>${e(summary[key])}</strong></div>`).join('')}</div>`).join('') || '<p class="muted">暂无关联财务数据</p>'}<h3>关联流水</h3>${table(['类型','金额','时间','说明'],order.financial_transactions.map(tx=>[badge(tx.type),amount(tx.amount,tx.currency),e(time(tx.occurred_at)),e(tx.description)]))}</section>
    <div class="dialog-actions"><button class="button primary" data-export-id="${order.id}">下载此订单 Excel</button></div>`;
  } catch (error) { if (sequence === sequences.detail) $('#detail-content').innerHTML = `<div class="error-box">${e(error.message)}</div>`; }
}

async function previewPostpony() {
  const sequence = ++sequences.preview;
  $('#postpony-download').disabled = true;
  $('#postpony-result').innerHTML = '<p class="muted">正在校验所选订单与模板…</p>';
  try {
    const result = await json('/exports/postpony/preview',post({order_ids:state.postponyIds}));
    if (sequence !== sequences.preview) return;
    $('#postpony-result').innerHTML = `<div class="success-box">${result.selected_orders} 个订单通过预览，预计导出 ${result.estimated_rows} 行。</div>${result.warnings.length ? `<h3>注意事项</h3><ul class="issue-list">${result.warnings.map(item=>`<li>订单 ID ${e(item.order_id)} · ${e(item.reason)}</li>`).join('')}</ul>` : ''}`;
    $('#postpony-download').disabled = !result.valid;
  } catch (error) { if (sequence === sequences.preview) $('#postpony-result').innerHTML = `<div class="error-box">${e(error.message)}</div>`; }
}

async function loadShops() {
  state.shops = await json('/shops'); $('#shop-count').textContent = state.shops.length;
  $$('.shop-select').forEach(select => { const value=select.value; select.innerHTML = '<option value="">全部店铺</option>' + state.shops.map(shop=>`<option value="${shop.id}">${e(shop.name)}</option>`).join(''); select.value=value; });
}
async function health() {
  try { await json('/health'); $('#health').textContent='数据库已连接'; $('#health').className='connection ok'; }
  catch (error) { $('#health').textContent='服务或数据库异常'; $('#health').className='connection error'; notify(error.message,true); }
}

$$('[data-view]').forEach(button=>button.addEventListener('click',()=>{
  state.view=button.dataset.view;
  const titles={orders:['订单管理','从查询到导出，让每一笔订单清晰有序。'],finance:['财务流水','按店铺与订单追溯每一笔收支。'],sync:['同步记录','查看数据导入的结果与历史。']};
  $('#page-title').textContent=titles[state.view][0]; $('#breadcrumb').textContent=titles[state.view][0]; $('#page-description').textContent=titles[state.view][1];
  $$('.view').forEach(view=>{view.hidden=view.id!==`${state.view}-view`;});
  $$('[data-view]').forEach(item=>{item.classList.toggle('active',item===button);item.setAttribute('aria-current',item===button?'page':'false');});
  ({orders:loadOrders,finance:loadFinance,sync:loadSync})[state.view]();
}));
$('#order-filter').addEventListener('submit',event=>{event.preventDefault();try{state.filters=filterParams(new FormData(event.target));state.page=1;hideMessage();loadOrders();}catch(error){notify(error.message,true);}});
$('#order-filter').addEventListener('reset',()=>{state.filters=new URLSearchParams();state.page=1;loadOrders();});
$('#finance-filter').addEventListener('submit',event=>{event.preventDefault();try{state.financeFilters=filterParams(new FormData(event.target));state.financePage=1;loadFinance();}catch(error){notify(error.message,true);}});
$('#finance-filter').addEventListener('reset',()=>{state.financeFilters=new URLSearchParams();state.financePage=1;loadFinance();});
$('#page-size').addEventListener('change',event=>{state.size=Number(event.target.value);state.page=1;loadOrders();});
for (const [kind,key,load] of [['order','page',loadOrders],['finance','financePage',loadFinance],['sync','syncPage',loadSync]]) {
  $(`#${kind}-prev`).addEventListener('click',()=>{state[key]=Math.max(1,state[key]-1);load();});
  $(`#${kind}-next`).addEventListener('click',()=>{state[key]++;load();});
}
$('#sync-refresh').addEventListener('click',loadSync);
document.addEventListener('change',event=>{
  const input=event.target.closest('[data-select-id]');if(!input)return;
  try{toggleSelection(state.selected,Number(input.dataset.selectId),input.checked);}catch(error){notify(error.message,true);if($('#batch-dialog').open)dialogMessage($('#batch-dialog'),error.message,true);}
  updateSelection();
});
$('#select-page').addEventListener('change',event=>{
  const ids=state.orders.map(order=>order.id);
  if(event.target.checked && new Set([...state.selected,...ids]).size>500){notify('最多选择 500 单，请先导出已选订单或使用全部导出。',true);updateSelection();return;}
  ids.forEach(id=>toggleSelection(state.selected,id,event.target.checked));updateSelection();
});
$('#clear-selection').addEventListener('click',()=>{state.selected.clear();updateSelection();});
document.addEventListener('click',event=>{
  const detail=event.target.closest('[data-detail-id]');if(detail)showDetail(Number(detail.dataset.detailId));
  const close=event.target.closest('[data-close]');if(close)$(`#${close.dataset.close}`).close();
  const single=event.target.closest('[data-export-id]');if(single)busy(single,()=>download('/exports/orders',post({order_ids:[Number(single.dataset.exportId)]}),'order.xlsx'),error=>{const box=document.createElement('p');box.className='error-box';box.textContent=error.message;single.closest('.dialog-actions').before(box);});
});
$('#export-all').addEventListener('click',event=>busy(event.currentTarget,()=>download('/exports/orders',{},'all-orders.xlsx')));
$('#export-selected').addEventListener('click',event=>{const ids=[...state.selected];busy(event.currentTarget,()=>download('/exports/orders',post({order_ids:ids}),'selected-orders.xlsx'));});
$('#sync-button').addEventListener('click',event=>busy(event.currentTarget,async()=>{
  const result=await json('/sync/mock',post({}));
  notify(`模拟数据同步完成：新增 ${result.added} 单，更新 ${result.updated} 单，未变化 ${result.unchanged} 单。`);
  await loadShops(); state.page=1;state.financePage=1;state.syncPage=1;
  await Promise.all([health(),loadOrders(),...(state.view==='finance'?[loadFinance()]:[]),...(state.view==='sync'?[loadSync()]:[])]);
}));
$('#batch-open').addEventListener('click',()=>$('#batch-dialog').showModal());
$('#batch-form').addEventListener('submit',event=>{
  event.preventDefault(); const form=event.target;
  busy(form.querySelector('button[type=submit]'),async()=>{
    $('#batch-result').textContent='正在匹配…';
    const data=new FormData(form); const body={lookup_type:data.get('lookup_type'),values:parseBatch(data.get('values'))};
    if(data.get('shop_id'))body.shop_id=Number(data.get('shop_id'));
    const result=await json('/orders/batch-lookup',post(body));
    $('#batch-result').innerHTML=result.map(match=>`<div class="match-result"><strong>${e(match.input_value)}</strong> <span class="badge ${match.status==='matched'?'green':'amber'}">${{matched:'匹配成功',not_found:'未找到',ambiguous:'多个匹配，请确认'}[match.status]}</span>${match.orders.map(order=>`<div class="match-order"><label><input type="checkbox" data-select-id="${order.id}">${e(order.platform_order_id)} · ${e(shopName(order.shop_id))} · ID ${order.id}</label><button class="text-button" data-detail-id="${order.id}">详情</button></div>`).join('')}</div>`).join('');updateSelection();
  },error=>{$('#batch-result').innerHTML=`<div class="error-box">${e(error.message)}</div>`;});
});
$('#postpony-open').addEventListener('click',()=>{state.postponyIds=[...state.selected];$('#postpony-dialog').showModal();previewPostpony();});
$('#postpony-check').addEventListener('click',event=>busy(event.currentTarget,previewPostpony));
$('#postpony-download').addEventListener('click',event=>busy(event.currentTarget,()=>download('/exports/postpony',post({order_ids:state.postponyIds}),'postpony-orders.xlsx'),error=>{$('#postpony-result').innerHTML=`<div class="error-box">${e(error.message)}</div>`;}));

async function start(){
  await health();
  try {await loadShops();}catch(error){notify(error.message,true);}
  await loadOrders();
}
start();
