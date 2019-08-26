from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from onadata.apps.fieldsight.models import Project, Site
from onadata.apps.fsforms.models import Stage, FieldSightXF, Schedule
from onadata.apps.fv3.serializers.ProjectDashboardSerializer import ProjectDashboardSerializer, ProgressGeneralFormSerializer, \
    ProgressScheduledFormSerializer, ProgressStageFormSerializer
from onadata.apps.fv3.role_api_permissions import ProjectDashboardPermissions


class ProjectDashboardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Project.objects.select_related('type', 'sector', 'sub_sector', 'organization')
    serializer_class = ProjectDashboardSerializer
    permission_classes = [IsAuthenticated, ProjectDashboardPermissions]

    def get_queryset(self):
        return self.queryset

    def get_serializer_context(self):
        return {'request': self.request}


class ProjectProgressTableViewSet(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args,  **kwargs):

        project_id = self.kwargs.get('pk', None)
        project_id = get_object_or_404(Project, pk=project_id).id

        generals_queryset = FieldSightXF.objects.select_related('xf').filter(is_staged=False, is_scheduled=False, is_deleted=False,
                                                        project_id=project_id, is_survey=False)
        generals = ProgressGeneralFormSerializer(generals_queryset, many=True)

        schedules_queryset = Schedule.objects.filter(project_id=project_id, schedule_forms__is_deleted=False,
                                                     site__isnull=True, schedule_forms__isnull=False,
                                                     schedule_forms__xf__isnull=False)
        schedules = ProgressScheduledFormSerializer(schedules_queryset, many=True)

        stages_queryset = Stage.objects.filter(stage__isnull=True, project_id=project_id, stage_forms__isnull=True).\
            order_by('order')

        stages = ProgressStageFormSerializer(stages_queryset, many=True)

        return Response({'generals': generals.data, 'schedules': schedules.data, 'stages': stages.data})

