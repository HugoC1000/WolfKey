# Forum code review

Reviewed 2026-09-09: posts, solutions, comments, user/profile models, serializers, web/API views, services, Django forms, and their HTML templates. This is a source review with targeted regression tests, not browser or production-data validation. Mobile source was checked for selected field consumers; it was not changed.

## Findings that still need work, in priority order

### 1. Use the same validation on create and edit

- `forum/views/post_views.py:create_post` validates `PostForm` but then reparses content and booleans from raw POST data. `edit_post` skips the form entirely. Consequently title requirements and maximum lengths are not enforced consistently.
- `forum/forms.py:UserProfileForm` and `UserUpdateForm` exist but `forum/services/profile_service.py:update_profile_info` assigns raw values and repeats parts of the validation. The user record is saved before profile validation finishes: an invalid LinkedIn URL can return an error after a name change has already been saved.
- Comment and solution creation check empty Editor.js blocks, while edits only check whether the outer content value is truthy. An empty block list can pass an edit. Multiple empty paragraphs also bypass the create check.

Recommendation: bind `PostForm` on both web create and edit, consume `cleaned_data`, and reuse one explicit content validator in the write paths. Validate profile/account updates together before saving in one transaction. Preserve omitted fields for the API's partial updates; blindly binding a complete ModelForm would clear or reject unrelated fields.

### 2. Comment API error handling disagrees with its service

`forum/services/comment_services.py` returns `{'status': 'error', 'messages': ...}`, while `forum/api/comment.py:create_comment_api` and `edit_comment_api` check for an `error` key. A rejected create can become a 500 from a missing `id`; a rejected edit can return a success response with unchanged content. Broad exception handlers also turn missing objects into 500s.

Recommendation: agree on one service result format, with Django messages added by the web adapter, and let expected not-found errors retain their HTTP status. Currently comments receive a request, whereas post/solution services receive a user and data. Prefer the latter consistently.

### 3. `Post.solved` duplicates `accepted_solution`

`forum/models/post.py` stores both. Acceptance writes both in `accept_solution_service`, but deleting an accepted solution sets the relation to null without clearing `solved`. The mobile post card uses `solved`, so simply deleting the response field would break it.

Recommendation: retain `solved` in the public response as a derived boolean from `accepted_solution_id`, and remove the database column with a migration plus admin updates. Check existing disagreements before choosing the relation as the sole authority.

### 4. Solution vote counts duplicate vote records

`forum/models/solution.py` stores `upvotes` and `downvotes` alongside `SolutionUpvote` and `SolutionDownvote`. `vote_solution_service` performs read/modify/save operations without a transaction, so concurrent requests can lose counts or leave counts inconsistent with rows. Separate tables also permit a user to have both vote types.

Recommendation: first make vote changes transactional. For a later schema simplification, one `SolutionVote(solution, user, value)` with one vote per user is clearer. Derive counts, or explicitly treat them as maintained caches. These are active fields, not unused fields to drop casually. Preserve current toggle behavior unless intentionally changing the UI.

### 5. Consolidate post and comment serialization

- `PostListSerializer` and `PostDetailSerializer` repeat author anonymity, courses, dates, likes, following, counts, and mentions.
- `CommentSerializer` and `SolutionSerializer` repeat author/date/mention formatting.
- `get_comments_service` manually creates another comment representation, including a different timestamp format. It starts from all comments, then recursively includes replies, repeating replies at the top level. The API serializer starts only from root comments.
- Solution ordering is implemented in both `PostDetailSerializer` and `get_sorted_solutions_service`, with different tie ordering.
- Recursive comment serialization queries relationships repeatedly. `get_depth` caps the displayed number after traversing all parents; it does not bound traversal or protect against cycles in imported/admin data.

Recommendation: use a small shared post serializer base and one explicitly named author serialization helper. Use one comment-tree representation and one solution-ordering function. Keep web/API adapters only where a consumer actually needs a different contract. Avoid a universal generic content/voting framework: it would obscure the distinct post, solution, and comment rules.

### 6. Visibility rules are spread across endpoints

`_check_teacher_visibility` is repeated by inline view checks. The web `get_comments_service` does not check it, even though the API comments reader does. Several edit/read/action paths differ in their checks and exception handling.

Recommendation: one authorized post lookup used by post and related-content endpoints. Add a small permission matrix test for owner, other student, teacher, and anonymous callers before consolidating.

