// Tailwind v4's PostCSS plugin also does vendor prefixing (Lightning CSS), so no autoprefixer.
module.exports = {
  plugins: {
    '@tailwindcss/postcss': {},
  },
};
