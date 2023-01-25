from dataclasses import dataclass, field
import inspect
import logging


@dataclass
class Track:
    name: str = None
    height: float = None
    speed: float = None
    length: float = None
    inversions: int = None
    drop: float = None

    def __setattr__(self, __name, __value) -> None:
        if __value is not None:
            attr_type = inspect.get_annotations(self.__class__).get(__name)
            try:
                __value = attr_type(__value)
            except Exception:
                logging.exception()
        super().__setattr__(__name, __value)


@dataclass
class Coaster:
    _id: str = None
    name: str = None
    manufacturer: str = None
    park: str = None
    country: str = None
    opening_date: str = None
    closing_date: str = None
    sbno_date: str = None
    tracks: list[Track] = field(default_factory=list)
    image_url: str = None
