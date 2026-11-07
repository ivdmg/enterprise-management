export const demoMode = import.meta.env.MODE === 'demo';
export const sessionKey = demoMode ? 'seh-demo-tokens' : 'seh-tokens';
