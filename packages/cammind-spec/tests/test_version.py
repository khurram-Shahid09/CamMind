import cammind_spec


def test_spec_version_starts_at_one() -> None:
    assert cammind_spec.SPEC_VERSION == 1
