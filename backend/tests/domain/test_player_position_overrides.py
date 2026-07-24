from sfa.domain.player_position_overrides import position_for_context


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
