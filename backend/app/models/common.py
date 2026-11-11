from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Category = Literal[
    "heritage", "nature", "mountains", "lakes", "beaches", "parks",
    "museums", "religious", "food", "shopping", "adventure", "family",
]
CATEGORIES: tuple[str, ...] = (
    "heritage", "nature", "mountains", "lakes", "beaches", "parks",
    "museums", "religious", "food", "shopping", "adventure", "family",
)
BudgetLevel = Literal["budget", "mid", "premium"]
Pace = Literal["relaxed", "balanced", "packed"]
Season = Literal["winter", "spring", "summer", "autumn"]

HHMM = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
Url = Annotated[str, StringConstraints(pattern=r"^https?://\S+$", max_length=500)]
Lat = Annotated[float, Field(ge=-90, le=90)]
Lng = Annotated[float, Field(ge=-180, le=180)]


class APIModel(BaseModel):
    """Base for request bodies: unknown fields are rejected so typos are caught early."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
