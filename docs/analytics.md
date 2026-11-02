# Daily analytics

Open `/admin/analytics/` as a superuser, or as an active staff account with
**Can export daily analytics** (`forum.export_analytics`). The admin home page
links to the exporter. Select dates and metric checkboxes, then download CSV.
The default is the last 30 calendar days, including today. CSV includes a UTF-8
BOM for Excel, stable column order, and one row per Vancouver date.

## Counts

- Unique users are distinct signed-in account IDs with an event that day.
  Overall users deduplicate web and mobile; platform users may overlap.
- Opens count initial display, navigation (including back), reload, and return
  from the background. Renders, API fetching, pagination and admin pages do not
  count. A post detail display counts as both a screen open and a post open.
- Match counts people opening the web Match page or another person's mobile
  schedule-comparison section. Profile search counts successful nonempty searches,
  including empty result sets, but excludes mention autocomplete.
- Volunteer hours counts people opening the feature, not volunteer hours earned.
- Interactions count new likes, follows, poll submissions, replies/comments and
  reply/comment votes. Unchanged submissions, edits, removals, failed actions and
  post creation are excluded. Changing an existing poll ballot is an edit.
- Browser traffic, including mobile browsers and Expo web, is `web`. Native iOS
  and Android screen opens are `mobile`.

## Delivery and storage

`POST /api/analytics/events/` accepts JSON with exactly `id` (UUID), `platform`
(`web` or `mobile`), `event_type` and an allowlisted `screen`. Supported client
events are `screen_open`, `match_open`, `profile_search` and `volunteer_open`.
The server supplies account identity and timestamp. Session authentication requires
CSRF; mobile uses existing token authentication. The endpoint is limited to 120
events per account per minute. UUID retries are idempotent.

Server interaction events originate in shared services after commit and cannot
be submitted through the client endpoint. The `X-WolfKey-Platform` header labels
interactions; older token clients default to mobile, session clients to web.
Client delivery is best-effort, with no offline queue. Analytics database failures
are logged and isolated from business transactions. Client failures warn in the
console and do not interrupt navigation.

Events store timestamps, UUIDs, internal numeric account IDs, predefined screen
names, platforms and event types. No query text, content, URLs, IP addresses or
device IDs are stored. Numeric account IDs intentionally have no foreign key, so
account deletion cannot prevent deletion or rewrite historical daily counts.
Raw events are not exposed through the admin; exports contain aggregate counts.

## Release

1. Deploy the backend and run `python manage.py migrate`. Migration 0077 creates
   the event tables, permission and persistent tracking-start timestamp.
2. Confirm web tracking and an authorized CSV download.
3. Release the WolfKeyMobile changes after the backend is available. Older apps
   have no screen tracking; server interaction counts can still include them.

The export page displays tracking start. Earlier dates are blank; tracked days
without events are zero. The first day and current day can be partial. Counts
are on-demand from stored events and have no Google Analytics or lifetime-view
counter backfill. Mobile counts grow with adoption of the updated app; they do
not imply coverage of older installations. Server timestamps assign delayed
events to their arrival date.

## Verification

Use PostgreSQL for `python manage.py test forum.tests.test_analytics`; existing
migrations require `pg_trgm`. Browser lifecycle tests run with
`node --test forum/tests/js/test_analytics.mjs`. In WolfKeyMobile, run
`node --test tests/analytics.test.mjs`.

For a live check, open a post twice with a back navigation, open Match, perform a
profile search and open volunteer hours. Export today's metrics and confirm
repeat opens, one unique account per feature, and no opens from background API
requests. Repeat on an updated native app and confirm platform counts while
overall unique users still deduplicate the account.
