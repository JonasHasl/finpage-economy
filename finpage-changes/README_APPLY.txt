How to apply these changes to your local clone of jonashasl/finpage
=====================================================================

Option A -- copy files directly (simplest):
  Extract this zip and copy its src/ folder on top of your local repo's
  src/ folder (it will overwrite 4 existing files and add 2 new ones):

    overwritten: src/app.py, src/pages/home.py, src/pages/useconomy.py,
                 src/assets/custom.css
    new files:   src/data_sources.py, src/pages/comparison.py

  Then from your repo root:
    git checkout -b claude/home-page-economy-data-i9gg69
    git add src/app.py src/data_sources.py src/pages/home.py \
            src/pages/comparison.py src/pages/useconomy.py src/assets/custom.css
    git commit -m "Add multi-country Economy drill-down and Comparison page"
    git push -u origin claude/home-page-economy-data-i9gg69

Option B -- apply the included patch instead:
    git checkout -b claude/home-page-economy-data-i9gg69
    git apply CHANGES.patch
    git add -A
    git commit -m "Add multi-country Economy drill-down and Comparison page"
    git push -u origin claude/home-page-economy-data-i9gg69

What changed
============
- src/data_sources.py (NEW): shared FRED / Yahoo Finance / Norges Bank / SSB
  fetchers, YoY calc, caching -- powers both pages below.
- src/pages/useconomy.py: /economy is now a market selector (US, Norway,
  EU with Germany/France/Italy/Spain drill-down, UK). Japan and China are
  intentionally skipped for now. US tab behavior/data is unchanged, just
  wrapped; added GDP YoY + a stat-card row.
- src/pages/comparison.py (NEW): /comparison -- GDP, CPI, 10Y yield, and
  unemployment compared across US/Norway/EU/UK on one page, with a country
  toggle.
- src/app.py: nav renamed "US Economy" -> "Economy", added "Comparison" link.
- src/pages/home.py: fixed the stale "US Economy" card copy, added a
  Comparison card.
- src/assets/custom.css: styling for the market selector, stat cards, EU
  country picker, and comparison toggle buttons.

Tested in a sandboxed environment with FRED/Yahoo/Norges Bank/SSB network
access blocked by policy -- confirmed the app boots cleanly, all four
Economy tabs render (with graceful "No data available" placeholders given
the blocked network), the EU sub-country switch works, and the Comparison
page's country toggles work, all with zero console/server errors. Could
not verify actual live data values end-to-end since this sandbox can't
reach those APIs -- worth a first real look after you deploy/run locally
with real network access.
