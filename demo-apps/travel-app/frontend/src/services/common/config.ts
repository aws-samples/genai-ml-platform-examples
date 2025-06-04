interface ServiceConfig {
  // API configuration
  apiEndpoint: string;
  apiVersion: string;
  
  // WebSocket configuration
  webSocketEndpoint: string;
  
  // Request configuration
  requestTimeout: number;
  maxRetries: number;
  
  // Authentication
  authEnabled: boolean;
  
  // Debug settings
  debug: boolean;
  
  
  // Backend-strands compatibility mode
  useBackendStrands: boolean;
}

/**
 * Get a configuration value from environment variables with a fallback
 */
function getConfigValue(key: string, defaultValue: string): string {
  const envKey = `REACT_APP_${key.toUpperCase()}`;
  const value = process.env[envKey] || defaultValue;
  
  // Log important configuration values
  if (key === 'USE_BACKEND_STRANDS') {
    console.log(`Config: ${key} = ${value} (from ${process.env[envKey] ? 'env' : 'default'})`);
  }
  
  return value;
}

// Load API endpoint from environment with fallback
const apiEndpoint = getConfigValue('API_ENDPOINT', 'https://api.example.com/dev');

// Load WebSocket endpoint from environment with fallback
// If backend-strands mode is enabled and no WebSocket endpoint is provided, use empty string to trigger polling
const useBackendStrands = getConfigValue('USE_BACKEND_STRANDS', 'false') === 'true';
const webSocketEndpoint = getConfigValue('WEBSOCKET_ENDPOINT', useBackendStrands ? '' : 'wss://ws.example.com/dev');

// Add a warning if using default endpoints in production
if (process.env.NODE_ENV === 'production' && 
    (apiEndpoint.includes('example.com') || webSocketEndpoint.includes('example.com'))) {
  console.error(
    '⚠️ ERROR: Using default API endpoints in production! ⚠️\n' +
    'The application will not work correctly with these placeholder endpoints.\n' +
    'Please configure REACT_APP_API_ENDPOINT and REACT_APP_WEBSOCKET_ENDPOINT environment variables.\n' +
    'See PRODUCTION-SETUP.md for instructions on how to set up endpoints.'
  );
  
  // Display more visible warning if in browser
  if (typeof window !== 'undefined') {
    setTimeout(() => {
      alert(
        'Warning: Using default API endpoints in production!\n\n' +
        'The application will not connect to your backend services. ' +
        'Please set up the correct environment variables.'
      );
    }, 1000);
  }
}

// Development warning
if (process.env.NODE_ENV === 'development' && 
    (apiEndpoint.includes('example.com') || webSocketEndpoint.includes('example.com'))) {
  console.warn(
    '⚠️ Warning: Using placeholder API endpoints in development ⚠️\n' +
    'For proper development, configure endpoints in .env.local or .env.development file.\n' +
    'See DEV-ENV-SETUP.md for instructions.'
  );
}

/**
 * Service configuration object
 */
export const config: ServiceConfig = {
  apiEndpoint,
  apiVersion: getConfigValue('API_VERSION', 'v1'),
  
  webSocketEndpoint,
  
  requestTimeout: parseInt(getConfigValue('REQUEST_TIMEOUT', '180000')),
  maxRetries: parseInt(getConfigValue('MAX_RETRIES', '3')),
  
  authEnabled: getConfigValue('AUTH_ENABLED', 'false') === 'true',
  
  debug: process.env.NODE_ENV === 'development',
  
  // Backend-strands compatibility mode
  useBackendStrands: useBackendStrands,
};

export default config; 