/* Pure prototype rules. Money is always represented in integer pence. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.Penny = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const MINIMUM = 200, RESERVATION_MS = 30 * 60 * 1000, RECOVERY_MS = 60 * 60 * 1000;
  function money(pence) { return '£' + (pence / 100).toFixed(2); }
  function parseMoney(text) {
    const value = String(text).trim();
    if (!/^\d+(?:\.\d{1,2})?$/.test(value)) return null;
    const [pounds, pennies = ''] = value.split('.');
    const result = Number(pounds) * 100 + Number(pennies.padEnd(2, '0'));
    return Number.isSafeInteger(result) ? result : null;
  }
  function progress(approved, total) {
    if (approved === total) return '100%';
    if (approved === 0) return '0%';
    const rounded = Math.round(approved / total * 100);
    return rounded === 0 ? '<1%' : Math.min(99, rounded) + '%';
  }
  function counts(challenge, total, now = Date.now()) {
    const result = {approved: 0, pending: 0, reserved: 0, available: total, amount: 0};
    const occupied = new Set();
    for (const claim of challenge.claims) {
      if (!['approved', 'pending'].includes(claim.status)) continue;
      for (const id of claim.amounts) {
        if (!occupied.has(id)) { occupied.add(id); result[claim.status]++; }
      }
      if (claim.status === 'approved') result.amount += claim.amount;
    }
    if (challenge.attempt && challenge.attempt.expiresAt > now) {
      for (const id of challenge.attempt.amounts) {
        if (!occupied.has(id)) { occupied.add(id); result.reserved++; }
      }
    }
    result.available = total - occupied.size;
    return result;
  }
  function available(challenge, total, now = Date.now()) {
    const occupied = new Set(challenge.claims.filter(c => ['pending','approved'].includes(c.status)).flatMap(c => c.amounts));
    if (challenge.attempt && challenge.attempt.expiresAt > now) challenge.attempt.amounts.forEach(i => occupied.add(i));
    return Array.from({length: total}, (_, i) => i + 1).filter(i => !occupied.has(i));
  }
  function reference(used, random = Math.random) {
    for (let i = 0; i < 100; i++) {
      const ref = 'EPC-' + Math.floor(random() * 1000000).toString().padStart(6, '0');
      if (!used.includes(ref)) return ref;
    }
    throw new Error('Unable to create a new reference. Please try again.');
  }
  // Try a small, varied allocation first. Exact subset-sum fallback handles scarce amounts.
  // Shuffling affects proposals only: a donor must accept one before checkout.
  function allocate(values, target, random = Math.random) {
    if (!Number.isSafeInteger(target) || target < MINIMUM) return null;
    const pool = values.filter(v => v <= target);
    if (pool.reduce((a,b) => a+b, 0) < target) return null;
    const set = new Set(pool);
    const preferred = Math.min(8, pool.length);
    const sizes = Array.from({length: Math.min(12, pool.length)}, (_, i) => i + 1)
      .sort((a,b) => Math.abs(a-preferred)-Math.abs(b-preferred));
    for (const size of sizes) {
      for (let trial = 0; trial < 100; trial++) {
        const picked = [], used = new Set(); let remaining = target;
        for (let k = size; k > 1; k--) {
          const average = remaining / k;
          const candidates = pool.filter(v => !used.has(v) && v < remaining && v >= average * .35 && v <= average * 1.65);
          if (!candidates.length) break;
          const value = candidates[Math.floor(random() * candidates.length)];
          picked.push(value); used.add(value); remaining -= value;
        }
        if (picked.length === size-1 && set.has(remaining) && !used.has(remaining)) return [...picked, remaining].sort((a,b)=>a-b);
      }
    }
    const shuffled = [...pool];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(random() * (i + 1)); [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    const mask = (1n << BigInt(target + 1)) - 1n;
    let reachable = 1n; const history = [];
    for (const value of shuffled) {
      history.push(reachable);
      reachable = (reachable | reachable << BigInt(value)) & mask;
      if ((reachable >> BigInt(target)) & 1n) {
        let remaining = target; const chosen = [];
        for (let i = history.length - 1; i >= 0 && remaining; i--) {
          if (!((history[i] >> BigInt(remaining)) & 1n)) {
            chosen.push(shuffled[i]); remaining -= shuffled[i];
          }
        }
        return chosen.sort((a,b)=>a-b);
      }
    }
    return null;
  }
  function start(challenge, amounts, donor, message, total, now, ref) {
    const sum = amounts.reduce((a,b) => a+b,0);
    if (!donor.trim()) throw new Error('Please enter your name.');
    if (!amounts.length || sum < MINIMUM) throw new Error('Select at least £2.00 before continuing.');
    if (new Set(amounts).size !== amounts.length) throw new Error('A square can only be selected once.');
    // Replacing an attempt releases its old reservation; claims remain unavailable.
    const permitted = new Set(available({...challenge, attempt: null}, total, now));
    if (amounts.some(i => !permitted.has(i))) throw new Error('Some squares are no longer available. Please review your selection.');
    challenge.attempt = {ref, amounts: [...amounts], amount: sum, donor: donor.trim(), message: message.trim(), expiresAt: now + RESERVATION_MS};
    return challenge.attempt;
  }
  function finish(challenge, ref, now) {
    if (challenge.claims.some(c => c.ref === ref)) throw new Error('This return has already been processed.');
    const attempt = challenge.attempt;
    if (!attempt || attempt.ref !== ref) throw new Error('This checkout attempt is no longer active. No claim was created.');
    if (attempt.expiresAt <= now) throw new Error('The reservation has expired. Return and select available squares again.');
    const claim = {...attempt, status: 'pending'};
    challenge.claims.push(claim); challenge.attempt = null;
    return claim;
  }
  function review(challenge, ref, action) {
    const claim = challenge.claims.find(c => c.ref === ref);
    if (!claim || claim.status !== 'pending') throw new Error('This claim is no longer pending. The figures have been refreshed.');
    if (!['approved','released'].includes(action)) throw new Error('Unknown review action.');
    claim.status = action;
    return claim;
  }
  return {MINIMUM, RESERVATION_MS, RECOVERY_MS, money, parseMoney, progress, counts, available, allocate, reference, start, finish, review};
});
