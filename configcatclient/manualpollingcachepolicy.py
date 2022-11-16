import logging
import sys
from requests import HTTPError

from .configfetcher import FetchResponse
from .readwritelock import ReadWriteLock
from .interfaces import CachePolicy

log = logging.getLogger(sys.modules[__name__].__name__)


class ManualPollingCachePolicy(CachePolicy):
    def __init__(self, config_fetcher, config_cache, cache_key):
        self._config_fetcher = config_fetcher
        self._config_cache = config_cache
        self._cache_key = cache_key
        self._lock = ReadWriteLock()

    def get(self):
        try:
            self._lock.acquire_read()

            configuration = self._config_cache.get(self._cache_key)
            return configuration.get(FetchResponse.CONFIG) if configuration else None
        finally:
            self._lock.release_read()

    def force_refresh(self):
        etag = ''

        try:
            self._lock.acquire_read()
            old_configuration = self._config_cache.get(self._cache_key)
            if bool(old_configuration):
                etag = old_configuration.get(FetchResponse.ETAG, '')
        finally:
            self._lock.release_read()

        try:
            configuration_response = self._config_fetcher.get_configuration_json(etag)
            if configuration_response.is_fetched():
                configuration = configuration_response.json()
                try:
                    self._lock.acquire_write()
                    self._config_cache.set(self._cache_key, configuration)
                finally:
                    self._lock.release_write()

        except HTTPError as e:
            log.error('Double-check your SDK Key at https://app.configcat.com/sdkkey.'
                      ' Received unexpected response: [%s]' % str(e.response))
        except Exception:
            log.exception(sys.exc_info()[0])

    def stop(self):
        pass
