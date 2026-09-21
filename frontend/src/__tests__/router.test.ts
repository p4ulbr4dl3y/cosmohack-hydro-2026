// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { router } from '../router';

describe('router route configurations', () => {
  const routes = router.routes;

  it('defines 8 application routes including wildcard 404', () => {
    expect(routes.length).toBe(8);
  });

  it('contains root path / mapped to Landing page', () => {
    const rootRoute = routes.find((r) => r.path === '/');
    expect(rootRoute).toBeDefined();
    expect(rootRoute?.element).toBeDefined();
  });

  it('contains /dashboard and /dashboard/:pairId paths', () => {
    const dashRoute = routes.find((r) => r.path === '/dashboard');
    const pairRoute = routes.find((r) => r.path === '/dashboard/:pairId');
    expect(dashRoute).toBeDefined();
    expect(pairRoute).toBeDefined();
  });

  it('contains /report/:pairId path', () => {
    const reportRoute = routes.find((r) => r.path === '/report/:pairId');
    expect(reportRoute).toBeDefined();
  });

  it('contains /compare/:pairId path', () => {
    const compareRoute = routes.find((r) => r.path === '/compare/:pairId');
    expect(compareRoute).toBeDefined();
  });

  it('contains /methodology path', () => {
    const methRoute = routes.find((r) => r.path === '/methodology');
    expect(methRoute).toBeDefined();
  });

  it('contains /api-docs path', () => {
    const apiRoute = routes.find((r) => r.path === '/api-docs');
    expect(apiRoute).toBeDefined();
  });

  it('contains wildcard catch-all route *', () => {
    const wildcardRoute = routes.find((r) => r.path === '*');
    expect(wildcardRoute).toBeDefined();
  });
});
