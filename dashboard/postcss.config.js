// PostCSS runs Tailwind (and adds browser prefixes) when Vite processes src/index.css.
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
