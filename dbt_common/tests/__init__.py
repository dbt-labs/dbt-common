_TEST_CACHING_ENABLED: bool = False


def test_caching_enabled() -> bool:
    return _TEST_CACHING_ENABLED


def enable_test_caching() -> None:
    global _TEST_CACHING_ENABLED
    if _TEST_CACHING_ENABLED is False:
        print("ENABLING CACHES")
    _TEST_CACHING_ENABLED = True