### 7. Website forms and templates contain competing implementations

- `profile.html` repeats schedule parsing and conversion to `block_1A` keys in two scripts. Both accept old/new field spellings, although the serializer already defines the current shape.
- `components/comments_list.html` shows two initial root comments but subtracts three for the hidden count; three roots can say “Show 0 more comments.” Its custom counter and conditional opening/closing tags are harder to follow than passing visible and hidden root lists.
- `post_detail` constructs unused `solution_form`/`comment_form` context while the template writes its Editor.js fields manually. SolutionForm still has active create/edit callers; remove only the unused context, not the entire class.
- Hand-written profile inputs repeat validation metadata defined in forms/models. Keep the Editor.js integration explicit, but render ordinary form fields or source their constraints from the bound form.

Recommendation: extract one profile JavaScript module, consume the canonical schedule shape directly, and pass root-comment slices/counts from the view. Keep form errors and submitted values on the page instead of redirecting away on invalid submission.

## Database field/table decisions

| Item | Evidence | Recommendation |
| --- | --- | --- |
| Comment voting | `CommentUpvote` was previously unused. | Now active alongside `CommentDownvote`; each user has at most one vote per comment. |
| `StandardPost` | No added fields. Current standard creation uses `Post`; Django admin still uses the child table, and a historical migration populated it. | Remove the redundant child model/table after updating admin and checking existing rows. Preserve parent posts. |
| `Post.solved` | Active mobile consumer, redundant stored state. | Derive the response value; migrate away the column. |
| `UserProfile.is_moderator` | API/search display reads the flag, while middleware/permission tags use membership in `Moderators`. | Choose group membership as one authority and migrate existing assignments before removing the flag. |
| `UserProfile.wolfnet_password` | Model and update path import `WolfNetSettingsForm`, which no longer exists. Admin and an API update branch still expose the feature. | Resolve whether the integration is retired. If retired, remove the whole feature path and stored field together; otherwise move encryption into a real helper. |
| `UserProfile.points` | Displayed in profiles/search and returned by APIs; admin can edit it. No automatic earning logic found. | Not proven useless. Keep unless retiring the points feature. |
| `upvotes` / `downvotes` | Active ordering/UI fields backed by separate vote rows. | Treat as derived/cached state, not dead fields. |
| `post_type` / `scope` | Distinct poll-vs-standard and school-vs-community behavior. | Keep both. |
| `allow_teacher`, `is_anonymous`, `accepted_solution`, saved/followed relations | Active permissions, display, acceptance, and independent user actions. | Keep. Saved and followed posts represent different intentions. |

No database schema was changed or migration applied in this review. Repository references cannot establish whether a production table contains data worth preserving.

## Changes made in this review

- Removed unused `get_post_detail_service`, its private formatting helper, and unused imports from both view modules. Active detail responses already use `PostDetailSerializer`.
- Removed unused `Post.get_author`, `MultipleFileInput`, and `MultipleFileField`.
- Removed `PostForm.clean_courses` and its redundant content-presence check. Django's model choice and JSON fields already validate these before custom cleaning. The old course parser ran after course values had already become model objects.
- Removed the `Comment.replies` property duplicating Django's reverse relation.
- Removed the second solution-file cleanup call; the existing deletion signal handles direct and cascading deletes.
- Removed the trivial `PostListSerializer.get_solved` method; normal model-field serialization preserves the response.
- Reused `UserProfileSerializer` for website schedule/comparison context, respecting privacy and omitting hidden email addresses. Removed a second serialization in the view.
- Added a profile ownership check before all update branches, restricted comment parents to the same solution, and required login for website comment creation.
- Corrected comment success labels that referred to solutions.
- Added `required` and `maxlength="200"` to the HTML post title. Removed metadata for nonexistent `Post.updated_at` instead of adding a column just to satisfy the template.
- Added explicit `PostListItem` objects and `prepare_posts()` so every post collection shares viewer-specific presentation state without mutating `Post` objects. The website renders these objects directly; APIs serialize the same objects through `PostListSerializer`.

The broader changes above remain recommendations; they are not claimed as implemented.

## Validation

- Existing forum suite plus six new regression tests: 84 passed against local PostgreSQL.
- New tests cover cross-user profile updates, web privacy context, cross-solution comment parents, anonymous comment creation, built-in course validation, and one-time solution file cleanup.
- Browser/mobile interactions and production-data inspection were not performed.
