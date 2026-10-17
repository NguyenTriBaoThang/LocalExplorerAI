# Main integration — 2026-10-17

The running checkout was advanced from `158ccec` to main `c7de7a1` on
`integration/main-runtime-20261017`. Local environment, encrypted integration
configuration, PostgreSQL data and private Meshy storage were retained.

## Compatibility fixes

- Merge Alembic heads `0020_meshy_jobs` and `0018_web_push_notifications` into
  `0021_merge_meshy_web_push`; the existing PostgreSQL database was upgraded.
- Convert the imported photo URL condition to a boolean so the Portal builds
  when source data has type `unknown`.
- Regenerate both DATA17 experimental bundles using the recorded local training
  versions. The ranker native text file now loads and matches its metadata hash.
  Preserve this byte-sensitive file with `-text` in `.gitattributes`.
- Pin the experiment's scikit-learn dependency to the regenerated bundle's
  version, 1.8.0. See `experiment_report.json` for the other training versions.

## Validation

- Main API suite: 373 passed using isolated SQLite fixtures.
- After bundle repair: model/ranker tests 18 passed; offline artifact smoke check
  passed for both serialized models and the native LightGBM file.
- Web and Portal production builds passed (large-bundle warnings remain).
- Live HTTPS checks: health, citywide catalog (192 public entries), admin login,
  dashboard and Meshy jobs returned HTTP 200. Database retains 2 users, 202 total
  POIs and 4 Meshy jobs. Gemini 3D remains configured as gemini-2.5-flash.
- Browser dashboard and catalog/3D exploration are checked after deployment.

Both DATA17 models remain synthetic offline experiments with deployment disabled.
The public ranker uses the rule baseline; flood prediction is not enabled by this
integration. Web Push needs VAPID configuration before it can send notifications.
No paid Meshy job or outbound notification was triggered for testing.

## Recovery

The prior code is retained in branch `backup/before-main-integration-20261017`.
The local database snapshot is outside Git at
`../.local-app/integration-main-20261017/before-main.dump`.
Restoring that snapshot would discard later writes, so inspect and back up the
current database before any restore. Runtime ports remain web 8080, Portal 5174,
API 8000; Cloudflare hostnames remain unchanged.
