// Shared Tailwind class strings for buttons and links (design tokens in index.css, D-43).
export const btn = {
  primary: 'inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white shadow-card hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed',
  secondary: 'inline-flex items-center justify-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-paper disabled:opacity-40 disabled:cursor-not-allowed',
  small: 'inline-flex items-center justify-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed',
  link: 'font-medium text-accent hover:underline underline-offset-2',
}
