def attach_poll_data_to_posts(posts, serialized_posts):
    """Attach serialized poll payloads to post objects for template rendering."""
    poll_data_by_post_id = {
        serialized_post.get('id'): serialized_post.get('poll_data')
        for serialized_post in serialized_posts
    }

    for post in posts:
        post.poll_data = poll_data_by_post_id.get(post.id)

    return posts
