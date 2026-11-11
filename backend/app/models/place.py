from pydantic import BaseModel, Field

from app.models.common import APIModel, Category, Lat, Lng, Season, Url


class PlaceBase(APIModel):
    name: str = Field(min_length=1, max_length=120)
    destination: str = Field(min_length=1, max_length=80)
    region: str = Field(min_length=1, max_length=80)
    category: Category
    tags: list[str] = Field(default_factory=list, max_length=12)
    description: str = Field(default="", max_length=600)
    lat: Lat
    lng: Lng
    # 0 = free, 1 = low, 2 = medium, 3 = high. An estimate, editable by admins.
    price_level: int = Field(default=0, ge=0, le=3)
    avg_visit_minutes: int = Field(default=60, ge=15, le=600)
    indoor: bool = False
    best_season: list[Season] = Field(default_factory=list)
    image_url: Url | None = None
    source_url: Url | None = None
    image_credit: str | None = Field(default=None, max_length=200)
    advisory: str | None = Field(default=None, max_length=200)
    verified: bool = False


class PlaceCreate(PlaceBase):
    id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,100}$")


class PlaceOut(BaseModel):
    id: str
    name: str
    destination: str
    region: str
    category: str
    tags: list[str] = []
    description: str = ""
    lat: float
    lng: float
    price_level: int = 0
    avg_visit_minutes: int = 60
    indoor: bool = False
    best_season: list[str] = []
    image_url: str | None = None
    source_url: str | None = None
    image_credit: str | None = None
    advisory: str | None = None
    verified: bool = False
    distance_km: float | None = None


class PlaceList(BaseModel):
    items: list[PlaceOut]
    total: int
    limit: int
    offset: int


class DestinationOut(BaseModel):
    name: str
    region: str
    count: int
    lat: float
    lng: float
    image_url: str | None = None
