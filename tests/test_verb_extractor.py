from analyzers import verb_extractor as ve


def test_is_adverb_detects_suffix():
    assert ve._is_adverb("strategically") is True
    assert ve._is_adverb("design") is False


def test_extract_verb_prefers_multiword_phrase():
    text = "Students will be familiar with legal frameworks in software projects."
    assert ve.extract_verb(text) == "be familiar with"


def test_extract_verb_extracts_pattern_match():
    text = "Students will design scalable services."
    assert ve.extract_verb(text) == "design"


def test_extract_verb_falls_back_to_first_non_stopword():
    text = "Innovate solutions for clients in teams."
    assert ve.extract_verb(text) == "innovate"
