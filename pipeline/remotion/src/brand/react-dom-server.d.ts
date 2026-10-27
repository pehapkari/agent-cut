// react-dom ships no types here; only renderToStaticMarkup is used (export.tsx).
declare module "react-dom/server" {
  export function renderToStaticMarkup(element: React.ReactNode): string;
}
