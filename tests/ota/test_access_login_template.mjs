import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const html = await readFile(new URL('../../app/bluetooth_flutter_Trace/cloudflare/update-service/admin/access-login.html', import.meta.url), 'utf8');

test('the official Access authentication control renders once, outside Liquid conditions', () => {
  assert.equal((html.match(/<cf-access-authbox>/g) ?? []).length, 1);
  assert.equal((html.match(/<\/cf-access-authbox>/g) ?? []).length, 1);
  let depth = 0;
  for (const token of html.matchAll(/{%\s*(if|endif|for|endfor)\b[^%]*%}|<cf-access-authbox>/g)) {
    if (['if', 'for'].includes(token[1])) depth++;
    else if (['endif', 'endfor'].includes(token[1])) depth--;
    else assert.equal(depth, 0);
    assert.ok(depth >= 0);
  }
  assert.equal(depth, 0);
});

test('the template cannot replace authentication with customer scripts or forms', () => {
  assert.doesNotMatch(html, /<script\b|<form\b|\bon\w+\s*=|javascript:|<input\b|<button\b/i);
  assert.doesNotMatch(html, /{%\s*(?:include|render|layout|echo|raw|for)\b|\|\s*raw\b/);
  assert.doesNotMatch(html, /cf-access-authbox[^}]*display:\s*none|\bhidden\b|type=["']password/i);
});

test('provider messages remain visible and escaped through the standard Liquid contract', () => {
  assert.match(html, /{% if message\.text\.size > 0 %}/);
  assert.match(html, /<p class="message" role="status">{{ message\.text }}<\/p>/);
  assert.match(html, /<h1>{{ app_name }}<\/h1>/);
});

test('the actual browser icons use the already public assets, not the protected Admin origin', () => {
  assert.match(html, /<title>E-Track<\/title>/);
  assert.match(html, /rel="icon"[^>]+image\/x-icon[^>]+https:\/\/trace-update-public-staging\.pages\.dev\/favicon\.ico\?v=/);
  assert.match(html, /rel="icon"[^>]+image\/png[^>]+https:\/\/trace-update-public-staging\.pages\.dev\/favicon\.png\?v=/);
  assert.doesNotMatch(html, /(?:src|href)="https:\/\/trace-update-admin-staging/);
});

test('the existing Admin palette, viewport and reduced-motion behavior are retained', () => {
  for (const value of ['#faf9f6', '#282d29', '#666d65', '#3c5b49', '#e0e3da']) assert.ok(html.includes(value));
  assert.match(html, /name="viewport" content="width=device-width, initial-scale=1"/);
  assert.match(html, /prefers-reduced-motion:\s*reduce/);
  assert.match(html, /width:\s*min\(440px, calc\(100% - 40px\)\)/);
});

test('normal Cloudflare CI includes the template contract and its test-only changes', async () => {
  const workflow = await readFile(new URL('../../.github/workflows/cloudflare-update-service.yml', import.meta.url), 'utf8');
  assert.equal((workflow.match(/- "tests\/ota\/test_access_login_template\.mjs"/g) ?? []).length, 2);
  assert.ok(workflow.includes('node --test tests/ota/test_update_public_proxy.mjs tests/ota/test_access_login_template.mjs'));
});
