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
    CourseRosterStudentSerializer,
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
    'CourseRosterStudentSerializer',
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
    # Notification serializers
    'NotificationSerializer',
    'VolunteerPinMilestoneSerializer',
    'VolunteerResourceSerializer',
]
