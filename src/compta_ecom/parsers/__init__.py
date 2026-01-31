"""Parsers CSV pour les différents canaux."""

from compta_ecom.parsers.base import BaseParser
from compta_ecom.parsers.shopify import ShopifyParser

__all__ = ["BaseParser", "ShopifyParser"]
