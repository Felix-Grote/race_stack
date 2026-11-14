"""The reference car, shared by the route and optimizer tests."""
from global_planner.car import Car
import pytest
from tracks import NUC5


@pytest.fixture(scope='session')
def car() -> Car:
    return Car.load(NUC5, margin_m=0.05)
