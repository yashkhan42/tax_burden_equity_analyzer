"""Codes in, plain English out.

Every string a reader can see is written here. Nothing in this file may
contain a column name, a module name, a file name, an acronym, or a term of
art — if a phrase would need explaining to someone who has never filed a
return alone, it does not belong on screen.

Two layers:

* the value codes the frozen data uses, mapped to how a person would say them
* `phrase_for`, which turns one model feature and its value into a sentence
  fragment the contribution chart can print as-is ("having two children at
  home", "income coming mostly from investments")

Imported by `model_interface` and by the UI; imports neither.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Filing status
# ---------------------------------------------------------------------------
# The project spec documents codes 2 and 3 as separate filers. They are not —
# the IPUMS codebook and the frozen data agree they are joint filers split by
# whether one or both spouses have reached 65 (code 3 is 100% aged 65+, min
# age 65; code 1 is 0% aged 65+, max age 64). The spec's labels would have
# described 5,306 filers as separated when they are married and filing
# together.
FILESTAT_LABELS = {
    1: "married, filing together",
    2: "married, filing together",
    3: "married, filing together",
    4: "head of household",
    5: "filing alone",
}

#: How the reader chooses it, where they have a choice.
FILING_CHOICE_LABELS = {
    4: "as head of household",
    5: "as a single filer",
}

# ---------------------------------------------------------------------------
# Marital status
# ---------------------------------------------------------------------------
MARST_LABELS = {
    1: "married, living together",
    2: "married, living apart",
    3: "separated",
    4: "divorced",
    5: "widowed",
    6: "never married",
}

# ---------------------------------------------------------------------------
# States. Exactly the 51 in the frozen data (50 states and Washington DC).
# ---------------------------------------------------------------------------
STATE_NAMES = {
    1: "Alabama", 2: "Alaska", 4: "Arizona", 5: "Arkansas", 6: "California",
    8: "Colorado", 9: "Connecticut", 10: "Delaware",
    11: "District of Columbia", 12: "Florida", 13: "Georgia", 15: "Hawaii",
    16: "Idaho", 17: "Illinois", 18: "Indiana", 19: "Iowa", 20: "Kansas",
    21: "Kentucky", 22: "Louisiana", 23: "Maine", 24: "Maryland",
    25: "Massachusetts", 26: "Michigan", 27: "Minnesota", 28: "Mississippi",
    29: "Missouri", 30: "Montana", 31: "Nebraska", 32: "Nevada",
    33: "New Hampshire", 34: "New Jersey", 35: "New Mexico", 36: "New York",
    37: "North Carolina", 38: "North Dakota", 39: "Ohio", 40: "Oklahoma",
    41: "Oregon", 42: "Pennsylvania", 44: "Rhode Island",
    45: "South Carolina", 46: "South Dakota", 47: "Tennessee", 48: "Texas",
    49: "Utah", 50: "Vermont", 51: "Virginia", 53: "Washington",
    54: "West Virginia", 55: "Wisconsin", 56: "Wyoming",
}

# ---------------------------------------------------------------------------
# The money questions, as a person would describe them
# ---------------------------------------------------------------------------
INCOME_COMPONENT_LABELS = {
    "incwage": "pay from a job",
    "incbus": "business or self-employment",
    "incint": "interest from savings",
    "incdivid": "dividends from investments",
    "incretir": "a pension or retirement account",
    "incss": "social security",
    "incrent": "rent from property",
}

#: Used mid-sentence: "income coming mostly from {…}".
INCOME_SOURCE_PHRASES = {
    "incwage": "a paycheck",
    "incbus": "a business",
    "incint": "savings interest",
    "incdivid": "investments",
    "incretir": "a pension",
    "incss": "social security",
    "incrent": "rented property",
}

# ---------------------------------------------------------------------------
# What the twin comparison changes
# ---------------------------------------------------------------------------
TWIN_FLIP_LABELS = {
    "filing_status": "how they file",
    "marital_status": "whether they are married",
    "dominant_income_source": "where the money comes from",
    "dependents": "whether they have children",
}

TWIN_FLIP_QUESTIONS = {
    "filing_status": "What if they filed a different way?",
    "marital_status": "What if they were married?",
    "dominant_income_source": "What if the money came from somewhere else?",
    "dependents": "What if there were children at home?",
}

# ---------------------------------------------------------------------------
# The list of things held constant in the twin comparison
# ---------------------------------------------------------------------------
# The comparison only means anything if the reader can see that everything
# except one fact stayed put, so the sameness is printed rather than claimed.
# These are the rows of that list, in the order they are shown.
SHARED_ATTRIBUTE_ORDER = (
    "income",
    "source",
    "age",
    "children",
    "household",
    "marital",
    "filing",
    "state",
)

SHARED_ATTRIBUTE_LABELS = {
    "income": "Income",
    "source": "Where the money comes from",
    "age": "Age",
    "children": "Children at home",
    "household": "People in the household",
    "marital": "Marital status",
    "filing": "How they file",
    "state": "State",
}

#: Which of those rows a given comparison moves, and so must not be listed as
#: held constant. Changing whether someone is married also changes how they
#: file, because in the survey those two always move together — listing filing
#: status as unchanged there would be a plain untruth on screen.
SHARED_ATTRIBUTES_MOVED_BY = {
    "filing_status": ("filing",),
    "marital_status": ("marital", "filing"),
    "dominant_income_source": ("source",),
    "dependents": ("children",),
}

_NUMBER_WORDS = {
    0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}


def in_words(count: int) -> str:
    """Small counts as words, larger ones as digits.

    Written out below eleven because a sentence reads better that way, and left
    as digits above it because "seventeen" in the middle of a line of prose
    slows a reader down more than 17 does.
    """
    return _NUMBER_WORDS.get(int(count), str(int(count)))


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def children_phrase(children: int, under_five: int) -> str:
    """Children at home, as someone would say it out loud."""
    children, under_five = int(children), int(under_five)
    if children == 0:
        return "none"
    phrase = f"{in_words(children)} {_plural(children, 'child', 'children')}"
    if under_five == 0:
        return phrase
    if under_five == children:
        return f"{phrase}, all under five"
    return f"{phrase}, {in_words(under_five)} of them under five"


def household_phrase(people: int) -> str:
    """Household size, as someone would say it out loud."""
    people = int(people)
    return f"{in_words(people)} {_plural(people, 'person', 'people')}"


def age_phrase(age: int) -> str:
    return f"{int(age)} years old"


def phrase_for(feature: str, value: float) -> str:
    """One model feature and its value, as a sentence fragment.

    This is what turns an attribution into something readable: instead of
    "nchild: -4.4" the chart prints "having two children at home". Fragments
    start lower case and carry no punctuation, so the chart can set them
    directly and a sentence can quote them inline.

    Returns an empty string for anything with nothing worth saying, which the
    caller drops from the chart.
    """
    v = float(value)

    if feature == "inctot":
        if v >= 400_000:
            return "earning a very high income"
        if v >= 150_000:
            return "earning a high income"
        if v >= 70_000:
            return "earning an above-average income"
        if v >= 30_000:
            return "earning a middle income"
        return "earning a low income"

    share_sources = {
        "wage_share": "a paycheck",
        "business_share": "running a business",
        "interest_share": "savings interest",
        "dividend_share": "investments",
        "retirement_share": "a pension",
        "socsec_share": "social security",
        "rent_share": "rented property",
    }
    if feature in share_sources:
        source = share_sources[feature]
        if v < 0:
            return f"losing money on {source}"
        if v < 0.15:
            return f"a little income from {source}"
        weight = "mostly" if v >= 0.6 else "partly"
        return f"income coming {weight} from {source}"

    if feature == "filestat":
        code = int(v)
        if code in (1, 2, 3):
            return "filing jointly with a spouse"
        if code == 4:
            return "filing as head of household"
        return "filing alone"

    if feature == "marst":
        return "being married" if int(v) == 1 else ""

    if feature == "nchild":
        n = int(v)
        if n == 0:
            return "having no children at home"
        words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
        return f"having {words.get(n, str(n))} {_plural(n, 'child', 'children')} at home"

    if feature == "nchlt5":
        n = int(v)
        if n == 0:
            return ""
        return f"having {_plural(n, 'a child', 'children')} under five"

    if feature == "famsize":
        n = int(v)
        return "" if n <= 2 else f"supporting a household of {n}"

    if feature == "age":
        return "being 65 or older" if int(v) >= 65 else ""

    if feature == "statefip":
        return ""  # federal rates do not vary by state; saying so would mislead

    return ""
