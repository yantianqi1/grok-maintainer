from __future__ import annotations

from dataclasses import dataclass


FIXED_GENERATION_STEPS = 8
UPSTREAM_IMAGE_MODEL = "ZImageTurbo_INT8"


@dataclass(frozen=True)
class ImageModelVariant:
    public_name: str
    width: int
    height: int
    upstream_name: str = UPSTREAM_IMAGE_MODEL


IMAGE_MODEL_VARIANTS = (
    ImageModelVariant("z-image-1024x1024", 1024, 1024),
    ImageModelVariant("z-image-832x1216", 832, 1216),
    ImageModelVariant("z-image-1216x832", 1216, 832),
    ImageModelVariant("z-image-688x1216", 688, 1216),
    ImageModelVariant("z-image-1216x688", 1216, 688),
)
IMAGE_MODEL_VARIANTS_BY_NAME = {item.public_name: item for item in IMAGE_MODEL_VARIANTS}


def list_public_model_ids() -> tuple[str, ...]:
    return tuple(item.public_name for item in IMAGE_MODEL_VARIANTS)


def find_image_model_variant(model_name: str) -> ImageModelVariant | None:
    return IMAGE_MODEL_VARIANTS_BY_NAME.get(model_name.strip())
