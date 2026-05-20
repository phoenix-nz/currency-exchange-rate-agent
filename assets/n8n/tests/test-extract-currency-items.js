/**
 * Integration test for the "Extract Currency Items" Code node.
 *
 * Replicates the exact pipeline n8n runs:
 *   1. Parse ECB XML with xml2js (mergeAttrs:true, explicitArray:false) — same settings the n8n XML node uses.
 *   2. Feed the result through the Code node logic extracted from the workflow JSON.
 *   3. Assert the output items.
 *
 * This test is what would have caught the `c.$.currency` bug before deployment:
 * xml2js with mergeAttrs:true puts attributes directly on the object, not under `$`.
 */

'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const xml2js = require('xml2js');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const FIXTURES = path.join(__dirname, 'fixtures');

/** Parse XML the same way n8n's XML node does. */
async function parseXml(xml) {
  return xml2js.parseStringPromise(xml, {
    mergeAttrs: true,
    explicitArray: false,
  });
}

/** Load the Code node JS from the workflow JSON so the test always reflects
 *  the current version of the workflow — not a stale copy. */
function loadCodeNodeScript() {
  const wfPath = path.join(
    __dirname, '..', 'workflows', 'exchange-rate-ecb-sync.n8n.json'
  );
  const wf = JSON.parse(fs.readFileSync(wfPath, 'utf8'));
  const node = wf.nodes.find(n => n.name === 'Extract Currency Items');
  if (!node) throw new Error('Node "Extract Currency Items" not found in workflow JSON');
  return node.parameters.jsCode;
}

/** Run the Code node script against a parsed-XML item, mimicking the n8n sandbox.
 *  n8n exposes `items` as the input array; the script returns an array of items. */
function runCodeNode(parsedJson) {
  const items = [{ json: parsedJson }];
  const script = loadCodeNodeScript();

  // Wrap in a function that receives `items` and returns the result of the script.
  // `return` at the top level of the script becomes the function's return value.
  // eslint-disable-next-line no-new-func
  const fn = new Function('items', script);
  return fn(items);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Extract Currency Items — Code node', () => {

  test('parses standard ECB XML and returns one item per currency', async () => {
    const xml = fs.readFileSync(path.join(FIXTURES, 'ecb-rates.xml'), 'utf8');
    const parsed = await parseXml(xml);
    const result = runCodeNode(parsed);

    assert.equal(result.length, 5, 'should return 5 currency items');

    const usd = result.find(r => r.json.TargetCurrency === 'USD');
    assert.ok(usd, 'USD item must be present');
    assert.equal(usd.json.SourceCurrency, 'EUR');
    assert.equal(usd.json.ExchangeRateType, 'M');
    assert.equal(usd.json.ExchangeRateValue, '1.0821');
    assert.equal(usd.json.ExchangeRateEffectiveDate, '2026-05-20');

    const gbp = result.find(r => r.json.TargetCurrency === 'GBP');
    assert.ok(gbp, 'GBP item must be present');
    assert.equal(gbp.json.ExchangeRateValue, '0.8453');

    // Every item must have all required S/4HANA fields
    for (const item of result) {
      assert.ok(item.json.ExchangeRateType, 'ExchangeRateType must not be empty');
      assert.ok(item.json.SourceCurrency, 'SourceCurrency must not be empty');
      assert.ok(item.json.TargetCurrency, 'TargetCurrency must not be empty');
      assert.ok(item.json.ExchangeRateEffectiveDate, 'ExchangeRateEffectiveDate must not be empty');
      assert.ok(item.json.ExchangeRateValue, 'ExchangeRateValue must not be empty');
    }
  });

  test('attributes are NOT nested under $ — they are merged directly onto the object', async () => {
    // This is the exact bug that slipped through before: the original code used c.$.currency
    // but xml2js with mergeAttrs:true puts currency directly on c, not under c.$.
    const xml = fs.readFileSync(path.join(FIXTURES, 'ecb-rates.xml'), 'utf8');
    const parsed = await parseXml(xml);

    // Confirm the parsed shape — currency items must NOT have a $ key
    const dateCube = parsed['gesmes:Envelope'].Cube.Cube;
    const cubes = Array.isArray(dateCube.Cube) ? dateCube.Cube : [dateCube.Cube];
    const first = cubes[0];

    assert.equal(first.currency, 'USD', 'currency must be a direct property, not under $');
    assert.equal(first.rate, '1.0821', 'rate must be a direct property, not under $');
    assert.equal(first.$, undefined, '$ must be undefined (mergeAttrs flattens it away)');
  });

  test('handles single-currency XML (explicitArray:false means no array wrapping)', async () => {
    // When there is only one <Cube currency="..."> child, xml2js with explicitArray:false
    // returns an object instead of a one-element array. The Code node must handle this.
    const xml = fs.readFileSync(path.join(FIXTURES, 'ecb-rates-single-currency.xml'), 'utf8');
    const parsed = await parseXml(xml);
    const result = runCodeNode(parsed);

    assert.equal(result.length, 1, 'single currency should produce one item');
    assert.equal(result[0].json.TargetCurrency, 'USD');
    assert.equal(result[0].json.ExchangeRateValue, '1.0821');
  });

  test('returns M3.missed item when no currencies are in the feed', async () => {
    const xml = fs.readFileSync(path.join(FIXTURES, 'ecb-rates-empty.xml'), 'utf8');
    const parsed = await parseXml(xml);
    const result = runCodeNode(parsed);

    assert.equal(result.length, 1);
    assert.ok(
      result[0].json.milestone.includes('M3.missed'),
      `expected M3.missed milestone, got: ${result[0].json.milestone}`
    );
  });

  test('effective date falls back to today when time attribute is missing', async () => {
    // Simulate a parsed structure with no time attribute
    const parsed = {
      'gesmes:Envelope': {
        Cube: {
          Cube: {
            // no `time` property
            Cube: [{ currency: 'USD', rate: '1.0821' }]
          }
        }
      }
    };
    const result = runCodeNode(parsed);
    const today = new Date().toISOString().slice(0, 10);
    assert.equal(result[0].json.ExchangeRateEffectiveDate, today);
  });

  test('output items have correct field values for all five currencies', async () => {
    const xml = fs.readFileSync(path.join(FIXTURES, 'ecb-rates.xml'), 'utf8');
    const parsed = await parseXml(xml);
    const result = runCodeNode(parsed);

    const expected = [
      { TargetCurrency: 'USD', ExchangeRateValue: '1.0821' },
      { TargetCurrency: 'JPY', ExchangeRateValue: '163.27' },
      { TargetCurrency: 'GBP', ExchangeRateValue: '0.8453' },
      { TargetCurrency: 'CHF', ExchangeRateValue: '0.9312' },
      { TargetCurrency: 'SEK', ExchangeRateValue: '11.0234' },
    ];

    for (const exp of expected) {
      const item = result.find(r => r.json.TargetCurrency === exp.TargetCurrency);
      assert.ok(item, `${exp.TargetCurrency} must be present`);
      assert.equal(
        item.json.ExchangeRateValue,
        exp.ExchangeRateValue,
        `${exp.TargetCurrency} rate mismatch`
      );
    }
  });

});
