import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { getSourceUrlLabel, normalizeUrl } from './portalLabels.js';

describe('Portal and Statutory Citation Label Logic', () => {
  it('Scenario 1: A statutory source URL that differs from the application portal returns Official Source', () => {
    const sourceUrl = 'https://industry.maharashtra.gov.in/policies/miisp-2025-notification.pdf';
    const portalUrl = 'https://maitri.mahaonline.gov.in/';
    const label = getSourceUrlLabel(sourceUrl, portalUrl);
    assert.equal(label, 'Official Source');
  });

  it('Scenario 2: A source URL identical to the application portal returns Department Portal (Fallback)', () => {
    const sourceUrl = 'https://cgwa-bhuneer.mowr.gov.in/';
    const portalUrl = 'https://cgwa-bhuneer.mowr.gov.in/';
    const label = getSourceUrlLabel(sourceUrl, portalUrl);
    assert.equal(label, 'Department Portal (Fallback)');
  });

  it('Scenario 3: A generic root homepage used as a fallback returns Department Portal (Fallback)', () => {
    // Differing hostnames, but source is a bare root homepage
    const sourceUrl = 'https://midc.maharashtra.gov.in/';
    const portalUrl = 'https://maitri.mahaonline.gov.in/';
    const label = getSourceUrlLabel(sourceUrl, portalUrl);
    assert.equal(label, 'Department Portal (Fallback)');

    const gpcbRoot = 'https://gpcb.gujarat.gov.in';
    assert.equal(getSourceUrlLabel(gpcbRoot, 'https://ifp.gujarat.gov.in/'), 'Department Portal (Fallback)');
  });

  it('Scenario 4: A missing statutory source URL returns null', () => {
    assert.equal(getSourceUrlLabel(null, 'https://cgwa-bhuneer.mowr.gov.in/'), null);
    assert.equal(getSourceUrlLabel('', 'https://cgwa-bhuneer.mowr.gov.in/'), null);
    assert.equal(getSourceUrlLabel('   ', 'https://cgwa-bhuneer.mowr.gov.in/'), null);
    assert.equal(getSourceUrlLabel(undefined, 'https://cgwa-bhuneer.mowr.gov.in/'), null);
  });

  it('Scenario 5: A missing application portal URL evaluates source URL correctly', () => {
    // When portal is missing, a deep statutory document is still Official Source
    const deepDoc = 'https://cpcb.gov.in/rules/environmental-statement-form-v.pdf';
    assert.equal(getSourceUrlLabel(deepDoc, null), 'Official Source');
    assert.equal(getSourceUrlLabel(deepDoc, ''), 'Official Source');

    // When portal is missing, a bare root homepage is still identified as Fallback
    const rootHomepage = 'https://cpcb.gov.in/';
    assert.equal(getSourceUrlLabel(rootHomepage, null), 'Department Portal (Fallback)');
  });

  it('Scenario 6: Trailing-slash and URL normalization differences', () => {
    // 6a. Trailing slash vs no slash on identical URLs
    assert.equal(
      getSourceUrlLabel('https://cgwa-bhuneer.mowr.gov.in', 'https://cgwa-bhuneer.mowr.gov.in/'),
      'Department Portal (Fallback)'
    );
    assert.equal(
      getSourceUrlLabel('https://cgwa-bhuneer.mowr.gov.in/', 'https://cgwa-bhuneer.mowr.gov.in'),
      'Department Portal (Fallback)'
    );

    // 6b. Multiple trailing slashes
    assert.equal(
      getSourceUrlLabel('https://cgwa-bhuneer.mowr.gov.in///', 'https://cgwa-bhuneer.mowr.gov.in/'),
      'Department Portal (Fallback)'
    );

    // 6c. Domain casing normalization
    assert.equal(
      getSourceUrlLabel('https://CGWA-BHUNEER.MOWR.GOV.IN/', 'https://cgwa-bhuneer.mowr.gov.in/'),
      'Department Portal (Fallback)'
    );

    // 6d. Distinct legal document URL with trailing slash must NOT be classified as fallback
    const deepDocWithSlash = 'https://industry.maharashtra.gov.in/policies/miisp-2025/';
    assert.equal(
      getSourceUrlLabel(deepDocWithSlash, 'https://maitri.mahaonline.gov.in/'),
      'Official Source'
    );

    // 6e. Distinct legal document URL with query string must NOT be classified as fallback
    const deepDocWithQuery = 'https://cpcb.nic.in/displaypdf.php?id=c2hyZWVzaC9XYXRlcl9BY3RfMTk3NC5wZGY=';
    assert.equal(
      getSourceUrlLabel(deepDocWithQuery, 'https://parivesh.nic.in/'),
      'Official Source'
    );
  });
});
