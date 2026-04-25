# Re-export all models for backward compatibility
from .user import User, UserManager, UserProfile
from .course import Block, Course, CourseAlias, UserCourseExperience, UserCourseHelp
from .post import Post, StandardPost, SavedPost, FollowedPost, PostLike
from .poll import Poll, PollOption, PollVote
from .solution import Solution, SavedSolution, Comment, SolutionUpvote, SolutionDownvote, CommentUpvote
from .schedule import GradebookSnapshot, DailySchedule
from .notification import Notification, UpdateAnnouncement, UserUpdateView
from .volunteer import VolunteerPinMilestone, VolunteerResource
from .file import File

# Import signals to ensure they are registered
from . import signals

__all__ = [
    # User models
    'User',
    'UserManager',
    'UserProfile',
    # Course models
    'Block',
    'Course',
    'CourseAlias',
    'UserCourseExperience',
    'UserCourseHelp',
    # Post models
    'Post',
    'StandardPost',
    'SavedPost',
    'FollowedPost',
    'PostLike',
    # Poll models
    'Poll',
    'PollOption',
    'PollVote',
    # Solution models
    'Solution',
    'SavedSolution',
    'Comment',
    'SolutionUpvote',
    'SolutionDownvote',
    'CommentUpvote',
    # Schedule models
    'GradebookSnapshot',
    'DailySchedule',
    # Notification models
    'Notification',
    'UpdateAnnouncement',
    'UserUpdateView',
    # Volunteer models
    'VolunteerPinMilestone',
    'VolunteerResource',
    # File models
    'File',
]
