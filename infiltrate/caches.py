"""Contains file_cache and mem_cache beaker caches."""
from beaker.cache import CacheManager

# noinspection PyProtectedMember
from beaker.util import parse_cache_config_options

# todo replace beaker with bolton caches? This is unfriendly and overkill.

ENABLE = False

_file_cache_opts = {
    "cache.type": "file",
    "cache.data_dir": "infiltrate/data/Beaker/tmp/cache/data",
    "cache.lock_dir": "infiltrate/data/Beaker/tmp/cache/lock",
    "enabled": ENABLE,
}
file_cache = CacheManager(**parse_cache_config_options(_file_cache_opts))

_mem_cache_opts = {"cache.type": "memory", "enabled": ENABLE}
mem_cache = CacheManager(**parse_cache_config_options(_mem_cache_opts))


def invalidate():
    """Kill all the caches.
    Used after major updates to depended data, like the card list."""
    from beaker.cache import cache_managers

    for _cache in cache_managers.values():
        _cache.clear()
