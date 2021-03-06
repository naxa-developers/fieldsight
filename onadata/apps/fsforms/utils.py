import os
from django.db.models import Q

from fcm.utils import get_device_model

from onadata.apps.fieldsight.models import Project
from onadata.apps.fieldsight.templatetags.filters import FORM_STATUS
from onadata.apps.fsforms.notifications import save_notification

from onadata.apps.logger.xform_instance_parser import get_uuid_from_xml, clean_and_parse_xml

from onadata.settings.local_settings import XML_VERSION_MAX_ITER
from onadata.apps.userrole.models import UserRole
from django.core.files.storage import get_storage_class

from django.utils.translation import ugettext as _

from xml.dom import Node
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.conf import settings


FIELDSIGHT_XFORM_ID = u"_fieldsight_xform_id"


def notify_koboform_updated(xform):
    from onadata.apps.fsforms.models import FieldSightXF
    project_ids = FieldSightXF.objects.filter(xf=xform).values_list('project_id', flat=True).distinct().order_by()
    site_ids = FieldSightXF.objects.filter(xf=xform).values_list('site_id', flat=True).distinct().order_by()
    project_ids = [v for v in project_ids if v]
    site_ids = [v for v in site_ids if v]
    emails = UserRole.objects.filter(ended_at=None,
                                    group__name__in=["Site Supervisor", "Region Supervisor"]
                                     ).filter(
        Q(site__id__in=site_ids) | Q(site__project__id__in=project_ids)
                                    ).values_list('user__email', flat=True).distinct().order_by()
    Device = get_device_model()
    is_delete = False
    message = {'notify_type': 'Form',
               'is_delete': is_delete,
               'form_name': xform.title,
               'xfid': xform.id_string,
               'form_type': "", 'form_type_id':"",
               'status': "Form Updated",
               'site': {}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails,is_active=True).send_message(message)


