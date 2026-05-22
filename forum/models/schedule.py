from django.db import models


class GradebookSnapshot(models.Model):
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name='gradebook_snapshots')
    section_id = models.CharField(max_length=32)
    marking_period_id = models.CharField(max_length=32)
    json_data = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'section_id', 'marking_period_id', 'timestamp')

    def __str__(self):
        return f"Snapshot for {self.user.school_email} | Section {self.section_id} | MP {self.marking_period_id} @ {self.timestamp}"


class DailySchedule(models.Model):
    date = models.DateField(unique=True)
    block_1 = models.CharField(max_length=100, blank=True, null=True)
    block_1_time = models.CharField(max_length=50, blank=True, null=True) 
    block_2 = models.CharField(max_length=100, blank=True, null=True)
    block_2_time = models.CharField(max_length=50, blank=True, null=True)
    block_3 = models.CharField(max_length=100, blank=True, null=True)
    block_3_time = models.CharField(max_length=50, blank=True, null=True)
    block_4 = models.CharField(max_length=100, blank=True, null=True)
    block_4_time = models.CharField(max_length=50, blank=True, null=True)
    block_5 = models.CharField(max_length=100, blank=True, null=True)
    block_5_time = models.CharField(max_length=50, blank=True, null=True)
    block_6 = models.CharField(max_length=100, blank=True, null=True) # Following blocks are only in case of days where there are more than 5 blocks. 
    block_6_time = models.CharField(max_length=50, blank=True, null=True)
    block_7 = models.CharField(max_length=100, blank=True, null=True)
    block_7_time = models.CharField(max_length=50, blank=True, null=True)
    block_8 = models.CharField(max_length=100, blank=True, null=True)
    block_8_time = models.CharField(max_length=50, blank=True, null=True)
    block_9 = models.CharField(max_length=100, blank=True, null=True)
    block_9_time = models.CharField(max_length=50, blank=True, null=True)
    block_10 = models.CharField(max_length=100, blank=True, null=True)
    block_10_time = models.CharField(max_length=50, blank=True, null=True)
    ceremonial_uniform = models.BooleanField(null=True)
    is_school = models.BooleanField(null=True)
    early_dismissal = models.BooleanField(null=True)
    late_start = models.BooleanField(null=True)

    def __str__(self):
        return f"Schedule for {self.date}"
