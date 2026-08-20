"""Session- and token-authenticated schedule import endpoints."""

import logging
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from django.conf import settings
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from forum.services.schedule_import_service import (
    ALLOWED_SCHEDULE_IMAGE_TYPES,
    MAX_SCHEDULE_IMAGE_BYTES,
    MAX_SCHEDULE_TEXT_LENGTH,
    ScheduleImportConfigurationError,
    ScheduleImportProviderError,
    ScheduleImportValidationError,
    build_schedule_preview,
    extract_schedule_with_gemini,
    replace_user_schedule,
)


logger = logging.getLogger(__name__)


class ScheduleImportRateThrottle(UserRateThrottle):
    scope = "schedule_import"

    def get_rate(self):
        return getattr(settings, "SCHEDULE_IMPORT_RATE", "4/hour")


def _validated_source(request):
    text = request.data.get("text")
    image = request.FILES.get("image")
    has_text = isinstance(text, str) and bool(text.strip())

    if has_text == bool(image):
        raise ScheduleImportValidationError("Provide exactly one screenshot or pasted schedule text.")

    if has_text:
        text = text.strip()
        if len(text) > MAX_SCHEDULE_TEXT_LENGTH:
            raise ScheduleImportValidationError("Schedule text must be 20,000 characters or fewer.")
        return {"text": text}

    if image.size > MAX_SCHEDULE_IMAGE_BYTES:
        raise ScheduleImportValidationError("The screenshot must be 10 MB or smaller.")
    if image.content_type not in ALLOWED_SCHEDULE_IMAGE_TYPES:
        raise ScheduleImportValidationError("Use a PNG, JPEG, or WebP screenshot.")

    image_bytes = image.read()
    try:
        with Image.open(BytesIO(image_bytes)) as opened_image:
            opened_image.verify()
            verified_mime_type = Image.MIME.get(opened_image.format)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ScheduleImportValidationError("The uploaded screenshot is not a valid image.") from exc
    if verified_mime_type not in ALLOWED_SCHEDULE_IMAGE_TYPES:
        raise ScheduleImportValidationError("Use a PNG, JPEG, or WebP screenshot.")

    return {"image_bytes": image_bytes, "mime_type": verified_mime_type}


@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
@throttle_classes([ScheduleImportRateThrottle])
def preview_schedule_import(request):
    try:
        source = _validated_source(request)
        extracted = extract_schedule_with_gemini(**source)
        preview = build_schedule_preview(extracted)
        return Response(preview, status=status.HTTP_200_OK)
    except ScheduleImportValidationError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except ScheduleImportConfigurationError as exc:
        logger.error("Schedule import configuration error: %s", exc)
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ScheduleImportProviderError as exc:
        logger.exception("Gemini schedule extraction failed")
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception:
        logger.exception("Unexpected schedule import preview failure")
        return Response(
            {"error": "The schedule could not be processed."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def apply_schedule_import(request):
    try:
        schedule = replace_user_schedule(
            request.user.userprofile,
            request.data.get("assignments"),
        )
        return Response(
            {"message": "Schedule imported successfully.", "schedule": schedule},
            status=status.HTTP_200_OK,
        )
    except ScheduleImportValidationError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except Exception:
        logger.exception("Unexpected schedule import apply failure")
        return Response(
            {"error": "The schedule could not be saved."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
