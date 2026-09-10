export const GROUPS = {
  upper: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', lower: 'abcdefghijklmnopqrstuvwxyz',
  numbers: '0123456789', symbols: '!@#$%^&*()-_=+[]{}:,.?',
};
function randomIndex(size, cryptoSource) {
  const limit = Math.floor(4294967296 / size) * size;
  const value = new Uint32Array(1);
  do { cryptoSource.getRandomValues(value); } while (value[0] >= limit);
  return value[0] % size;
}
export function generatePassword(length, enabled, cryptoSource = crypto) {
  const groups = Object.keys(GROUPS).filter(key => enabled[key]).map(key => GROUPS[key]);
  if (!groups.length) throw new Error('Select at least one character type.');
  if (!Number.isInteger(length) || length < 8 || length > 64) throw new Error('Choose a length between 8 and 64.');
  const pool = groups.join('');
  const result = groups.map(group => group[randomIndex(group.length, cryptoSource)]);
  while (result.length < length) result.push(pool[randomIndex(pool.length, cryptoSource)]);
  for (let index = result.length - 1; index > 0; index--) {
    const other = randomIndex(index + 1, cryptoSource);
    [result[index], result[other]] = [result[other], result[index]];
  }
  return result.join('');
}
// A local composition estimate, not a breach lookup or cracking guarantee.
export function passwordStrength(password) {
  const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^a-zA-Z0-9]/].filter(pattern => pattern.test(password)).length;
  const common = /password|qwerty|letmein|123456|abcdef|welcome/i.test(password) || /^(.)\1+$/.test(password);
  const score = common || password.length < 10 ? 0 : password.length < 14 || classes < 2 ? 1 : password.length < 20 ? 2 : 3;
  return { score, label: ['Weak', 'Medium', 'Strong', 'Very strong'][score], weak: score < 2 };
}
export function accountPasswordError(password) {
  if (password.length < 12) return 'Use at least 12 characters.';
  if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password) || !/[^\w\s]/.test(password)) return 'Include uppercase, lowercase, a number, and a symbol.';
  return '';
}
