from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from forum.services.analytics_service import CLIENT_EVENTS, FEATURE_SCREENS, SCREENS, record_event

class AnalyticsThrottle(UserRateThrottle):
    scope = 'analytics'
    rate = '120/min'


class EventSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    platform = serializers.ChoiceField(choices=['web', 'mobile'])
    event_type = serializers.ChoiceField(choices=sorted(CLIENT_EVENTS))
    screen = serializers.ChoiceField(choices=sorted(SCREENS))

    def validate(self, attrs):
        if set(self.initial_data) != set(self.fields):
            raise serializers.ValidationError('Only id, platform, event_type and screen are accepted.')
        allowed = FEATURE_SCREENS.get(attrs['event_type'])
        if allowed and attrs['screen'] not in allowed:
            raise serializers.ValidationError('Event is not valid for this screen.')
        return attrs


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalyticsThrottle])
def analytics_events(request):
    serializer = EventSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    recorded = record_event(request.user, data['event_type'], data['screen'],
                            platform=data['platform'], event_id=data['id'])
    return Response({'recorded': recorded}, status=200 if recorded else 503)
