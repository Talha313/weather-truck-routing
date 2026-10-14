import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import PlanSerializer, TripSerializer
from .services import geocoding
from .services.heatmap import build_heatmap
from .services.http import UpstreamError
from .services.planner import plan_trip
from .services.routing import get_routes

log = logging.getLogger(__name__)


def _error(message: str, code: int) -> Response:
    return Response({"error": message}, status=code)


def _resolve_places(data: dict) -> tuple[dict, dict]:
    origin = geocoding.resolve(data["origin"])
    destination = geocoding.resolve(data["destination"])
    if abs(origin["lat"] - destination["lat"]) < 1e-3 and abs(origin["lon"] - destination["lon"]) < 1e-3:
        raise LookupError("Origin and destination are the same place.")
    return origin, destination


def _handle(fn):
    """Map service exceptions to clean JSON errors."""
    try:
        return fn()
    except LookupError as exc:
        return _error(str(exc), status.HTTP_400_BAD_REQUEST)
    except UpstreamError as exc:
        log.warning("Upstream failure: %s", exc)
        return _error(str(exc), status.HTTP_502_BAD_GATEWAY)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def geocode(request):
    return _handle(lambda: Response({"results": geocoding.search(request.query_params.get("q", ""))}))


@api_view(["POST"])
def plan(request):
    serializer = PlanSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    def run():
        origin, destination = _resolve_places(data)
        return Response(
            plan_trip(
                origin,
                destination,
                data["departure_time"],
                data["load_weight_lbs"],
                int(data["checkpoint_interval_miles"]),
                data["include_hos"],
            )
        )

    return _handle(run)


@api_view(["POST"])
def heatmap(request):
    serializer = TripSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    def run():
        origin, destination = _resolve_places(data)
        # Same arguments as /plan, so the routes come straight from the cache.
        routes = get_routes((origin["lat"], origin["lon"]), (destination["lat"], destination["lon"]), data["load_weight_lbs"])
        return Response(build_heatmap(routes, data["departure_time"], data["load_weight_lbs"]))

    return _handle(run)
