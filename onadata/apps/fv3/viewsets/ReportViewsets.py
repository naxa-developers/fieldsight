from django.contrib.gis.geos import Point
from rest_framework import viewsets, status
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from onadata.apps.fsforms.enketo_utils import CsrfExemptSessionAuthentication
from onadata.apps.fv3.serializers.ReportSerializer import ReportSerializer


class ReportVs(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [BasicAuthentication, CsrfExemptSessionAuthentication]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=False):
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response({"message": "Your Report have been submitted. Thank You"},
                            status=status.HTTP_201_CREATED, headers=headers)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        lat = float(self.request.data.get("lat", 0))
        lng = float(self.request.data.get("lng", 0))
        location = Point(round(lng, 6), round(lat, 6), srid=4326)
        serializer.save(user=self.request.user, location=location)
