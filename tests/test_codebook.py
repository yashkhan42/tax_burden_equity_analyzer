"""Reader-facing language must remain true to the supplied value."""

from codebook import phrase_for


def test_zero_income_share_is_never_described_as_a_little_income() -> None:
    assert phrase_for("wage_share", 0) == "having no income from a paycheck"
    assert phrase_for("socsec_share", 0) == "having no social security income"


def test_negative_income_share_is_described_as_a_loss() -> None:
    assert phrase_for("business_share", -0.2) == "losing money in a business"
    assert phrase_for("rent_share", -0.1) == "losing money on rented property"
