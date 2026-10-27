import assert from 'node:assert/strict';
import test from 'node:test';
import { api } from '../src/api.ts';

function reply(t,body,status=200,type='application/json'){
  const previous=globalThis.fetch;
  globalThis.fetch=async()=>new Response(body,{status,headers:{'content-type':type}});
  t.after(()=>{globalThis.fetch=previous});
}

test('returns successful JSON',async t=>{
  reply(t,'{"status":"ok"}');
  assert.deepEqual(await api('/api/health'),{status:'ok'});
});

test('explains a Vercel plain-text 404 instead of leaking a JSON parser error',async t=>{
  reply(t,'The page could not be found\nNOT_FOUND',404,'text/plain; charset=utf-8');
  await assert.rejects(api('/api/route-analyses'),/HTTP 404 instead of JSON.*Django API/);
});

test('handles an HTML server error',async t=>{
  reply(t,'<!doctype html><title>Internal Server Error</title>',500,'text/html');
  await assert.rejects(api('/api/health'),/HTTP 500 instead of JSON/);
});

test('handles malformed JSON with an actionable error',async t=>{
  reply(t,'{unfinished');
  await assert.rejects(api('/api/health'),/returned invalid JSON/);
});

test('preserves backend error messages',async t=>{
  reply(t,'{"error":"Forecast unavailable"}',502);
  await assert.rejects(api('/api/route-analyses'),/Forecast unavailable/);
});

test('shows nested field validation errors',async t=>{
  reply(t,'{"origin":{"coordinates":["Choose a valid location."]}}',400);
  await assert.rejects(api('/api/route-analyses'),/origin: coordinates: Choose a valid location/);
});
