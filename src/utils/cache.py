import hashlib
import json
import os
import threading
from typing import Any, Callable, Optional


class DiskCache:
    """简单文件缓存：key -> json 序列化的值。

    - 线程安全（进程内）
    - 命中即返回，未命中由 loader 生成并回写
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._lock = threading.Lock()

    def _key_to_path(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self.base_dir, f"{digest}.json")

    def get(self, key: str) -> Optional[Any]:
        path = self._key_to_path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def set(self, key: str, value: Any) -> None:
        path = self._key_to_path(key)
        tmp_path = f"{path}.tmp"
        data = value
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            # best-effort
            pass

    def get_or_set(self, key: str, loader: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        with self._lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            value = loader()
            self.set(key, value)
            return value