def send_message(fxf, status=None, comment=None, comment_url=None):
    roles = UserRole.objects.filter(site=fxf.site, ended_at=None, group__name="Site Supervisor")
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    is_delete = True if status is None and fxf.fsform is not None else False
    is_deployed = True
    if fxf.is_deployed:
        status_message = "New Form Deployed"
    else:
        is_deployed = False
        status_message = "Form Undeployed"
    message = {'notify_type': 'Form',
               'is_delete':is_delete,
               'form_id': fxf.id,
               'comment': comment,
               'form_name': fxf.xf.title,
               'xfid': fxf.xf.id_string,
               'form_type':fxf.form_type(), 'form_type_id':fxf.form_type_id(),
               'status': status_message,
               'is_deployed': is_deployed,
               'comment_url': comment_url,
               'site': {'name': fxf.site.name, 'id': fxf.site.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails, is_active=True).send_message(message)


def send_message_project_form(fxf, status=None, comment=None, comment_url=None):
    roles = UserRole.objects.filter(site__project=fxf.project, ended_at=None, group__name="Site Supervisor").distinct('user')
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    is_delete = False
    is_deployed = True
    if fxf.is_deployed:
        status_message = "New Form Deployed"
    else:
        is_deployed = False
        status_message = "Form Undeployed"
    message = {'notify_type': 'ProjectForm',
               'is_delete':is_delete,
               'form_id': fxf.id,
               'comment': comment,
               'form_name': fxf.xf.title,
               'xfid': fxf.xf.id_string,
               'form_type':fxf.form_type(), 'form_type_id':fxf.form_type_id(),
               'status': status_message,
               'is_deployed': is_deployed,
               'comment_url': comment_url,
               'site': {},
               'project': {'name': fxf.project.name, 'id': fxf.project.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails, is_active=True).send_message(message)


def send_message_flagged(fi=None, comment=None, comment_url=None):
    if fi.submitted_by:
        emails = [fi.submitted_by.email]
        Device = get_device_model()
        is_delete = False
        message = {'notify_type': 'Form_Flagged',
                   'is_delete':is_delete,
                   'form_id': fi.fsxf.id,
                   'project_form_id': fi.fsxf.id,
                   'comment': comment,
                   'form_name': fi.fsxf.xf.title,
                   'xfid': fi.fsxf.xf.id_string,
                   'form_type':fi.fsxf.form_type(), 'form_type_id':fi.fsxf.form_type_id(),
                   'status': FORM_STATUS.get(fi.form_status,"New Form"),
                   'comment_url': comment_url,
                   'submission_date_time': str(fi.date),
                   'submission_id': fi.id,
                   'version':fi.version
                   }
        if fi.site:
            message['site'] = {'name': fi.site.name, 'id': fi.site.id, 'identifier':fi.site.identifier}
        if fi.project:
            message['project'] = {'name': fi.project.name, 'id': fi.project.id}
        if fi.fsxf.site:
            message['site_level_form'] = True
        else:
            message['site_level_form'] = False
        save_notification(message, emails)
        Device.objects.filter(name__in=emails, is_active=True).send_message(message)


def send_bulk_message_stages(site_ids):
    return
    roles = UserRole.objects.filter(site_id__in=site_ids, ended_at=None, group__name="Site Supervisor").distinct('user')
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'Stages Ready',
               'is_delete':True,
               'site':{'name': site.name, 'id': site.id}}
    Device.objects.filter(name__in=emails, is_active=True).send_message(message)


def send_message_stages(site):
    roles = UserRole.objects.filter(site=site, ended_at=None, group__name="Site Supervisor")
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'Stages Ready',
               'is_delete':True,
               'site':{'name': site.name, 'id': site.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails, is_active=True).send_message(message)


def send_bulk_message_stages_deployed_project(project):
    roles = UserRole.objects.filter(site__project=project, ended_at=None, group__name="Site Supervisor").distinct('user')
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'deploy_all',
               'is_delete':True,
               'is_project':1,
               'description':u"Stages Ready in Project {}".format(project.name),
               'project':{'name': project.name, 'id': project.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails,is_active=True).send_message(message)


def send_bulk_message_stages_deployed_site(site):
    roles = UserRole.objects.filter(site=site, ended_at=None, group__name="Site Supervisor")
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'deploy_all',
               'is_delete':True,
               'is_project':0,
               'description':"Stages Ready in Site {}".format(site.name),
               'site':{'name': site.name, 'id': site.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails,is_active=True).send_message(message)


def send_bulk_message_stage_deployed_project(project, main_stage, deploy_id):
    roles = UserRole.objects.filter(site__project=project, ended_at=None, group__name="Site Supervisor").distinct('user')
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'deploy_ms',
               'is_delete':True,
               'is_project':1,
               'deploy_id':deploy_id,
               'description':u"Main Stage Ready in Project {}".format(
                   project.name),
               'project':{'name': project.name, 'id': project.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails,is_active=True).send_message(message)


def send_bulk_message_stage_deployed_site(site, main_stage, deploy_id):
    roles = UserRole.objects.filter(site=site, ended_at=None, group__name="Site Supervisor")
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'deploy_ms',
               'is_delete':True,
               'is_project':0,
               'deploy_id':deploy_id,
               'description':"Main Stage Ready in Site {}".format(site.name),
               'site':{'name': site.name, 'id': site.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails, is_active=True).send_message(message)


def send_sub_stage_deployed_project(project, sub_stage, deploy_id):
    roles = UserRole.objects.filter(site__project=project, ended_at=None, group__name="Site Supervisor").distinct('user')
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'deploy_ss',
               'is_delete':True,
               'is_project':1,
               'deploy_id':deploy_id,
               'description':u"Sub Stage Ready in Project {}".format(
                   project.name),
               'project':{'name': project.name, 'id': project.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails, is_active=True).send_message(message)


def send_sub_stage_deployed_site(site, sub_stage, deploy_id):
    roles = UserRole.objects.filter(site=site, ended_at=None, group__name="Site Supervisor").distinct('user')
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'deploy_ss',
               'is_delete':True,
               'is_project':0,
               'deploy_id':deploy_id,
               'description':"Sub Stage Ready in Site {}".format(site.name),
               'site':{'name': site.name, 'id': site.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails, is_active=True).send_message(message)



def send_message_un_deploy(fxf):
    roles = UserRole.objects.filter(site=fxf.site, ended_at=None, group__name="Site Supervisor").distinct('user')
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'Form Altered',
               'is_delete':False,
               'form_id': fxf.id,
                   'is_deployed': fxf.is_deployed,
               'form_name': fxf.xf.title,
               'xfid': fxf.xf.id_string,
               'form_type':fxf.form_type(), 'form_type_id':fxf.form_type_id(),
               'site': {'name': fxf.site.name, 'id': fxf.site.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails, is_active=True).send_message(message)


def send_message_un_deploy_project(fxf):
    roles = UserRole.objects.filter(site__project=fxf.project, ended_at=None, group__name="Site Supervisor").distinct('user')
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'Form Altered Project',
               'is_delete':False,
               'form_id': fxf.id,
               'is_deployed': fxf.is_deployed,
               'form_name': fxf.xf.title,
               'xfid': fxf.xf.id_string,
               'form_type':fxf.form_type(), 'form_type_id':fxf.form_type_id(),
               'site': {},
               'project': {'name': fxf.project.name, 'id': fxf.project.id}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails, is_active=True).send_message(message)


def send_message_xf_changed(fxf=None, form_type=None, id=None):
    roles = UserRole.objects.filter(site=fxf.site, ended_at=None, group__name="Site Supervisor").distinct('user')
    emails = [r.user.email for r in roles]
    Device = get_device_model()
    message = {'notify_type': 'Kobo Form Changed',
               'is_delete': True,
               'site':{'name': fxf.site.name, 'id': fxf.site.id},
               'form':{'xfid': fxf.xf.id_string, 'form_id': fxf.id,
                       'form_type':form_type,'form_source_id':id,'form_name':fxf.xf.title}}
    save_notification(message, emails)
    Device.objects.filter(name__in=emails,is_active=True).send_message(message)


