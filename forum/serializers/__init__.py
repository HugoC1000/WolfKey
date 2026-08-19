# Re-export all serializers for backward compatibility
from .user import (
    CourseSerializer,
    UserProfileSerializer,
    UserSummarySerializer,
    UserSerializer,
    PrivateUserSerializer,
    PrivateUserProfileSerializer,
    AnonymousAuthorSerializer,
    FeedUserSerializer,
    FeedUserProfileSerializer,
    UserScheduleSerializer,
)
from .post import (
    PostListSerializer,
    PostDetailSerializer,
)
from .solution import (
    CommentSerializer,
    SolutionSerializer,
)
from .poll import (
    PollOptionSerializer,
    PollVoterSerializer,
    PollSerializer,
    serialize_poll_display_data,
)
from .petition import PetitionSerializer, serialize_petition_display_data
from .notification import NotificationSerializer
from .volunteer import (
    VolunteerPinMilestoneSerializer,
    VolunteerResourceSerializer,
)
from forum.services.poll_display_service import attach_poll_data_to_posts

__all__ = [
    # User serializers
    'CourseSerializer',
    'UserProfileSerializer',
    'UserSummarySerializer',
    'UserSerializer',
    'PrivateUserSerializer',
    'PrivateUserProfileSerializer',
    'AnonymousAuthorSerializer',
    'FeedUserSerializer',
    'FeedUserProfileSerializer',
    'UserScheduleSerializer',
    # Post serializers
    'PostListSerializer',
    'PostDetailSerializer',
    # Solution serializers
    'CommentSerializer',
    'SolutionSerializer',
    # Poll serializers
    'PollOptionSerializer',
    'PollVoterSerializer',
    'PollSerializer',
    'serialize_poll_display_data',
    'attach_poll_data_to_posts',
    'PetitionSerializer',
    'serialize_petition_display_data',
    # Notification serializers
    'NotificationSerializer',
    'VolunteerPinMilestoneSerializer',
    'VolunteerResourceSerializer',
]
