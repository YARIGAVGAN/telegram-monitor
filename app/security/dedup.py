from cachetools import LRUCache

class Deduplicator:
    def __init__(self, maxsize=50000):
        self.cache = LRUCache(maxsize=maxsize)

    def mark_seen(self, chat_id, message_id):
        key = f"{chat_id}_{message_id}"
        self.cache[key] = True

    def is_seen(self, chat_id, message_id):
        key = f"{chat_id}_{message_id}"
        return key in self.cache