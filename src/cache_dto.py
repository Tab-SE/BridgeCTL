import os
import yaml
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Optional
from src.enums import SCRATCH_DIR
from src.lib.general_helper import StringUtils


@dataclass
class BaseDto:

    last_updated: Optional[datetime] = None

    def is_valid(self) -> bool:
        return bool(self.last_updated)

    def is_expired(self, max_age_minutes: float = 60.0) -> bool:
        if not self.is_valid():
            return True
        age = (datetime.utcnow() - self.last_updated).total_seconds() / 60.0
        return age > max_age_minutes

    @classmethod
    def get_blank(cls) -> 'BaseDto':
        return cls(last_updated=None)


@dataclass
class EcrImageListDto(BaseDto):
    tags: List[str] = field(default_factory=list)

    @classmethod
    def get_blank(cls) -> 'EcrImageListDto':
        return cls(tags=[], last_updated=None)


class CacheManagerEcrImageList:
    _cache_path = SCRATCH_DIR / "ecr_image_tags.yaml"

    @classmethod
    def load(cls) -> EcrImageListDto:
        if not os.path.exists(cls._cache_path):
            return EcrImageListDto.get_blank()
            
        with open(cls._cache_path, 'r') as f:
            data = yaml.safe_load(f)
            
        return EcrImageListDto(
            tags=data.get('tags', []),
            last_updated=data.get('last_updated')
        )

    @classmethod
    def save(cls, dto: EcrImageListDto) -> None:
        if not SCRATCH_DIR.exists():
            SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

        dto.last_updated = StringUtils.now_utc()
        with open(cls._cache_path, 'w') as outfile:
            yaml.dump(
                asdict(dto),
                outfile, 
                default_flow_style=False, 
                sort_keys=False
            )

