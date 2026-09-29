import test from 'node:test';
import assert from 'node:assert/strict';
import {escapeHTML, filterParams, errorMessage, parseBatch, toggleSelection} from '../app/static/utils.mjs';

test('外部订单文本不能注入 HTML', () => {
  assert.equal(escapeHTML('<img src=x onerror="alert(1)"> & \'x\''), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &#39;x&#39;');
  assert.equal(escapeHTML(null), '');
});

test('筛选保留前导零，清理空白及空参数', () => {
  const params = filterParams([['order_number',' 0001001 '],['tracking_number','000012345678901234567890'],['shop_id',''],['currency','usd']]);
  assert.equal(params.get('order_number'),'0001001');
  assert.equal(params.get('tracking_number'),'000012345678901234567890');
  assert.equal(params.has('shop_id'),false);
  assert.equal(params.get('currency'),'USD');
});

test('日期筛选按浏览器本地日期包含结束当天，并转为带时区时间', () => {
  const params = filterParams([['date_from','2026-01-01'],['date_to','2026-01-01']]);
  assert.equal(params.get('date_from'),new Date('2026-01-01T00:00:00').toISOString());
  assert.equal(params.get('date_to'),new Date('2026-01-02T00:00:00').toISOString());
  assert.throws(()=>filterParams([['date_from','2026-02-01'],['date_to','2026-01-01']]),/结束日期/);
});

test('批量匹配保留原编号，限制 500 行及单号长度', () => {
  assert.deepEqual(parseBatch(' 0001001\r\n\n SHARED-TRACKING \n0001001'),['0001001','SHARED-TRACKING','0001001']);
  assert.throws(()=>parseBatch('  \n'),/至少/);
  assert.throws(()=>parseBatch('1\n'.repeat(501)),/500/);
  assert.throws(()=>parseBatch('1'.repeat(257)),/256/);
});

test('跨页选择去重，不能超限，满额仍可取消与保留已选', () => {
  const ids = new Set(Array.from({length:500},(_,i)=>i+1));
  toggleSelection(ids,1,true);
  assert.equal(ids.size,500);
  assert.throws(()=>toggleSelection(ids,501,true),/500/);
  assert.equal(ids.has(501),false);
  toggleSelection(ids,1,false);toggleSelection(ids,501,true);
  assert.equal(ids.size,500); assert.equal(ids.has(1),false);
});

test('错误信息解释缺模板并定位订单，限制超长错误列表', () => {
  assert.match(errorMessage({code:'TEMPLATE_NOT_FOUND'},422),/普通 Excel 导出不需要模板/);
  assert.match(errorMessage({code:'DATABASE_NOT_INITIALIZED'},503),/alembic upgrade head/);
  const message=errorMessage({message:'校验失败',details:Array.from({length:18},(_,i)=>({order_id:i+1,field:'weight',reason:'缺失'}))},422);
  assert.match(message,/订单 ID 1 · weight：缺失/);
  assert.match(message,/另有 3 项错误/);
  assert.equal(errorMessage({},500),'请求失败（HTTP 500）');
});
