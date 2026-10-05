from memory.fallback_store import recall, remember


class MemoryAdapter:
    provider = "SQLite fallback"
    recall = staticmethod(recall)
    remember = staticmethod(remember)
