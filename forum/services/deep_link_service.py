"""
Deep linking support for WolfKey notifications
"""
import logging
from typing import Dict, Optional
from django.urls import reverse
from django.conf import settings

logger = logging.getLogger(__name__)

class WolfKeyDeepLink:
    """Helper class for creating deep link data for WolfKey notifications"""
    
    @staticmethod
    def post_detail(post_id: int, comment_id: Optional[int] = None, solution_id: Optional[int] = None) -> Dict:
        """Create deep link data for post detail screen"""
        data = {
            'type': 'post_detail',
            'screen': 'PostDetail',
            'params': {'postId': str(post_id)},
            'post_id': str(post_id),
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/post/{post_id}/"
        }
        
        if comment_id:
            data['comment_id'] = str(comment_id)
            data['params']['commentId'] = str(comment_id)
            data['web_url'] += f"#comment-{comment_id}"
            
        if solution_id:
            data['solution_id'] = str(solution_id)
            data['params']['solutionId'] = str(solution_id)
            data['web_url'] += f"#solution-{solution_id}"
            
        return data
    
    @staticmethod
    def solution_detail(post_id: int, solution_id: int, comment_id: Optional[int] = None) -> Dict:
        """Create deep link data for solution detail within a post"""
        data = {
            'type': 'solution_detail',
            'screen': 'PostDetail',
            'params': {
                'postId': str(post_id),
                'solutionId': str(solution_id)
            },
            'post_id': str(post_id),
            'solution_id': str(solution_id),
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/post/{post_id}/#solution-{solution_id}"
        }
        
        if comment_id:
            data['comment_id'] = str(comment_id)
            data['params']['commentId'] = str(comment_id)
            data['web_url'] += f"-comment-{comment_id}"
            
        return data
    
    @staticmethod
    def profile(username: str, user_id: Optional[int] = None) -> Dict:
        """Create deep link data for user profile screen"""
        data = {
            'type': 'profile',
            'screen': 'Profile',
            'params': {'username': username},
            'username': username,
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/profile/{username}/"
        }
        
        if user_id:
            data['user_id'] = str(user_id)
            data['params']['userId'] = str(user_id)
            
        return data
    
    @staticmethod
    def schedule(date: Optional[str] = None, block: Optional[str] = None) -> Dict:
        """Create deep link data for schedule screen"""
        data = {
            'type': 'schedule',
            'screen': 'Schedule',
            'params': {},
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/schedule/"
        }
        
        if date:
            data['params']['date'] = date
            data['date'] = date
            data['web_url'] += f"?date={date}"
            
        if block:
            data['params']['block'] = block
            data['block'] = block
            separator = '&' if '?' in data['web_url'] else '?'
            data['web_url'] += f"{separator}block={block}"
            
        return data
    
    @staticmethod
    def course_posts(course_id: int, course_name: Optional[str] = None) -> Dict:
        """Create deep link data for course-specific posts"""
        data = {
            'type': 'course_posts',
            'screen': 'CoursePosts',
            'params': {'courseId': str(course_id)},
            'course_id': str(course_id),
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/course/{course_id}/posts/"
        }
        
        if course_name:
            data['course_name'] = course_name
            data['params']['courseName'] = course_name
            
        return data
    
    @staticmethod
    def grade_update() -> Dict:
        """Create deep link data for grade update notifications - links to notifications screen"""
        return {
            'type': 'grade_update',
            'screen': 'Notifications',
            'params': {},
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/notifications/"
        }
    
    @staticmethod
    def followed_posts() -> Dict:
        """Create deep link data for followed posts screen"""
        return {
            'type': 'followed_posts',
            'screen': 'FollowedPosts',
            'params': {},
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/followed-posts/"
        }
    
    @staticmethod
    def notifications() -> Dict:
        """Create deep link data for notifications screen"""
        return {
            'type': 'notifications',
            'screen': 'Notifications',
            'params': {},
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/notifications/"
        }
    
    @staticmethod
    def course_comparer(users: Optional[list] = None) -> Dict:
        """Create deep link data for course comparer screen"""
        data = {
            'type': 'course_comparer',
            'screen': 'CourseComparer',
            'params': {},
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/match/"
        }
        
        if users:
            data['params']['preselectedUsers'] = users
            data['preselected_users'] = users
            
        return data
    
    @staticmethod
    def my_posts() -> Dict:
        """Create deep link data for user's own posts"""
        return {
            'type': 'my_posts',
            'screen': 'MyPosts',
            'params': {},
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/my-posts/"
        }
    
    @staticmethod
    def for_you_feed() -> Dict:
        """Create deep link data for personalized feed"""
        return {
            'type': 'for_you',
            'screen': 'ForYou',
            'params': {},
            'web_url': f"{getattr(settings, 'SITE_URL', '')}/for-you/"
        }

