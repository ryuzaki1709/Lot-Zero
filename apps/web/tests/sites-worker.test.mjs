import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker/index.js';

test('sites-worker: passes through existing static asset (200 OK)', async () => {
  const mockEnv = {
    ASSETS: {
      fetch: async () => {
        return new Response('console.log("app");', {
          status: 200,
          headers: { 'Content-Type': 'application/javascript' },
        });
      },
    },
  };

  const req = new Request('https://lot-zero.example/assets/index.js', {
    method: 'GET',
    headers: { accept: '*/*' },
  });

  const res = await worker.fetch(req, mockEnv);
  assert.equal(res.status, 200);
});

test('sites-worker: rewrites 404 HTML navigation requests to /index.html', async () => {
  const fetchCalls = [];
  const mockEnv = {
    ASSETS: {
      fetch: async (req) => {
        fetchCalls.push(new URL(req.url).pathname);
        if (new URL(req.url).pathname === '/index.html') {
          return new Response('<!DOCTYPE html><html><body>SPA Root</body></html>', {
            status: 200,
            headers: { 'Content-Type': 'text/html' },
          });
        }
        return new Response('Not Found', { status: 404 });
      },
    },
  };

  const req = new Request('https://lot-zero.example/incidents/EVAL-CASE-01', {
    method: 'GET',
    headers: { accept: 'text/html,application/xhtml+xml' },
  });

  const res = await worker.fetch(req, mockEnv);
  assert.equal(res.status, 200);
  assert.deepEqual(fetchCalls, ['/incidents/EVAL-CASE-01', '/index.html']);
});

test('sites-worker: does not rewrite 404 non-HTML resource requests', async () => {
  const fetchCalls = [];
  const mockEnv = {
    ASSETS: {
      fetch: async (req) => {
        fetchCalls.push(new URL(req.url).pathname);
        return new Response('Not Found', { status: 404 });
      },
    },
  };

  const req = new Request('https://lot-zero.example/missing-asset.png', {
    method: 'GET',
    headers: { accept: 'image/png,*/*' },
  });

  const res = await worker.fetch(req, mockEnv);
  assert.equal(res.status, 404);
  assert.deepEqual(fetchCalls, ['/missing-asset.png']);
});

test('sites-worker: does not rewrite 404 POST requests', async () => {
  const fetchCalls = [];
  const mockEnv = {
    ASSETS: {
      fetch: async (req) => {
        fetchCalls.push(new URL(req.url).pathname);
        return new Response('Not Found', { status: 404 });
      },
    },
  };

  const req = new Request('https://lot-zero.example/api/action', {
    method: 'POST',
    headers: { accept: 'text/html' },
  });

  const res = await worker.fetch(req, mockEnv);
  assert.equal(res.status, 404);
  assert.deepEqual(fetchCalls, ['/api/action']);
});
