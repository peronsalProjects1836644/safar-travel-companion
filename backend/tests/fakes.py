"""Test doubles: an in-memory database with PyMongo's async interface, and a fake OpenAI client."""

from types import SimpleNamespace

import mongomock


class AsyncCursor:
    def __init__(self, cursor):
        self._c = cursor

    def sort(self, *a, **k):
        self._c = self._c.sort(*a, **k)
        return self

    def skip(self, n):
        self._c = self._c.skip(n)
        return self

    def limit(self, n):
        self._c = self._c.limit(n)
        return self

    async def to_list(self, length=None):
        docs = list(self._c)
        return docs if length is None else docs[:length]

    def __aiter__(self):
        self._it = iter(self._c)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


class AsyncCollection:
    def __init__(self, col):
        self._col = col

    async def find_one(self, *a, **k):
        return self._col.find_one(*a, **k)

    def find(self, *a, **k):
        return AsyncCursor(self._col.find(*a, **k))

    async def insert_one(self, *a, **k):
        return self._col.insert_one(*a, **k)

    async def update_one(self, *a, **k):
        return self._col.update_one(*a, **k)

    async def replace_one(self, *a, **k):
        return self._col.replace_one(*a, **k)

    async def delete_one(self, *a, **k):
        return self._col.delete_one(*a, **k)

    async def delete_many(self, *a, **k):
        return self._col.delete_many(*a, **k)

    async def count_documents(self, *a, **k):
        return self._col.count_documents(*a, **k)

    async def find_one_and_update(self, *a, **k):
        return self._col.find_one_and_update(*a, **k)

    async def create_index(self, *a, **k):
        return self._col.create_index(*a, **k)

    async def aggregate(self, pipeline):
        return AsyncCursor(self._col.aggregate(pipeline))


class FakeDB:
    def __init__(self):
        self._db = mongomock.MongoClient(tz_aware=True).smart_tour_test

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return AsyncCollection(self._db[name])

    def __getitem__(self, name):
        return AsyncCollection(self._db[name])

    async def command(self, *a, **k):
        return {"ok": 1}


class FakeOpenAI:
    """Mimics client.chat.completions.create for plain, structured and streaming calls."""

    def __init__(self):
        self.queue: list = []  # strings (JSON text) or Exceptions, consumed in order
        self.stream_chunks: list = ["Hello", " there"]
        self.stream_error: Exception | None = None
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return self._stream()
        item = self.queue.pop(0) if self.queue else "{}"
        if isinstance(item, Exception):
            raise item
        message = SimpleNamespace(content=item, refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    async def _stream(self):
        for text in self.stream_chunks:
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])
        if self.stream_error:
            raise self.stream_error
