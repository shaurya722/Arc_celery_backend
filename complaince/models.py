from django.db import models


class ComplianceCalculation(models.Model):
    """
    Stores compliance calculation results.
    """
    community = models.ForeignKey(
        'community.Community',
        on_delete=models.CASCADE,
        related_name='compliance_calculations'
    )
    program = models.CharField(max_length=100)
    required_sites = models.IntegerField()
    actual_sites = models.IntegerField()
    shortfall = models.IntegerField(default=0)
    excess = models.IntegerField(default=0)
    compliance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    calculation_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compliance_calculations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'compliance_calculations'
        ordering = ['-calculation_date']
        unique_together = [['community', 'program']]
        indexes = [
            models.Index(fields=['community', 'program']),
            models.Index(fields=['calculation_date']),
        ]
    
    def __str__(self):
        return f"{self.community.name} - {self.program}: {self.compliance_rate}%"
