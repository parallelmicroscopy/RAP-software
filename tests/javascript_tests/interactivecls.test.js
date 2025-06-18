test('basic math works', () => {
  expect(1 + 1).toBe(2);
});

const {
  zeroPad,
  generateLEDList,
  led_to_arduino_string
} = require('../../javascript/interactivecls.js');

// Test 1: Zero-padding utility
test('zeroPad pads numbers with leading zeros', () => {
  expect(zeroPad(5, 3)).toBe('005');
  expect(zeroPad(123, 5)).toBe('00123');
  expect(zeroPad(0, 2)).toBe('00');
});

