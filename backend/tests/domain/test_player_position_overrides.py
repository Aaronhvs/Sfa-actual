from sfa.domain.player_position_overrides import (
    override_name_terms_for_position,
    position_for_context,
)


def test_messi_is_extremo_in_world_cup_context() -> None:
    assert (
        position_for_context(
            "MC",
            player_name="Lionel Messi",
            team_name="Argentina",
            competition_id=350,
        )
        == "EXT"
    )


def test_kimmich_is_lateral_only_for_germany_world_cup_context() -> None:
    assert (
        position_for_context(
            "MC",
            player_name="Joshua Kimmich",
            team_name="Germany",
            competition_id=350,
        )
        == "LAT"
    )

    assert (
        position_for_context(
            "MC",
            player_name="Joshua Kimmich",
            team_name="Bayern Munich",
            competition_id=78,
        )
        == "MC"
    )


def test_olise_is_mco_only_for_france_world_cup_context() -> None:
    assert (
        position_for_context(
            "EXT",
            player_name="Michael Olise",
            team_name="France",
            competition_id=350,
        )
        == "MCO"
    )

    assert (
        position_for_context(
            "EXT",
            player_name="Michael Olise",
            team_name="Bayern München",
            competition_id=78,
        )
        == "EXT"
    )


def test_alex_baena_is_extremo_only_for_spain_world_cup_context() -> None:
    assert (
        position_for_context(
            "MC",
            player_name="Álex Baena",
            team_name="Spain",
            competition_id=350,
        )
        == "EXT"
    )

    assert (
        position_for_context(
            "MC",
            player_name="Álex Baena",
            team_name="Atletico Madrid",
            competition_id=140,
        )
        == "MC"
    )


def test_fermin_lopez_is_mco_in_club_context_with_or_without_accents() -> None:
    for name in ("Fermin Lopez", "Fermín López"):
        assert (
            position_for_context(
                "EXT",
                player_name=name,
                team_name="Barcelona",
                competition_id=140,
            )
            == "MCO"
        )


def test_martin_zubimendi_is_mc_in_club_context_with_or_without_accents() -> None:
    for name in ("Martin Zubimendi", "Martín Zubimendi"):
        assert (
            position_for_context(
                "DC",
                player_name=name,
                team_name="Arsenal",
                competition_id=39,
            )
            == "MC"
        )


def test_corrected_positions_are_available_to_ranking_prefilters() -> None:
    assert "fermin lopez" in override_name_terms_for_position("MCO")
    assert "martin zubimendi" in override_name_terms_for_position("MC")
