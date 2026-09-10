import {test} from 'node:test';
import assert from 'node:assert/strict';
import {generatePassword, passwordStrength, accountPasswordError} from '../security.js';

test('generator enforces selected classes and bounds with fresh random output',()=>{
  const options={upper:true,lower:true,numbers:true,symbols:true};
  const passwords=Array.from({length:50},()=>generatePassword(24,options));
  assert.equal(new Set(passwords).size,50);
  for(const password of passwords){assert.equal(password.length,24);for(const pattern of [/[A-Z]/,/[a-z]/,/[0-9]/,/[^a-zA-Z0-9]/])assert.match(password,pattern);}
  assert.match(generatePassword(64,{numbers:true}),/^\d{64}$/);
  assert.throws(()=>generatePassword(20,{}),/Select/);
  assert.throws(()=>generatePassword(7,options),/between/);
});
test('generator rejects biased random tail values rather than reducing them modulo pool size',()=>{
  let calls=0;
  const fakeCrypto={getRandomValues(array){array[0]=calls++===0?4294967295:0;return array;}};
  assert.equal(generatePassword(8,{numbers:true},fakeCrypto),'00000000');
  assert.ok(calls>8);
});
test('composition estimates do not reward common or repetitive passwords',()=>{
  assert.equal(passwordStrength('passwordpassword123!').weak,true);
  assert.equal(passwordStrength('AAAAAAAAAAAAAAAAAAAA').weak,true);
  assert.equal(passwordStrength('nZ8!wX2@pL5#sR9&mK4%').label,'Very strong');
  assert.ok(accountPasswordError('short'));
  assert.equal(accountPasswordError('LongUniqueTest!9'),'');
});
