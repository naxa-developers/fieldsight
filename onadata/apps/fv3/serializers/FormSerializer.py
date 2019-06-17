from rest_framework import serializers

from onadata.apps.logger.models import XForm

from django.conf import settings


class XFormSerializer(serializers.ModelSerializer):
    edit_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    replace_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    media_url = serializers.SerializerMethodField()

    class Meta:
        model = XForm
        fields = ('id_string','title', 'edit_url', 'preview_url', 'replace_url', 'download_url', 'media_url', 'date_created')

    def get_edit_url(self, obj):
        return "{}#forms/{}/edit/".format(settings.KPI_URL, obj.id_string)

    def get_preview_url(self, obj):
        return "{}/forms/preview/{}/".format(settings.KOBOCAT_URL, obj.id_string)

    def get_replace_url(self, obj):
        return "{}{}/".format(settings.KPI_URL,"import")

    def get_download_url(self, obj):
        return "{}{}.{}".format(settings.KPI_ASSET_URL, obj.id_string, "xls")

    def get_media_url(self, obj):
        return "{}/{}/forms/{}/form_settings".format(settings.KOBOCAT_URL, obj.user.username, obj.id_string)


class ShareFormSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField())


class ShareProjectFormSerializer(serializers.Serializer):
    project = serializers.IntegerField()


class ShareTeamFormSerializer(serializers.Serializer):
    team = serializers.IntegerField()