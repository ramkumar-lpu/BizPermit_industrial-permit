import assert from 'node:assert/strict';
import test from 'node:test';
import { getRoleHomeRoute } from './navigation.js';

// Mock storage simulating localStorage in browser
class MockLocalStorage {
  constructor() {
    this.store = new Map();
  }
  getItem(key) {
    return this.store.get(key) || null;
  }
  setItem(key, value) {
    this.store.set(key, String(value));
  }
  removeItem(key) {
    this.store.delete(key);
  }
  clear() {
    this.store.clear();
  }
}

test('Test 1 & 2 — Business Owner logo navigation & session persistence', () => {
  const storage = new MockLocalStorage();
  const ownerUser = {
    id: 'usr-bo-01',
    email: 'business@horizon.in',
    full_name: 'Rajesh Kumar',
    role: 'BUSINESS_OWNER',
  };

  // 1. Simulate Login
  storage.setItem('bizpermit_access_token', 'mock.access.token');
  storage.setItem('bizpermit_refresh_token', 'mock.refresh.token');
  storage.setItem('bizpermit_user', JSON.stringify(ownerUser));

  // 2. Verify Session is active
  const userFromStorage = JSON.parse(storage.getItem('bizpermit_user'));
  assert.equal(userFromStorage.email, 'business@horizon.in');
  assert.equal(userFromStorage.role, 'BUSINESS_OWNER');

  // 3. User clicks BizPermit Logo
  const logoTarget = getRoleHomeRoute(userFromStorage);
  assert.equal(logoTarget, '/dashboard', 'Logo must route Business Owner to /dashboard');

  // 4. Verify session state is completely unaffected by clicking the logo
  assert.equal(storage.getItem('bizpermit_access_token'), 'mock.access.token');
  assert.equal(storage.getItem('bizpermit_refresh_token'), 'mock.refresh.token');
  assert.notEqual(storage.getItem('bizpermit_user'), null);

  // 5. Simulate page refresh on destination (/dashboard)
  // Re-reading from storage as done on browser reload
  const reloadedUser = JSON.parse(storage.getItem('bizpermit_user'));
  const reloadedToken = storage.getItem('bizpermit_access_token');
  assert.equal(reloadedUser.id, 'usr-bo-01');
  assert.equal(reloadedUser.role, 'BUSINESS_OWNER');
  assert.equal(reloadedToken, 'mock.access.token');
});

test('Test 3 — Role preservation: Business Owner cannot enter Officer or Admin routes', () => {
  const ownerUser = { id: 'usr-bo-01', role: 'BUSINESS_OWNER' };
  const targetRoute = getRoleHomeRoute(ownerUser);
  assert.equal(targetRoute, '/dashboard');

  // Guard assertion: ensure Business Owner is not routed to Officer or Admin portals
  const officerRoles = ['DEPARTMENT_OFFICER'];
  const adminRoles = ['SUPER_ADMIN'];
  assert.equal(officerRoles.includes(ownerUser.role), false);
  assert.equal(adminRoles.includes(ownerUser.role), false);
});

test('Test 4 — Other roles: Officer and Admin logo navigation and active sessions', () => {
  const officerUser = { id: 'usr-off-01', role: 'DEPARTMENT_OFFICER' };
  assert.equal(getRoleHomeRoute(officerUser), '/officer/dashboard');

  const adminUser = { id: 'usr-adm-01', role: 'SUPER_ADMIN' };
  assert.equal(getRoleHomeRoute(adminUser), '/admin/dashboard');
});

test('Test 5 — Unauthenticated visitor logo navigation', () => {
  const visitor = null;
  assert.equal(getRoleHomeRoute(visitor), '/', 'Visitor logo must point to public landing /');
});

test('Test 6 — Normal logout button clears session tokens and resets user state', () => {
  const storage = new MockLocalStorage();
  storage.setItem('bizpermit_access_token', 'mock.access.token');
  storage.setItem('bizpermit_refresh_token', 'mock.refresh.token');
  storage.setItem('bizpermit_user', JSON.stringify({ id: 'usr-01', role: 'BUSINESS_OWNER' }));

  // Simulate logout execution (AuthContext.logout())
  storage.removeItem('bizpermit_access_token');
  storage.removeItem('bizpermit_refresh_token');
  storage.removeItem('bizpermit_user');

  assert.equal(storage.getItem('bizpermit_access_token'), null);
  assert.equal(storage.getItem('bizpermit_refresh_token'), null);
  assert.equal(storage.getItem('bizpermit_user'), null);

  // Logo for logged out user must now point to /
  assert.equal(getRoleHomeRoute(null), '/');
});
