from app.services import matching_service as m


class TestCleanTitleAndGuess:
    def test_strips_official_video_parens(self):
        cleaned = m.clean_title("The Weeknd - Blinding Lights (Official Video)")
        assert cleaned == "The Weeknd - Blinding Lights"

    def test_strips_official_video_brackets(self):
        cleaned = m.clean_title("Daft Punk - Get Lucky [Official Video]")
        assert cleaned == "Daft Punk - Get Lucky"

    def test_strips_bare_remastered(self):
        cleaned = m.clean_title("Queen - Bohemian Rhapsody Remastered")
        assert cleaned == "Queen - Bohemian Rhapsody"

    def test_strips_bare_lyrics(self):
        cleaned = m.clean_title("Imagine Dragons - Believer Lyrics")
        assert cleaned == "Imagine Dragons - Believer"

    def test_guess_artist_track_splits_on_dash(self):
        guess = m.guess_artist_track("The Weeknd - Blinding Lights")
        assert guess == {"artist": "The Weeknd", "track": "Blinding Lights"}

    def test_guess_artist_track_no_separator_is_ambiguous(self):
        # No " - " style separator: we can't tell artist from track, so the
        # whole cleaned string becomes the track guess (spec §15: ambiguous
        # cases shouldn't crash or invent an artist).
        guess = m.guess_artist_track("Bohemian Rhapsody")
        assert guess == {"artist": None, "track": "Bohemian Rhapsody"}

    def test_extra_whitespace_is_collapsed(self):
        cleaned = m.clean_title("Queen  -   Bohemian   Rhapsody (Official Video)")
        assert cleaned == "Queen - Bohemian Rhapsody"


class TestBuildSearchQueries:
    def test_includes_field_scoped_and_plain_queries(self):
        queries = m.build_search_queries("The Weeknd - Blinding Lights (Official Video)")
        assert "track:Blinding Lights artist:The Weeknd" in queries
        assert "The Weeknd Blinding Lights" in queries

    def test_no_duplicate_queries(self):
        queries = m.build_search_queries("Bohemian Rhapsody")
        assert len(queries) == len(set(queries))


class TestDetectVersion:
    def test_detects_live(self):
        assert m.detect_version("Queen - Bohemian Rhapsody (Live at Wembley)") == "live"

    def test_detects_remastered(self):
        assert m.detect_version("Queen - Bohemian Rhapsody Remastered") == "remastered"

    def test_no_version_tag_returns_none(self):
        assert m.detect_version("The Weeknd - Blinding Lights") is None


class TestConfidenceLevel:
    def test_high(self):
        assert m.confidence_level(95) == "alta"

    def test_medium(self):
        assert m.confidence_level(75) == "media"

    def test_low(self):
        assert m.confidence_level(40) == "baja"

    def test_boundaries_are_inclusive(self):
        assert m.confidence_level(m.CONFIDENCE_HIGH) == "alta"
        assert m.confidence_level(m.CONFIDENCE_MEDIUM) == "media"


class TestScoreCandidate:
    def test_exact_match_scores_higher_than_unrelated_song(self):
        video_title = "The Weeknd - Blinding Lights (Official Video)"
        exact = m.score_candidate(
            video_title=video_title,
            video_duration_ms=200_040,
            candidate_name="Blinding Lights",
            candidate_artists="The Weeknd",
            candidate_album="After Hours",
            candidate_duration_ms=200_040,
        )
        unrelated = m.score_candidate(
            video_title=video_title,
            video_duration_ms=200_040,
            candidate_name="Save Your Tears",
            candidate_artists="The Weeknd",
            candidate_album="After Hours",
            candidate_duration_ms=215_000,
        )
        assert exact > unrelated
        assert m.confidence_level(exact) == "alta"

    def test_live_video_scores_live_candidate_over_studio_candidate(self):
        video_title = "Queen - Bohemian Rhapsody (Live at Wembley)"
        live_candidate = m.score_candidate(
            video_title=video_title,
            video_duration_ms=None,
            candidate_name="Bohemian Rhapsody - Live at Wembley Stadium",
            candidate_artists="Queen",
            candidate_album="Live Magic",
            candidate_duration_ms=None,
        )
        studio_candidate = m.score_candidate(
            video_title=video_title,
            video_duration_ms=None,
            candidate_name="Bohemian Rhapsody",
            candidate_artists="Queen",
            candidate_album="A Night at the Opera",
            candidate_duration_ms=None,
        )
        assert live_candidate > studio_candidate
