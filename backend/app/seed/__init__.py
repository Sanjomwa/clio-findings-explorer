class SeedError(Exception):
    """A seed precondition failed. Raised before, or rolled back from, any database change."""
