import assert from 'node:assert/strict';
import test from 'node:test';
import { api } from '../.test-build/api.js';
import { uploadDocuments } from '../.test-build/uploads.js';

const documents = () => [new File(['first'], 'First.docx'), new File(['second'], 'Second.pdf')];
const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

test('a partial upload refreshes Materials and reports the completed count before retrying', async context => {
  const originalFetch = globalThis.fetch;
  context.after(() => { globalThis.fetch = originalFetch; });
  const calls = [];
  let materialNames = [];
  globalThis.fetch = async (url, init) => {
    calls.push(url);
    if (url === '/api/uploads') {
      assert.equal(init.method, 'POST');
      assert.equal(init.body.get('category'), 'Projects');
      assert.deepEqual(init.body.getAll('files').map(file => file.name), ['First.docx', 'Second.pdf']);
      return response({ detail: 'Second.pdf could not be uploaded.', partial: true, files: [{ name: 'First.docx' }] }, 400);
    }
    assert.equal(url, '/api/status');
    return response({ files: [{ name: 'First.docx' }] });
  };
  await assert.rejects(uploadDocuments('Projects', documents(), async () => { materialNames = (await api('/status')).files.map(file => file.name); }), /1 of 2 documents uploaded to Box.*retry only the remaining files/);
  assert.deepEqual(calls, ['/api/uploads', '/api/status']);
  assert.deepEqual(materialNames, ['First.docx']);
});

test('an uncertain upload result still refreshes Materials before allowing another attempt', async context => {
  const originalFetch = globalThis.fetch;
  context.after(() => { globalThis.fetch = originalFetch; });
  const calls = [];
  globalThis.fetch = async url => {
    calls.push(url);
    if (url === '/api/uploads') throw new TypeError('Connection reset after sending the file');
    return response({ files: [{ name: 'First.docx' }] });
  };
  await assert.rejects(uploadDocuments('Projects', documents(), async () => { await api('/status'); }), /Cannot reach the local service.*Check Materials before retrying/);
  assert.deepEqual(calls, ['/api/uploads', '/api/status']);
});

test('successful upload followed by refresh failure does not invite duplicate uploads', async context => {
  const originalFetch = globalThis.fetch;
  context.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => response({ files: [{ name: 'First.docx' }, { name: 'Second.pdf' }] });
  await assert.rejects(uploadDocuments('Projects', documents(), async () => { throw new Error('Box list unavailable'); }), /documents were uploaded to Box.*Check Box before retrying/);
});

test('partial upload with failed refresh retains the partial outcome in the error', async context => {
  const originalFetch = globalThis.fetch;
  context.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => response({ detail: 'Upload stopped.', partial: true, files: [{ name: 'First.docx' }] }, 400);
  await assert.rejects(uploadDocuments('Projects', documents(), async () => { throw new Error('Box list unavailable'); }), /1 of 2 documents uploaded.*materials list could not be refreshed.*Check Box before retrying/);
});

test('a completed upload refreshes Materials once without an error', async context => {
  const originalFetch = globalThis.fetch;
  context.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => response({ files: [{ name: 'First.docx' }, { name: 'Second.pdf' }] });
  let refreshes = 0;
  await uploadDocuments('Peer Feedback', documents(), async () => { refreshes += 1; });
  assert.equal(refreshes, 1);
});
