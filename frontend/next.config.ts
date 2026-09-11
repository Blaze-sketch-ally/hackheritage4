import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `/` has no landing page of its own -- the login flow is the entry
  // point. A framework-level redirect (real 307, resolved before
  // middleware/rendering) rather than a page-level `redirect()` call:
  // the latter statically prerenders `/` as a 200 HTML page with a
  // 1-second <meta http-equiv="refresh"> fallback (verified locally via
  // `next build` + `next start`), which is a visible delay and not a true
  // HTTP redirect. This is instant and works identically for browsers,
  // curl, and crawlers. app/page.tsx keeps its own `redirect("/login")`
  // as a harmless fallback in case this config redirect is ever removed.
  async redirects() {
    return [
      {
        source: "/",
        destination: "/login",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