def get_version(xml):
    import re
    n = XML_VERSION_MAX_ITER
    version = check_version(xml, n)
    
    if version:
        return version

    else:
        p = re.compile('version="(.*)">')
        m = p.search(xml)
        if m:
            return m.group(1)

        # for new version labels
        p1 = re.compile("""<bind calculate="\'(.*)\'" nodeset="/(.*)/_version_" """)
        m1 = p1.search(xml)
        if m1:
            return m1.group(1)

        p2 = re.compile("""<bind calculate="(.*)" nodeset="/(.*)/_version_" """)
        m2 = p2.search(xml)
        if m2:
            return m2.group(1)

        #for old version labels
        p3 = re.compile("""<bind calculate="\'(.*)\'" nodeset="/(.*)/__version__" """)
        m3 = p3.search(xml)
        if m3:
            return m3.group(1)
        
        p4 = re.compile("""<bind calculate="(.*)" nodeset="/(.*)/__version__" """)
        m4 = p4.search(xml)
        if m4:
            return m4.group(1)

    return None


def check_version(xml, n):
    import re
    for i in range(n, 0, -1):
        #for old version labels(containing only numbers)
        p = re.compile("""<bind calculate="(.*)" nodeset="/(.*)/_version__00{0}" """.format(i))
        m = p.search(xml)
        if m:
            return m.group(1)

        #for old version labels(containing both letters and alphabets)
        p1 = re.compile("""<bind calculate="\'(.*)\'" nodeset="/(.*)/_version__00{0}" """.format(i))
        m1 = p1.search(xml)
        if m1:
            return m1.group(1)

    return None


def get_path(path, suffix):
    fileName, fileExtension = os.path.splitext(path)
    return fileName + suffix + fileExtension


def image_urls_dict(instance):
    default_storage = get_storage_class()()
    urls = dict()
    suffix = settings.THUMB_CONF['medium']['suffix']
    for a in instance.attachments.all():
        filename = a.media_file.name
        if default_storage.exists(get_path(a.media_file.name, suffix)):
            url = default_storage.url(
                get_path(a.media_file.name, suffix))
        else:
            url = a.media_file.url
        file_basename = os.path.basename(filename)
        if url.startswith('/'):
            url = settings.KOBOCAT_URL + url
        urls[file_basename] = url
    return urls


def inject_instanceid(xml_str, uuid):
    if get_uuid_from_xml(xml_str) is None:
        xml = clean_and_parse_xml(xml_str)
        children = xml.childNodes
        if children.length == 0:
            raise ValueError(_("XML string must have a survey element."))

        # check if we have a meta tag
        survey_node = children.item(0)
        meta_tags = [
            n for n in survey_node.childNodes
            if n.nodeType == Node.ELEMENT_NODE
            and n.tagName.lower() == "meta"]
        if len(meta_tags) == 0:
            meta_tag = xml.createElement("meta")
            xml.documentElement.appendChild(meta_tag)
        else:
            meta_tag = meta_tags[0]

        # check if we have an instanceID tag
        uuid_tags = [
            n for n in meta_tag.childNodes
            if n.nodeType == Node.ELEMENT_NODE
            and n.tagName == "instanceID"]
        if len(uuid_tags) == 0:
            uuid_tag = xml.createElement("instanceID")
            meta_tag.appendChild(uuid_tag)
        else:
            uuid_tag = uuid_tags[0]
        # insert meta and instanceID
        text_node = xml.createTextNode(u"uuid:%s" % uuid)
        uuid_tag.appendChild(text_node)
        return xml.toxml()
    return xml_str


def get_shared_asset_ids(user):
    from onadata.apps.fsforms.models import Asset, ObjectPermission
    codenames = ['view_asset', 'change_asset']
    permissions = Permission.objects.filter(content_type__app_label='kpi', codename__in=codenames)
    content_type = ContentType.objects.get(id=settings.ASSET_CONTENT_TYPE_ID)
    obj_perm = ObjectPermission.objects.filter(user=user,
                                               content_type=content_type,
                                               permission__in=permissions,
                                               deny=False,
                                               inherited=False)
    asset_uids = []
    for item in obj_perm:
        a = Asset.objects.get(id=item.object_id)
        asset_uids.append(a.uid)
    return asset_uids


def has_change_form_permission(request, form, action_type="edit"):
    from onadata.apps.fsforms.models import FormSettings
    if FormSettings.objects.filter(form=form).exists():
        if action_type == "edit":
            if not form.settings.can_edit:
                return False
        else:
            if not form.settings.can_delete:
                return False

    if request.is_super_admin:
        return True

    if form.site is not None:
        project_id = form.site.project_id
    else:
        project_id = form.project_id
    organization_id = Project.objects.get(pk=project_id).organization.id
    user_role_asorgadmin = request.roles.filter(organization_id=organization_id, group__name="Organization Admin")
    if user_role_asorgadmin:
        return True
    if form.site is not None:
        site_id = form.site_id
        user_role = request.roles.filter(site_id=site_id, group__name="Reviewer")
        if user_role:
            return True
    else:
        project_id = form.project.id
    user_role = request.roles.filter(project_id=project_id, group__name="Project Manager")
    if user_role:
        return True
    if request.roles.filter(project_id=project_id, group__name__in=["Reviewer", "Region Reviewer"]).exists():
            return True
    return False
