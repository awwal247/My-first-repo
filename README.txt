Zenith OX v2.8 — Frontend UI refresh (drop-in)
================================================
FRONTEND ONLY. No backend/Python files are touched.

How to apply:
  Copy the `templates/` and `static/` folders from this package into the
  ROOT of your Zenith OX project, overwriting the existing files.
  All Jinja blocks, url_for(), form fields and JS IDs are unchanged, so
  the app keeps working exactly as before — only the look changes.

What changed:
  - static/css/style.css   -> new deep-slate glass theme, indigo→teal accent,
                              Sora/Inter typography, refined buttons, nav rail,
                              gradient brand orb, modern scrollbars (v2.8 block
                              appended at the bottom).
  - templates/base.html    -> added Inter + Sora Google Fonts links.
  - templates/index.html   -> font link now also loads Sora.
  - templates/landing.html -> font link now also loads Sora.
  - static/images/logo-orb.png -> optional brand orb asset.
  - static/js/*            -> unchanged (included so folders drop in cleanly).

Fonts load from Google Fonts via <link> (no build step needed).
