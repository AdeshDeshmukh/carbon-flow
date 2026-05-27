from rest_framework import serializers
from .models import Company, DataSource, IngestionJob, Emission, AuditLog


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'created_at', 'is_active']
        read_only_fields = ['id', 'created_at']


class DataSourceSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = DataSource
        fields = ['id', 'company', 'company_name', 'source_type', 'name', 'config', 'created_at']
        read_only_fields = ['id', 'created_at']


class IngestionJobSerializer(serializers.ModelSerializer):
    data_source_name = serializers.CharField(source='data_source.name', read_only=True)
    duration_seconds = serializers.SerializerMethodField()
    
    class Meta:
        model = IngestionJob
        fields = [
            'id', 'data_source', 'data_source_name', 'status', 'file_name',
            'started_at', 'completed_at', 'total_rows', 'successful_rows',
            'failed_rows', 'error_log', 'duration_seconds'
        ]
        read_only_fields = ['id', 'started_at', 'completed_at']
    
    def get_duration_seconds(self, obj):
        if obj.completed_at and obj.started_at:
            delta = obj.completed_at - obj.started_at
            return round(delta.total_seconds(), 2)
        return None


class EmissionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    data_source_name = serializers.CharField(source='data_source.name', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Emission
        fields = [
            'id', 'company', 'company_name', 'data_source', 'data_source_name',
            'ingestion_job', 'scope', 'scope_display', 'category', 'activity_date',
            'original_value', 'original_unit', 'normalized_value', 'normalized_unit',
            'co2e_kg', 'status', 'status_display', 'reviewed_by', 'reviewed_at',
            'raw_data', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'company_name', 'data_source_name', 'scope_display',
            'status_display', 'created_at', 'updated_at'
        ]
    
    def validate_status(self, value):
        if self.instance and self.instance.status == 'locked' and value != 'locked':
            raise serializers.ValidationError("Cannot modify locked emission records")
        return value


class EmissionListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Emission
        fields = [
            'id', 'company_name', 'scope', 'scope_display', 'category',
            'activity_date', 'original_value', 'original_unit', 'co2e_kg',
            'status', 'status_display', 'reviewed_by', 'reviewed_at'
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    emission_id = serializers.IntegerField(source='emission.id', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'emission', 'emission_id', 'user', 'action',
            'field_name', 'old_value', 'new_value', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class EmissionApprovalSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['approved', 'rejected', 'locked'])
    reviewed_by = serializers.CharField(max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_status(self, value):
        emission = self.context.get('emission')
        if emission and emission.status == 'locked':
            raise serializers.ValidationError("Cannot modify locked emission records")
        return value
