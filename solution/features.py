"""Feature assembly kept separate from the I/O so it can be unit-tested."""

from .tracking import control_features


def build(tracking, config):
    return control_features(tracking, config)
