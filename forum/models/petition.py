from django.core.validators import MinValueValidator
from django.db import models

from .poll import Poll


class Petition(Poll):
    """A public, two-sided petition implemented as a constrained poll."""

    SUPPORT = 'Support'
    OPPOSE = 'Oppose'
    STANCE_LABELS = (SUPPORT, OPPOSE)

    support_goal = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = 'Petition'
        verbose_name_plural = 'Petitions'
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(support_goal__isnull=True)
                    | models.Q(support_goal__gte=1)
                ),
                name='petition_support_goal_positive',
            ),
        ]

    def get_stance_option(self, stance):
        labels = {
            'support': self.SUPPORT,
            'oppose': self.OPPOSE,
        }
        label = labels.get(str(stance).lower())
        if label is None:
            return None
        return self.options.filter(text=label).first()

    def ensure_stance_options(self):
        """Create the two server-owned petition choices if they are missing."""
        from .poll import PollOption

        existing = set(self.options.values_list('text', flat=True))
        for label in self.STANCE_LABELS:
            if label not in existing:
                PollOption.objects.create(poll=self, text=label)
