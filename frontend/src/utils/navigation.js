/**
 * Navigation and role-based routing utilities for BizPermit.
 */

/**
 * Resolves the authoritative home landing page route for a given user based on role.
 *
 * @param {Object|null|undefined} user - The user object from AuthContext
 * @returns {string} The path corresponding to the user's role workspace, or '/' for visitors.
 */
export const getRoleHomeRoute = (user) => {
  if (!user || typeof user !== 'object') {
    return '/';
  }

  switch (user.role) {
    case 'SUPER_ADMIN':
      return '/admin/dashboard';
    case 'DEPARTMENT_OFFICER':
      return '/officer/dashboard';
    case 'BUSINESS_OWNER':
      return '/dashboard';
    default:
      return '/';
  }
};
