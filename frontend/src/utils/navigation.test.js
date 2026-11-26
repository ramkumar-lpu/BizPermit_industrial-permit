import assert from 'node:assert/strict';
import test from 'node:test';
import { getRoleHomeRoute } from './navigation.js';

test('getRoleHomeRoute returns / for unauthenticated visitor (null, undefined, non-object)', () => {
  assert.equal(getRoleHomeRoute(null), '/');
  assert.equal(getRoleHomeRoute(undefined), '/');
  assert.equal(getRoleHomeRoute(false), '/');
  assert.equal(getRoleHomeRoute('invalid'), '/');
});

test('getRoleHomeRoute returns / for missing, empty, or unknown roles', () => {
  // Empty user object
  assert.equal(getRoleHomeRoute({}), '/');
  // Object with no role property
  assert.equal(getRoleHomeRoute({ id: 'usr-no-role', email: 'test@biz.in' }), '/');
  // Object with empty string role
  assert.equal(getRoleHomeRoute({ id: 'usr-empty-role', role: '' }), '/');
  // Object with null role
  assert.equal(getRoleHomeRoute({ id: 'usr-null-role', role: null }), '/');
  // Authenticated user with an unknown/unsupported role
  assert.equal(getRoleHomeRoute({ id: 'usr-unknown', role: 'AUDITOR' }), '/');
  assert.equal(getRoleHomeRoute({ id: 'usr-unknown-2', role: 'GUEST' }), '/');
});

test('Test 1 — Business Owner logo navigation destination', () => {
  const businessOwner = { id: 'usr-1', email: 'owner@horizon.in', role: 'BUSINESS_OWNER' };
  const destination = getRoleHomeRoute(businessOwner);
  assert.equal(destination, '/dashboard', 'Business Owner must be routed to /dashboard, not /');
});

test('Test 3 — Role preservation: Business Owner destination is strictly /dashboard', () => {
  const businessOwner = { id: 'usr-1', email: 'owner@horizon.in', role: 'BUSINESS_OWNER' };
  assert.notEqual(getRoleHomeRoute(businessOwner), '/admin/dashboard');
  assert.notEqual(getRoleHomeRoute(businessOwner), '/officer/dashboard');
  assert.notEqual(getRoleHomeRoute(businessOwner), '/');
});

test('Test 4 — Other supported roles: Officer and Administrator destinations', () => {
  const officer = { id: 'usr-2', email: 'officer@pcb.gov.in', role: 'DEPARTMENT_OFFICER' };
  assert.equal(getRoleHomeRoute(officer), '/officer/dashboard', 'Department Officer must navigate to /officer/dashboard');

  const admin = { id: 'usr-3', email: 'admin@bizpermit.gov.in', role: 'SUPER_ADMIN' };
  assert.equal(getRoleHomeRoute(admin), '/admin/dashboard', 'Super Admin must navigate to /admin/dashboard');
});
