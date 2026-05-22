from django.db import models


class VolunteerPinMilestone(models.Model):
    """
    Configurable pin milestones for volunteer hours.
    """
    name = models.CharField(
        max_length=100,
        help_text="Name of the pin milestone (e.g., 'Bronze Pin', 'Silver Pin')"
    )
    hours_required = models.PositiveIntegerField(
        help_text="Number of volunteer hours required to achieve this milestone"
    )
    has_other_requirements = models.BooleanField(
        default=False,
        help_text="Check if this pin has other requirements beyond volunteer hours"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['hours_required']
        verbose_name = "Volunteer Pin Milestone"
        verbose_name_plural = "Volunteer Pin Milestones"

    def __str__(self):
        return f"{self.name} ({self.hours_required} hours)"


class VolunteerResource(models.Model):
    """
    Links to volunteer service resources that appear on the volunteer hours page.
    """
    title = models.CharField(
        max_length=200,
        help_text="Title of the resource (e.g., 'Volunteer Application Form', 'Service Guidelines')"
    )
    url = models.URLField(
        max_length=500,
        help_text="URL to the resource"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional short description of the resource"
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Order in which the resource appears (lower numbers appear first)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this resource is currently displayed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'title']
        verbose_name = "Volunteer Resource"
        verbose_name_plural = "Volunteer Resources"

    def __str__(self):
        return self.title
