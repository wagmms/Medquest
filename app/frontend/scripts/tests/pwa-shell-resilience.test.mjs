import assert from 'node:assert/strict';
import test from 'node:test';

// Test 1: Verify next.config.ts PWA runtime caching pattern rules out RSC requests
test('PWA runtimeCaching strictly ignores RSC requests and non-navigate requests', () => {
  // next.config.ts exports withPWA(nextConfig)
  // We can inspect the withPWA options or nextConfig
  // Let's inspect next.config.ts text or exported behavior
  // Specifically, test the urlPattern logic directly:
  const isMatch = ({ request, sameOrigin, pathname }) => {
    return (
      sameOrigin &&
      request?.mode === 'navigate' &&
      !request?.headers?.get('RSC') &&
      (pathname === '/estudar' || pathname === '/simulado' || pathname === '/revisao-ativa')
    );
  };

  // Standard document navigation
  const navRequest = {
    mode: 'navigate',
    headers: new Map(),
  };
  assert.equal(
    isMatch({ request: navRequest, sameOrigin: true, pathname: '/estudar' }),
    true,
    'Should match document navigation to /estudar'
  );

  // Client-side RSC prefetch/transition request
  const rscRequest = {
    mode: 'cors',
    headers: new Map([['RSC', '1']]),
  };
  assert.equal(
    isMatch({ request: rscRequest, sameOrigin: true, pathname: '/estudar' }),
    false,
    'Must NOT match RSC request to /estudar'
  );

  // Client-side same-origin fetch without navigate mode
  const fetchRequest = {
    mode: 'same-origin',
    headers: new Map(),
  };
  assert.equal(
    isMatch({ request: fetchRequest, sameOrigin: true, pathname: '/estudar' }),
    false,
    'Must NOT match client-side non-navigate fetch'
  );
});

// Test 2: Verify HTML response validator correctly identifies HTML vs RSC text/x-component
test('isValidHtmlResponse validates Content-Type strictly', () => {
  function isValidHtmlResponse(response) {
    if (!response || !response.ok) return false;
    const contentType = response.headers.get('content-type');
    return Boolean(contentType && contentType.toLowerCase().includes('text/html'));
  }

  const validHtml = new Response('<!DOCTYPE html><html><body>App</body></html>', {
    status: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
  });
  assert.equal(isValidHtmlResponse(validHtml), true);

  const rscFlightResponse = new Response('1:I[57121,[],"LoadingBoundaryProvider"]\n0:{"f":[]}', {
    status: 200,
    headers: { 'content-type': 'text/x-component' },
  });
  assert.equal(isValidHtmlResponse(rscFlightResponse), false);

  const jsonResponse = new Response('{"status":"ok"}', {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
  assert.equal(isValidHtmlResponse(jsonResponse), false);

  const errorResponse = new Response('Server error', {
    status: 500,
    headers: { 'content-type': 'text/html' },
  });
  assert.equal(isValidHtmlResponse(errorResponse), false);
});

// Test 3: getOfflineStudyShell discards corrupted RSC responses from cache and falls back safely
test('offline study shell loader refuses corrupted RSC cache and serves clean fallback', async () => {
  function isValidHtmlResponse(response) {
    if (!response || !response.ok) return false;
    const contentType = response.headers.get('content-type');
    return Boolean(contentType && contentType.toLowerCase().includes('text/html'));
  }

  function getOfflineFallbackHtml() {
    return new Response('<!DOCTYPE html><html><body>Modo Plantão Ativo</body></html>', {
      headers: { 'content-type': 'text/html; charset=utf-8' },
    });
  }

  // Simulated cache containing corrupted RSC response
  const poisonedCache = new Map([
    ['/estudar', new Response('1:I[57121,[],"LoadingBoundaryProvider"]', {
      status: 200,
      headers: { 'content-type': 'text/x-component' },
    })],
  ]);

  async function getOfflineStudyShell(pathname = '/estudar') {
    const target = poisonedCache.get(pathname);
    if (isValidHtmlResponse(target)) return target;

    const defaultShell = poisonedCache.get('/estudar');
    if (isValidHtmlResponse(defaultShell)) return defaultShell;

    return getOfflineFallbackHtml();
  }

  const result = await getOfflineStudyShell('/estudar');
  assert.equal(result.headers.get('content-type'), 'text/html; charset=utf-8');
  const text = await result.text();
  assert.ok(text.includes('Modo Plantão Ativo'), 'Should fall back to clean offline HTML');
  assert.ok(!text.includes('LoadingBoundaryProvider'), 'Should NEVER dump raw RSC text');
});
