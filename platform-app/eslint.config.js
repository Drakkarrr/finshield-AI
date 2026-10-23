const { FlatCompat } = require('@eslint/eslintrc');
const js = require('@eslint/js');

const compat = new FlatCompat();

module.exports = [
  js.configs.recommended,
  ...compat.extends('next/core-web-vitals'),
];
