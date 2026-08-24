from django.db import models


class Block(models.Model):
    code = models.CharField(max_length=8, unique=True)  # e.g. '1A', '2C'
    label = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.code


class Course(models.Model):
    class Category(models.TextChoices):
        ART = 'Art', 'Art'
        BIOLOGY = 'Biology', 'Biology'
        CHEMISTRY = 'Chemistry', 'Chemistry'
        DRAMA = 'Drama', 'Drama'
        ENVIRONMENTAL_SCIENCE = 'Environmental Science', 'Environmental Science'
        ENGLISH = 'English', 'English'
        FRENCH = 'French', 'French'
        HUMANITIES = 'Humanities', 'Humanities'
        INFORMATION_TECHNOLOGY = 'Information Technology', 'Information Technology'
        LANGUAGE = 'Language', 'Language'
        MANDARIN = 'Mandarin', 'Mandarin'
        DESIGN = 'Design', 'Design'
        MATH = 'Math', 'Math'
        MISC = 'Misc', 'Misc'
        MUSIC = 'Music', 'Music'
        PE = 'PE', 'Physical Education'
        PHYSICS = 'Physics', 'Physics'
        SCIENCE = 'Science', 'Science'
        SOCIAL_STUDIES = 'Social Studies', 'Social Studies'
        SPANISH = 'Spanish', 'Spanish'
        STUDY_HALL = 'Study Hall', 'Study Hall'

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100, choices=Category.choices, default=Category.MISC)
    description = models.TextField(blank=True)
    # Maximum grade level eligible for this course (e.g., 12). If null, course is available to all grades.
    max_grade = models.IntegerField(null=True, blank=True)
    blocks = models.ManyToManyField(Block, blank=True, related_name='courses')
    
    def __str__(self):
        return f"{self.name}"


class CourseAlias(models.Model):
    name = models.CharField(max_length=100)
    course = models.ForeignKey(Course, related_name='aliases', on_delete=models.CASCADE)


class CourseTeacher(models.Model):
    """A community-reported teacher assignment for one course and timetable block."""
    course = models.ForeignKey(Course, related_name='teacher_reports', on_delete=models.CASCADE)
    block = models.CharField(max_length=8)
    teacher_name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'block', 'teacher_name'],
                name='unique_course_teacher_report',
            )
        ]
        ordering = ['block', 'teacher_name']

    def __str__(self):
        return f"{self.course} — {self.block}: {self.teacher_name}"


class UserCourseExperience(models.Model):
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name='experienced_courses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'course']


class UserCourseHelp(models.Model):
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name='help_needed_courses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'course']
