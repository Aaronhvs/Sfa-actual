__all__ = ["APIFootballProvider", "FBrefScraper", "UnderstatScraper"]


def __getattr__(name: str):
    if name == "APIFootballProvider":
        from .api_football import APIFootballProvider

        return APIFootballProvider
    if name == "FBrefScraper":
        from .fbref_scraper import FBrefScraper

        return FBrefScraper
    if name == "UnderstatScraper":
        from .understat_scraper import UnderstatScraper

        return UnderstatScraper
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
