export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

export function filterParams(entries) {
  const params = new URLSearchParams();
  for (const [key, raw] of entries) {
    const value = String(raw).trim();
    if (!value) continue;
    if (key === 'date_from' || key === 'date_to') {
      const date = new Date(`${value}T00:00:00`);
      if (Number.isNaN(date.getTime())) throw new Error('请输入有效日期');
      if (key === 'date_to') date.setDate(date.getDate() + 1);
      params.set(key, date.toISOString());
    } else params.set(key, key === 'currency' ? value.toUpperCase() : value);
  }
  if (params.has('date_from') && params.has('date_to') && params.get('date_from') >= params.get('date_to')) {
    throw new Error('结束日期不能早于开始日期');
  }
  return params;
}

export function errorMessage(body, status) {
  let text = body?.message || `请求失败（HTTP ${status}）`;
  if (body?.code === 'DATABASE_NOT_INITIALIZED') text = '数据库尚未初始化，请在服务器运行 python -m alembic upgrade head。';
  if (body?.code === 'TEMPLATE_NOT_FOUND') text = '未找到 PostPony 原模板。请将模板放到服务器 templates/postpony.xlsx；普通 Excel 导出不需要模板。';
  const details = Array.isArray(body?.details) ? body.details : [];
  if (details.length) text += '\n' + details.slice(0, 15).map(item =>
    `${item.order_id != null ? `订单 ID ${item.order_id} · ` : ''}${item.field || ''}：${item.reason || item.message || '校验失败'}`).join('\n');
  if (details.length > 15) text += `\n另有 ${details.length - 15} 项错误，请缩小选择范围后检查。`;
  return text;
}

export function parseBatch(value) {
  const values = value.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  if (!values.length) throw new Error('请至少输入一个订单号或物流单号');
  if (values.length > 500) throw new Error('每次最多匹配 500 个编号');
  if (values.some(s => s.length > 256)) throw new Error('单个编号不能超过 256 个字符');
  return values;
}

export function toggleSelection(selection, id, checked) {
  if (checked && !selection.has(id) && selection.size >= 500) throw new Error('最多选择 500 个订单；导出全部数据请使用“全部导出”。');
  if (checked) selection.add(id); else selection.delete(id);
}
