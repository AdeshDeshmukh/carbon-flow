from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'companies'
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class DataSource(models.Model):
    SOURCE_TYPES = [
        ('sap', 'SAP'),
        ('utility', 'Utility'),
        ('travel', 'Travel'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='data_sources')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    name = models.CharField(max_length=255)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'data_sources'

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class IngestionJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='ingestion_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    file_name = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    error_log = models.TextField(blank=True)

    class Meta:
        db_table = 'ingestion_jobs'
        ordering = ['-started_at']

    def __str__(self):
        return f"Job {self.id} - {self.file_name}"


class Emission(models.Model):
    SCOPE_CHOICES = [
        ('1', 'Scope 1'),
        ('2', 'Scope 2'),
        ('3', 'Scope 3'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('locked', 'Locked for Audit'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='emissions')
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='emissions')
    ingestion_job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='emissions')

    scope = models.CharField(max_length=1, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=100)
    activity_date = models.DateField()

    original_value = models.DecimalField(max_digits=15, decimal_places=3)
    original_unit = models.CharField(max_length=20)

    normalized_value = models.DecimalField(max_digits=15, decimal_places=3)
    normalized_unit = models.CharField(max_length=20)

    co2e_kg = models.DecimalField(max_digits=15, decimal_places=3)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.CharField(max_length=255, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    raw_data = models.JSONField()
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'emissions'
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['activity_date']),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.scope} - {self.activity_date}"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('edited', 'Edited'),
        ('locked', 'Locked'),
    ]

    emission = models.ForeignKey(Emission, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    field_name = models.CharField(max_length=100, blank=True, null=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}"

