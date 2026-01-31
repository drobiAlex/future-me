goal: dict | None = None


def get_goal() -> dict | None:
    return goal


def set_goal(next_goal: dict) -> dict:
    global goal
    goal = next_goal
    return goal


def clear_goal() -> dict | None:
    global goal
    current = goal
    goal = None
    return current
