from rest_framework import serializers


class FeedPaginationSerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    limit = serializers.IntegerField(min_value=1, default=8)


def feed_pagination(request):
    pagination = FeedPaginationSerializer(data=request.query_params.dict())
    pagination.is_valid(raise_exception=True)
    return pagination.validated_data['page'], pagination.validated_data['limit']