def create_notification_deep_link(notification_type: str, **kwargs) -> Dict:
    """
    Create appropriate deep link data based on notification type and context
    
    Args:
        notification_type: Type of notification ('post', 'solution', 'comment', 'reply', etc.)
        **kwargs: Context data (post_id, solution_id, comment_id, user, etc.)
    
    Returns:
        Dict with deep link data for mobile app navigation
    """
    try:
        post_id = kwargs.get('post_id')
        solution_id = kwargs.get('solution_id')
        comment_id = kwargs.get('comment_id')
        user = kwargs.get('user')
        post = kwargs.get('post')
        solution = kwargs.get('solution')
        comment = kwargs.get('comment')
        
        # Extract IDs from model instances if provided
        if post and not post_id:
            post_id = post.id
        if solution and not solution_id:
            solution_id = solution.id
        if comment and not comment_id:
            comment_id = comment.id
            
        if notification_type == 'post':
            # New post in course - link to post detail
            return WolfKeyDeepLink.post_detail(post_id=post_id)
            
        elif notification_type == 'solution':
            # New solution to post - link to solution within post
            return WolfKeyDeepLink.solution_detail(
                post_id=post_id,
                solution_id=solution_id
            )
            
        elif notification_type in ['comment', 'reply']:
            # Comment on solution or reply to comment - link to comment within post
            if solution_id:
                return WolfKeyDeepLink.solution_detail(
                    post_id=post_id,
                    solution_id=solution_id,
                    comment_id=comment_id
                )
            else:
                return WolfKeyDeepLink.post_detail(
                    post_id=post_id,
                    comment_id=comment_id
                )
                
        elif notification_type == 'follow':
            return WolfKeyDeepLink.post_detail(post_id=post_id)
            
        elif notification_type == 'like':
            return WolfKeyDeepLink.post_detail(post_id=post_id)
                
        elif notification_type == 'course_update':
            # Course-related update - link to course posts
            course_id = kwargs.get('course_id')
            course_name = kwargs.get('course_name')
            if course_id:
                return WolfKeyDeepLink.course_posts(
                    course_id=course_id,
                    course_name=course_name
                )
            else:
                return WolfKeyDeepLink.for_you_feed()
                
        elif notification_type == 'schedule_update':
            # Schedule update - link to schedule
            date = kwargs.get('date')
            block = kwargs.get('block')
            return WolfKeyDeepLink.schedule(date=date, block=block)
            
        elif notification_type == 'grade_update':
            # Grade update - link to notifications screen to view all grade updates
            return WolfKeyDeepLink.grade_update()
            
        else:
            # Default fallback - link to notifications screen
            logger.warning(f"Unknown notification type for deep linking: {notification_type}")
            return WolfKeyDeepLink.notifications()
            
    except Exception as e:
        logger.error(f"Error creating deep link for notification type {notification_type}: {str(e)}")
        # Fallback to notifications screen
        return WolfKeyDeepLink.notifications()
