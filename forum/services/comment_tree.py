def attach_comment_trees(comments, solution_ids):
    """Attach query-free reply lists and depths, grouped by solution."""
    comments = list(comments)
    comments_by_id = {comment.id: comment for comment in comments}
    roots_by_solution = {solution_id: [] for solution_id in solution_ids}

    for comment in comments:
        comment.detail_replies = []

    for comment in comments:
        if comment.parent_id is None:
            roots_by_solution[comment.solution_id].append(comment)
            continue

        parent = comments_by_id.get(comment.parent_id)
        if parent is not None:
            parent.detail_replies.append(comment)

    depth_cache = {}

    def calculate_depth(comment, visiting=None):
        if comment.id in depth_cache:
            return depth_cache[comment.id]
        if comment.parent_id is None:
            depth_cache[comment.id] = 0
            return 0

        if visiting is None:
            visiting = set()
        if comment.id in visiting:
            return 5

        parent = comments_by_id.get(comment.parent_id)
        if parent is None:
            depth_cache[comment.id] = 0
            return 0

        visiting.add(comment.id)
        depth = min(calculate_depth(parent, visiting) + 1, 5)
        visiting.remove(comment.id)
        depth_cache[comment.id] = depth
        return depth

    for comment in comments:
        comment.detail_depth = calculate_depth(comment)

    return roots_by_solution
