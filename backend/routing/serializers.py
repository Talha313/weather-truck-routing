from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

MAX_LOAD_LBS = 120_000
MAX_DAYS_AHEAD = 7  # forecasts get unreliable beyond this, and the trip must fit in 16 days


class PlaceField(serializers.Field):
    """Either free text or {label, lat, lon} as returned by the geocode endpoint."""

    def to_internal_value(self, data):
        if isinstance(data, str):
            if not data.strip():
                raise serializers.ValidationError("This field may not be blank.")
            return data.strip()
        if isinstance(data, dict):
            try:
                lat, lon = float(data["lat"]), float(data["lon"])
            except (KeyError, TypeError, ValueError):
                if isinstance(data.get("label"), str) and data["label"].strip():
                    return {"label": data["label"].strip()}
                raise serializers.ValidationError("Provide a place name or lat/lon.")
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise serializers.ValidationError("Coordinates out of range.")
            return {"label": str(data.get("label") or ""), "lat": lat, "lon": lon}
        raise serializers.ValidationError("Provide a place name or lat/lon.")

    def to_representation(self, value):
        return value


class TripSerializer(serializers.Serializer):
    origin = PlaceField()
    destination = PlaceField()
    departure_time = serializers.DateTimeField()
    load_weight_lbs = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LBS)

    def validate_departure_time(self, value):
        now = timezone.now()
        if value < now - timedelta(hours=6):
            raise serializers.ValidationError("Departure can't be more than 6 hours in the past.")
        if value > now + timedelta(days=MAX_DAYS_AHEAD):
            raise serializers.ValidationError(f"Departure must be within the next {MAX_DAYS_AHEAD} days.")
        return value


class PlanSerializer(TripSerializer):
    checkpoint_interval_miles = serializers.ChoiceField(choices=[10, 25, 50], default=25)
    include_hos = serializers.BooleanField(default=True)
