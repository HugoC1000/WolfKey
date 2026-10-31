# Markdown content contract

Posts, solutions, comments, and replies store both `content` (Editor.js JSON) and
`content_markdown` (Markdown). The JSON and Markdown API families each return their
own representation for every record, including records authored by the other
family. Poll choices remain in poll tables, separate from the post body.

## API routes

| Action | Editor.js JSON | Markdown |
| --- | --- | --- |
| List posts | `GET /api/all-posts/`, `/api/for-you/` | `GET /api/v2/all-posts/`, `/api/v2/for-you/` |
| Create post | `POST /api/posts/create/` | `POST /api/v2/posts/create/` |
| Get post and responses | `GET /api/posts/<id>/` | `GET /api/v2/posts/<id>/` |
| Edit/delete post | `/api/posts/<id>/edit/`, `/delete/` | `/api/v2/posts/<id>/edit/`, `/delete/` |
| Create solution | `POST /api/posts/<id>/solutions/create/` | `POST /api/v2/posts/<id>/solutions/create/` |
| Edit/delete solution | `/api/solutions/<id>/edit/`, `/delete/` | `/api/v2/solutions/<id>/edit/`, `/delete/` |
| Create comment/reply | `POST /api/solutions/<id>/comments/create/` | `POST /api/v2/solutions/<id>/comments/create/` |
| List comments | `GET /api/solutions/<id>/comments/` | `GET /api/v2/solutions/<id>/comments/` |
| Edit/delete comment | `/api/comments/<id>/edit/`, `/delete/` | `/api/v2/comments/<id>/edit/`, `/delete/` |

The v2 API accepts a Markdown string in `content`; the original API accepts an
Editor.js document with a `blocks` array. The original web comment endpoint
also accepts its older plain-text payload and projects it as one JSON
paragraph. Replies use the comment create endpoint with `parent_id`.

Post creation requires a title; the v2 post body may be omitted or empty.
Solutions and comments still require nonempty content. Feed `page` and `limit`
must be positive integers (defaults: 1 and 8); invalid values return HTTP 400.

## Conversion profile

The shared converter supports paragraphs, headings, block quotes, ordered and
unordered lists, bold, emphasis, strikeout, inline code, fenced code with a
language, links, images, horizontal rules, `$...$` inline math, `$$...$$`
block math, and plain-text `@username` and course mentions. Markdown is
stored as submitted (apart from trimming outer whitespace), so its source is
preserved even when the Editor.js projection cannot represent it exactly.
Tables become readable text in the JSON projection. Nested lists and custom
Editor.js blocks do not round-trip structurally; unknown blocks retain their
text when available. Conversion does not execute raw HTML. Server-rendered
HTML is sanitized, and the mobile renderer restricts links and images to
approved URL schemes. Mobile currently displays math delimiters as text;
the web renderer typesets them with KaTeX.

## Rollout

1. Release the interim mobile build with `CONTENT_API_VERSION = 'v1'`. It reads
   and writes Editor.js content through the existing API.
2. Deploy the server and web assets, and apply migration `0075_markdown_content`.
   It backfills Markdown without modifying the existing JSON and refreshes post
   search vectors. Large installations should account for the full-table
   backfill. Keep `LEGACY_APP_UPDATE_ONLY` unset so legacy all-posts and for-you
   feeds continue to return normal posts.
3. Verify that the deployed server serves `/api/v2/`, then release the mobile
   build with `CONTENT_API_VERSION = 'v2'`.
4. Once the v2 mobile release is available, set `LEGACY_APP_UPDATE_ONLY=True`
   on the server. The legacy feeds then return one admin-authored update post.
5. Keep the JSON field and projection while older clients are supported. When
   that support ends, the JSON compatibility paths and converter can be
   retired in a separate migration.

The web editor's pinned Milkdown Crepe assets are built locally with
`cd web_editor && npm ci && npm run build`. The generated files under
`static/forum/vendor/` are committed for normal Django static deployment.
Read-only post pages render server-side without loading the editor bundle.
