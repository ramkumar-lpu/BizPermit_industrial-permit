/**
 * Utility functions for regulatory portal and citation reference labels.
 */

/**
 * Determines the appropriate user-facing label for a statutory citation or source URL.
 *
 * Prevents generic root department homepages from being misleadingly labeled as
 * verified "Official Source" citations.
 *
 * @param {string|null|undefined} sourceUrl - The statutory source / citation reference URL
 * @param {string|null|undefined} officialPortalUrl - The application portal URL
 * @returns {string|null} The display label ('Department Portal (Fallback)' or 'Official Source'), or null if missing.
 */
/**
 * Normalizes a URL for comparison by standardizing protocol, hostname casing,
 * and stripping redundant trailing slashes from the pathname.
 *
 * @param {string|null|undefined} urlStr
 * @returns {string} Normalized URL string
 */
export const normalizeUrl = (urlStr) => {
  if (!urlStr || typeof urlStr !== 'string') return '';
  const trimmed = urlStr.trim();
  if (!trimmed) return '';

  try {
    const parsed = new URL(trimmed);
    const origin = parsed.origin.toLowerCase();
    const pathname = parsed.pathname.replace(/\/+$/, '');
    const search = parsed.search || '';
    const hash = parsed.hash || '';
    return `${origin}${pathname}${search}${hash}`;
  } catch (e) {
    return trimmed.replace(/\/+$/, '').toLowerCase();
  }
};

/**
 * Determines the appropriate user-facing label for a statutory citation or source URL.
 *
 * Prevents generic root department homepages from being misleadingly labeled as
 * verified "Official Source" citations.
 *
 * @param {string|null|undefined} sourceUrl - The statutory source / citation reference URL
 * @param {string|null|undefined} officialPortalUrl - The application portal URL
 * @returns {string|null} The display label ('Department Portal (Fallback)' or 'Official Source'), or null if missing.
 */
export const getSourceUrlLabel = (sourceUrl, officialPortalUrl) => {
  if (!sourceUrl || typeof sourceUrl !== 'string' || !sourceUrl.trim()) {
    return null;
  }

  const normSource = normalizeUrl(sourceUrl);
  const normPortal = normalizeUrl(officialPortalUrl);

  // 1. Identical to application portal -> Fallback
  if (normPortal && normSource === normPortal) {
    return 'Department Portal (Fallback)';
  }

  // 2. Generic root domain check (no deep path, query, or hash) -> Fallback
  try {
    const parsed = new URL(sourceUrl.trim());
    const path = parsed.pathname.replace(/\/+$/, '');
    if ((path === '' || path === '/') && !parsed.search && !parsed.hash) {
      return 'Department Portal (Fallback)';
    }
  } catch (e) {
    if (/^https?:\/\/[^\/]+\/*$/i.test(sourceUrl.trim())) {
      return 'Department Portal (Fallback)';
    }
  }

  // 3. Genuine deep citation / statutory reference document
  return 'Official Source';
};
