/**
 * Authentication and configuration normalization logic for Lot Zero.
 */

export function isDemoCredential(key) {
  if (!key || typeof key !== 'string') return false;
  return key.startsWith('key-') || key.includes('eval-') || key.includes('demo');
}

/**
 * Safely inspect and return window.localStorage if accessible.
 * Returns null if localStorage is undefined, blocked, partitioned, or throws SecurityError.
 */
export function getSafeStorage() {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const testKey = '__lot_zero_storage_test__';
      window.localStorage.setItem(testKey, '1');
      window.localStorage.removeItem(testKey);
      return window.localStorage;
    }
  } catch (_) {
    // Storage access denied (e.g. sandboxed iframe, incognito, disabled cookies)
  }
  return null;
}

export function safeGetItem(storage, key, defaultValue = '') {
  if (!storage) return defaultValue;
  try {
    const val = storage.getItem(key);
    return val !== null && val !== undefined ? val : defaultValue;
  } catch (_) {
    return defaultValue;
  }
}

export function safeSetItem(storage, key, value) {
  if (!storage) return false;
  try {
    storage.setItem(key, String(value));
    return true;
  } catch (_) {
    return false;
  }
}

export function safeRemoveItem(storage, key) {
  if (!storage) return false;
  try {
    storage.removeItem(key);
    return true;
  } catch (_) {
    return false;
  }
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
      safeSetItem(storage, 'lot_zero_api_key', activeKey);
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
  if (currentStoredKey && isDemoCredential(currentStoredKey)) {
    safeRemoveItem(storage, 'lot_zero_api_key');
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
