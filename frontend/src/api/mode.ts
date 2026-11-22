export const browserMockMode = import.meta.env.MODE === 'demo';
export const showcaseMode = import.meta.env.MODE === 'showcase';
export const demoMode = browserMockMode || showcaseMode;
export const sessionKey = demoMode ? 'seh-demo-tokens' : 'seh-tokens';
