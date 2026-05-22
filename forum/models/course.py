from django.db import models


class Block(models.Model):
    code = models.CharField(max_length=8, unique=True)  # e.g. '1A', '2C'
    label = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.code


class Course(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100, default="Misc")
    description = models.TextField(blank=True)
    # Maximum grade level eligible for this course (e.g., 12). If null, course is available to all grades.
    max_grade = models.IntegerField(null=True, blank=True)
    blocks = models.ManyToManyField(Block, blank=True, related_name='courses')
    
    def __str__(self):
        return f"{self.name}"


class CourseAlias(models.Model):
    name = models.CharField(max_length=100)
    course = models.ForeignKey(Course, related_name='aliases', on_delete=models.CASCADE)


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
