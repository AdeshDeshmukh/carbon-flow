from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Count
import tempfile
import os

from .models import Company, DataSource, IngestionJob, Emission, AuditLog
from .serializers import (
    CompanySerializer, DataSourceSerializer, IngestionJobSerializer,
    EmissionSerializer, EmissionListSerializer, AuditLogSerializer,
    EmissionApprovalSerializer
)
from .parsers import parse_sap_csv, parse_utility_csv, parse_travel_csv


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer


class DataSourceViewSet(viewsets.ModelViewSet):
    queryset = DataSource.objects.all()
    serializer_class = DataSourceSerializer


class IngestionJobViewSet(viewsets.ModelViewSet):
    queryset = IngestionJob.objects.all()
    serializer_class = IngestionJobSerializer
    
    @action(detail=False, methods=['post'])
    def upload(self, request):
        file = request.FILES.get('file')
        source_type = request.data.get('source_type')
        company_id = request.data.get('company_id', 1)
        
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        if source_type not in ['sap', 'utility', 'travel']:
            return Response({'error': 'Invalid source_type'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            company = Company.objects.create(name='Demo Company')
        
        data_source, _ = DataSource.objects.get_or_create(
            company=company,
            source_type=source_type,
            defaults={'name': f'{source_type.upper()} Data Source'}
        )
        
        ingestion_job = IngestionJob.objects.create(
            data_source=data_source,
            status='processing',
            file_name=file.name
        )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        try:
            if source_type == 'sap':
                emissions_data, errors = parse_sap_csv(temp_file_path, company, data_source, ingestion_job)
            elif source_type == 'utility':
                emissions_data, errors = parse_utility_csv(temp_file_path, company, data_source, ingestion_job)
            elif source_type == 'travel':
                emissions_data, errors = parse_travel_csv(temp_file_path, company, data_source, ingestion_job)
            
            created_emissions = []
            for emission_dict in emissions_data:
                emission = Emission.objects.create(**emission_dict)
                created_emissions.append(emission)
                
                AuditLog.objects.create(
                    emission=emission,
                    user='system',
                    action='created'
                )
            
            ingestion_job.total_rows = len(emissions_data) + len(errors)
            ingestion_job.successful_rows = len(emissions_data)
            ingestion_job.failed_rows = len(errors)
            ingestion_job.status = 'completed'
            ingestion_job.completed_at = timezone.now()
            
            if errors:
                ingestion_job.error_log = str(errors)
            
            ingestion_job.save()
            
            os.unlink(temp_file_path)
            
            return Response({
                'job_id': ingestion_job.id,
                'status': 'completed',
                'total_rows': ingestion_job.total_rows,
                'successful_rows': ingestion_job.successful_rows,
                'failed_rows': ingestion_job.failed_rows,
                'emissions': EmissionListSerializer(created_emissions, many=True).data,
                'errors': errors
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            ingestion_job.status = 'failed'
            ingestion_job.error_log = str(e)
            ingestion_job.completed_at = timezone.now()
            ingestion_job.save()
            
            os.unlink(temp_file_path)
            
            return Response({
                'error': str(e),
                'job_id': ingestion_job.id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmissionViewSet(viewsets.ModelViewSet):
    queryset = Emission.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EmissionListSerializer
        return EmissionSerializer
    
    @action(detail=True, methods=['patch'])
    def approve(self, request, pk=None):
        emission = self.get_object()
        serializer = EmissionApprovalSerializer(data=request.data, context={'emission': emission})
        
        if serializer.is_valid():
            old_status = emission.status
            
            emission.status = serializer.validated_data['status']
            emission.reviewed_by = serializer.validated_data['reviewed_by']
            emission.reviewed_at = timezone.now()
            
            if 'notes' in serializer.validated_data:
                emission.notes = serializer.validated_data['notes']
            
            emission.save()
            
            AuditLog.objects.create(
                emission=emission,
                user=serializer.validated_data['reviewed_by'],
                action=serializer.validated_data['status'],
                field_name='status',
                old_value=old_status,
                new_value=serializer.validated_data['status']
            )
            
            return Response(EmissionSerializer(emission).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        company_id = request.query_params.get('company_id', 1)
        
        summary_data = Emission.objects.filter(company_id=company_id).values('scope', 'status').annotate(
            total_co2e_kg=Sum('co2e_kg'),
            count=Count('id')
        )
        
        scope_totals = {}
        for item in summary_data:
            scope = item['scope']
            if scope not in scope_totals:
                scope_totals[scope] = {
                    'scope': scope,
                    'total_co2e_kg': 0,
                    'pending': 0,
                    'approved': 0,
                    'locked': 0,
                    'rejected': 0
                }
            
            scope_totals[scope]['total_co2e_kg'] += float(item['total_co2e_kg'] or 0)
            scope_totals[scope][item['status']] += item['count']
        
        return Response({
            'scope_totals': list(scope_totals.values()),
            'grand_total_co2e_kg': sum(s['total_co2e_kg'] for s in scope_totals.values())
        })


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
