"""Investor filter rules (Strategy pattern over a Template-Method base)."""

from investor_lens.domain.rules.base import CheckCollector, FilterRule, combine_checks
from investor_lens.domain.rules.buffett import BuffettRule
from investor_lens.domain.rules.dalio import DalioRule
from investor_lens.domain.rules.graham import GrahamRule
from investor_lens.domain.rules.greenblatt import GreenblattRule
from investor_lens.domain.rules.lynch import LynchRule
from investor_lens.domain.rules.marks import MarksRule
from investor_lens.domain.rules.news import NewsRule
from investor_lens.domain.rules.piotroski import PiotroskiRule

__all__ = [
    "BuffettRule",
    "CheckCollector",
    "DalioRule",
    "FilterRule",
    "GrahamRule",
    "GreenblattRule",
    "LynchRule",
    "MarksRule",
    "NewsRule",
    "PiotroskiRule",
    "combine_checks",
]
