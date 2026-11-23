# Spec 17 — Check in from a post

## Why

People can already share a post from a bar and review that bar. This feature connects
those actions without changing how a post appears in the feed.

Builds on specs 03 (reviews), 05 (profiles), 06 (posts) and 16 (rating from a post).
This spec replaces spec 16's optional single vibe slider with the full review fields;
atmosphere is the vibe score.

## What

### 1. Profile: Been to

- Keep the existing **Bars** tab and its followed-venue list unchanged.
- Add a separate **Been to** tab beside it. It lists venues where the profile owner has
  submitted a review or created a post tagged with that venue.
- Each venue appears once, ordered by the most recent review or venue-tagged post.
  Typed **Other** locations do not count.
- Venue rows open the existing venue detail page.

### 2. Rate from a post

- When a customer chooses a listed venue in the post form, show an optional **Rate this
  bar** section with the venue review fields: Atmosphere, Value for money and Quality
  (each 1–5), optional Super Bock price (€0.50–€10.00), and optional comment (up to 500
  characters).
- Atmosphere is the vibe rating. Do not add a separate vibe slider or a post vibe
  field. Do not change post cards, feed ordering, or other post behavior.
- A rating is submitted through the existing `logic.submit_review` rules. A second post
  rating for the same venue updates the user's existing review.
- If the customer leaves the rating unchecked, save only the post.
- Validate the rating before saving the post. If any rating field is invalid, show the
  review error and save neither the post nor a review.
- Businesses and posts using **Other** do not show a rating section and cannot submit
  a rating through the post flow.

## Out of scope

- Changing the appearance or behavior of feed posts and post cards.
- Rating from comments or from an **Other** location.
- Adding a rating badge or storing a separate rating on a post.
- Changing the followed-venue **Bars** tab.

## Done when

- [ ] The profile **Been to** tab shows reviewed and venue-posted bars once each, newest
      first; **Other** locations are excluded.
- [ ] The existing **Bars** tab still shows followed venues.
- [ ] A complete post rating creates or updates the existing review, including all
      review fields.
- [ ] Invalid scores or prices save neither a post nor a review.
- [ ] An unchecked rating saves the post without a review.
- [ ] Businesses and **Other** locations cannot rate from the post form.
- [ ] Existing feed and post tests still pass; feed post appearance and behavior do not
      change.
- [ ] `uv run pytest` passes.
