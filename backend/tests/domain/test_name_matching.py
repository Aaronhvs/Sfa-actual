from sfa.domain.name_matching import event_matches_player, name_matches


def test_abbreviated_name_matches_by_initial_and_surname_without_provider_id():
    assert name_matches("L. Martinez", "Lisandro Martinez")


def test_provider_id_disambiguates_same_initial_same_surname_teammates():
    lautaro_external_id = 154
    lisandro_external_id = 135

    assert event_matches_player(
        lautaro_external_id,
        "L. Martinez",
        lautaro_external_id,
        "Lautaro Martinez",
    )
    assert not event_matches_player(
        lautaro_external_id,
        "L. Martinez",
        lisandro_external_id,
        "Lisandro Martinez",
    )


def test_falls_back_to_name_matching_when_provider_id_is_missing():
    assert event_matches_player(None, "L. Martinez", 135, "Lisandro Martinez")
