/**
 * Authentication and configuration normalization logic for Lot Zero.
 */

export function isDemoCredential(key) {
  if (!key || typeof key !== 'string') return false;
  return key.startsWith('key-') || key.includes('eval-') || key.includes('demo');
}

export function normalizeConfig(serverData, currentStoredKey = '', storage = null) {
  // Server-confirmed evaluation mode
  if (serverData && serverData.evaluation_mode === true) {
    const personas = Array.isArray(serverData.personas) ? serverData.personas : [];
    const tenant_id = serverData.tenant_id || '';

    let activeKey = '';
    const matchingPersona = personas.find((p) => p.key === currentStoredKey);
    if (matchingPersona) {
      activeKey = matchingPersona.key;
    } else if (personas.length > 0) {
      activeKey = personas[0].key;
      if (storage) {
        try {
          storage.setItem('lot_zero_api_key', activeKey);
        } catch (_) {}
      }
    }

    return {
      config: {
        evaluation_mode: true,
        tenant_id,
        personas,
      },
      activeApiKey: activeKey,
    };
  }

  // Non-evaluation mode or server failure: FAIL CLOSED
  if (storage && currentStoredKey && isDemoCredential(currentStoredKey)) {
    try {
      storage.removeItem('lot_zero_api_key');
    } catch (_) {}
  }

  const sanitizedKey = isDemoCredential(currentStoredKey) ? '' : (currentStoredKey || '');

  return {
    config: {
      evaluation_mode: false,
      tenant_id: '',
      personas: [],
    },
    activeApiKey: sanitizedKey,
  };
}

export function getEffectiveAuthHeaders(activeApiKey, evaluationMode = false) {
  if (!activeApiKey) return {};
  if (!evaluationMode && isDemoCredential(activeApiKey)) {
    return {};
  }
  return { 'X-API-Key': activeApiKey };
}

export function buildRequestHeaders(activeApiKey, evaluationMode = false, extraHeaders = {}) {
  const auth = getEffectiveAuthHeaders(activeApiKey, evaluationMode);
  return {
    ...extraHeaders,
    ...auth,
  };
}

export function canStartSse(configStatus, activeApiKey, evaluationMode = false) {
  if (configStatus !== 'ready') return false;
  const headers = getEffectiveAuthHeaders(activeApiKey, evaluationMode);
  return Boolean(headers['X-API-Key']);
}

export function hasEffectiveAuth(activeApiKey, evaluationMode = false) {
  const headers = getEffectiveAuthHeaders(activeApiKey, evaluationMode);
  return Boolean(headers['X-API-Key']);
}
