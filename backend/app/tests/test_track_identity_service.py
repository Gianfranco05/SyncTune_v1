from app.services import track_identity_service as ti


def _track(id_: str, name: str, artists: str) -> dict:
    return {"id": id_, "uri": f"spotify:track:{id_}", "name": name, "artists": artists}


class TestIsSameTrack:
    def test_same_id_is_always_the_same_track(self):
        a = _track("1", "Blinding Lights", "The Weeknd")
        b = _track("1", "Completely different title", "Someone else")
        assert ti.is_same_track(a, b) is True

    def test_matching_title_and_artist_is_the_same_track(self):
        a = _track("1", "Blinding Lights", "The Weeknd")
        b = _track("2", "Blinding Lights", "The Weeknd")
        assert ti.is_same_track(a, b) is True

    def test_different_song_is_not_the_same_track(self):
        a = _track("1", "Blinding Lights", "The Weeknd")
        b = _track("2", "Save Your Tears", "The Weeknd")
        assert ti.is_same_track(a, b) is False

    def test_different_artist_is_not_the_same_track(self):
        a = _track("1", "Perfect", "Ed Sheeran")
        b = _track("2", "Perfect", "Simple Plan")
        assert ti.is_same_track(a, b) is False


class TestCompareTrackLists:
    def test_splits_common_only_a_only_b(self):
        common_a = _track("1", "Blinding Lights", "The Weeknd")
        common_b = _track("1b", "Blinding Lights", "The Weeknd")
        only_in_a = _track("2", "Starboy", "The Weeknd")
        only_in_b = _track("3", "Save Your Tears", "The Weeknd")

        result = ti.compare_track_lists([common_a, only_in_a], [common_b, only_in_b])

        assert result["common"] == [common_a]
        assert result["only_a"] == [only_in_a]
        assert result["only_b"] == [only_in_b]

    def test_does_not_match_the_same_b_track_twice(self):
        # Two identical songs in A must not both claim the single copy in B.
        a1 = _track("1", "Blinding Lights", "The Weeknd")
        a2 = _track("2", "Blinding Lights", "The Weeknd")
        b1 = _track("3", "Blinding Lights", "The Weeknd")

        result = ti.compare_track_lists([a1, a2], [b1])

        assert len(result["common"]) == 1
        assert len(result["only_a"]) == 1
        assert result["only_b"] == []


class TestFindDuplicates:
    def test_groups_repeated_tracks(self):
        a = _track("1", "Blinding Lights", "The Weeknd")
        a_dup = _track("2", "Blinding Lights", "The Weeknd")
        unique = _track("3", "Starboy", "The Weeknd")

        groups = ti.find_duplicates([a, unique, a_dup])

        assert len(groups) == 1
        assert {t["id"] for t in groups[0]} == {"1", "2"}

    def test_no_duplicates_returns_empty(self):
        a = _track("1", "Blinding Lights", "The Weeknd")
        b = _track("2", "Starboy", "The Weeknd")
        assert ti.find_duplicates([a, b]) == []
