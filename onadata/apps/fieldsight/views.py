from __future__ import unicode_literals
import datetime
import json
from collections import OrderedDict

import xlwt
from django.contrib.contenttypes.models import ContentType
from django.utils.decorators import method_decorator
from io import BytesIO
from django.contrib import messages
from django.contrib.auth.models import Group, User, Permission
from django.contrib.gis.geos import Point
from django.db import transaction, connection
from django.db.models import Q
from django.forms import modelformset_factory
from django.http import HttpResponseRedirect, JsonResponse, Http404, HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, render, redirect
from django.template.response import TemplateResponse
from django.views.generic import ListView, View
from django.core.urlresolvers import reverse_lazy, reverse
from django.core.serializers import serialize
from django.forms.forms import NON_FIELD_ERRORS
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.contrib.auth.decorators import login_required


from django.db.models import Sum, Case, When, IntegerField, Count

import django_excel as excel
from registration.backends.default.views import RegistrationView
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from onadata.apps.eventlog.models import CeleryTaskProgress
from onadata.apps.fieldsight.bar_data_project import BarGenerator, ProgressBarGenerator
from onadata.apps.fieldsight.management.commands.municipality_data import generate_municipality_data
from onadata.apps.fsforms.line_data_project import LineChartGenerator, LineChartGeneratorOrganization, \
    LineChartGeneratorSite, ProgressGeneratorSite, LineChartGeneratorProject
from onadata.apps.fsforms.models import FieldSightXF, Stage, FInstance, Instance
from onadata.apps.userrole.models import UserRole
from onadata.apps.users.models import UserProfile
from onadata.apps.fsforms.tasks import clone_form
from .mixins import (LoginRequiredMixin, SuperAdminMixin, OrganizationMixin, ProjectMixin, SiteView,
                     CreateView, UpdateView, DeleteView, OrganizationView as OView, ProjectView as PView,
                     group_required, OrganizationViewFromProfile, ReviewerMixin, MyOwnOrganizationMixin,
                     MyOwnProjectMixin, ProjectMixin)

from .rolemixins import FullMapViewMixin, SuperUserRoleMixin, ReadonlyProjectLevelRoleMixin, ReadonlySiteLevelRoleMixin, \
    DonorRoleMixin, DonorSiteViewRoleMixin, SiteDeleteRoleMixin, SiteRoleMixin, ProjectRoleView, ReviewerRoleMixin, \
    ProjectRoleMixin, OrganizationRoleMixin, ProjectRoleMixinDeleteView, RegionRoleMixin, \
    RegionSupervisorReviewerMixin, SuperOrganizationRoleMixin

from .models import ProjectGeoJSON, Organization, Project, Site, BluePrints, UserInvite, Region, SiteType, \
    ProjectType, Sector, ProjectLevelTermsAndLabels, SuperOrganization
from .forms import (OrganizationForm, ProjectForm, SiteForm, RegistrationForm, SetProjectManagerForm, SetSupervisorForm,
                    SetProjectRoleForm, AssignOrgAdmin, UploadFileForm, BluePrintForm, ProjectFormKo, RegionForm,
                    SiteBulkEditForm, SiteTypeForm, ProjectGeoLayerForm, ProjectGsuitSyncForm, FieldsightFormGsuitSyncEditForm, FieldsightFormGsuitSyncNewForm )

from onadata.apps.subscriptions.models import Subscription, Customer, Package
from django.views.generic import TemplateView
from django.core.mail import EmailMessage
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string, get_template
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.crypto import get_random_string

from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode

from onadata.apps.fieldsight.tasks import generateSiteDetailsXls, UnassignAllProjectRolesAndSites, \
    UnassignAllSiteRoles, UnassignUser, generateCustomReportPdf, multiuserassignproject, bulkuploadsites, multiuserassignsite, \
    multiuserassignregion, multi_users_assign_regions, multi_users_assign_to_entire_project, email_after_subscribed_plan
from .generatereport import PDFReport
from django.conf import settings
from django.db.models import Prefetch
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.serializers.json import DjangoJSONEncoder
from django.template import Context
from onadata.apps.fsforms.reports_util import get_images_for_site, get_images_for_site_all, get_site_responses_coords, get_images_for_sites_count
from onadata.apps.staff.models import Team
from .metaAttribsGenerator import generateSiteMetaAttribs
from django.db.models.signals import post_save
from django.dispatch import receiver
from onadata.apps.fsforms.models import SyncSchedule

from onadata.libs.utils.image_tools import image_url
from onadata.apps.logger.models import Attachment
from django.core.files.storage import get_storage_class
from django.core.files.storage import FileSystemStorage

@login_required
def dashboard(request):
    # current_role_count = request.roles.count()
    # if current_role_count == 1:
    #     current_role = request.roles[0]
    #     role_type = request.roles[0].group.name
    #
    #     if role_type == "Staff Project Manager":
    #         return HttpResponseRedirect(reverse("staff:staff-project-detail"))
    #     if role_type == "Unassigned":
    #         HttpResponseRedirect("/fieldsight/application/#/my-roles")
    #     if role_type == "Site Supervisor":
    #         return HttpResponseRedirect(reverse("fieldsight:site-dashboard",  kwargs={'pk': current_role.site.pk}))
    #     if role_type == "Reviewer":
    #         return HttpResponseRedirect(reverse("fieldsight:site-dashboard", kwargs={'pk': current_role.site.pk}))
    #     if role_type == "Region Supervisor":
    #         return HttpResponseRedirect(reverse("fieldsight:regional-sites",  kwargs={'pk': current_role.project.pk, 'region_id': current_role.region.pk}))
    #     if role_type == "Region Reviewer":
    #         return HttpResponseRedirect(reverse("fieldsight:regional-sites", kwargs={'pk': current_role.project.pk, 'region_id': current_role.region.pk}))
    #     if role_type == "Project Donor":
    #         return HttpResponseRedirect(reverse("fieldsight:donor_project_dashboard_lite", kwargs={'pk': current_role.project.pk}))
    #     if role_type == "Project Manager":
    #         return HttpResponseRedirect(reverse("fieldsight:project-dashboard", kwargs={'pk': current_role.project.pk}))
    #     if role_type == "Organization Admin":
    #         return HttpResponseRedirect(reverse("fieldsight:organizations-dashboard",
    #                                             kwargs={'pk': current_role.organization.pk}))
    if not request.is_super_admin:
        return HttpResponseRedirect("/fieldsight/application/#/my-roles")

    # total_users = User.objects.all().count()
    # total_organizations = Organization.objects.all().count()
    # total_projects = Project.objects.all().count()
    # total_sites = Site.objects.all().count()
    # data = serialize('custom_geojson', Site.objects.prefetch_related('site_instances').filter(is_survey=False, is_active=True), geometry_field='location', fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone','id'))

    #
    # # outstanding_query = FInstance.objects.filter(form_status=0)
    # # data = serialize('custom_geojson', Site.objects.filter(is_survey=False, is_active=True).prefetch_related(Prefetch('site_instances', queryset=outstanding_query, to_attr='outstanding')), geometry_field='location', fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone','id'))
    # # fs_forms = FieldSightXF.objects.all()
    # # fs_forms = list(fs_forms)
    # # # outstanding = flagged = approved = rejected = 0
    # # for form in fs_forms:
    # #     if form.form_status == 0:
    # #         outstanding += 1
    # #     elif form.form_status == 1:
    # #         flagged +=1
    # #     elif form.form_status == 2:
    # #         approved +=1
    # #     else:
    # #         rejected +=1
    #
    # dashboard_data = {
    #     'total_users': total_users,
    #     'total_organizations': total_organizations,
    #     'total_projects': total_projects,
    #     'total_sites': total_sites,
    #     # 'outstanding': outstanding,
    #     # 'flagged': flagged,
    #     # 'approved': approved,
    #     # 'rejected': rejected,
    #     'data': data,
    # }
    # return TemplateResponse(request, "fieldsight/fieldsight_dashboard.html", dashboard_data)
    
    return HttpResponseRedirect("/fieldsight/application/#/teams")


def get_site_images(site_id):
    query = {'fs_site': str(site_id), '_deleted_at': {'$exists': False}}
    return settings.MONGO_DB.instances.find(query).sort([("_id", 1)]).limit(20)


def site_images(request, pk):
    cursor = get_site_images(pk)
    cursor = list(cursor)
    medias = []
    for index, doc in enumerate(cursor):
        for media in cursor[index].get('_attachments', []):
            if media:
                medias.append(media.get('download_url', ''))

    return JsonResponse({'images':medias[:5]})

def FormResponseSite(request, pk):
    fi=FInstance.objects.get(instance_id=pk)
    data={}
    if fi.site:
        data['name'] = fi.site.name
        data['pk'] = fi.site.id 

    return JsonResponse(data)


class Organization_dashboard(LoginRequiredMixin, OrganizationRoleMixin, TemplateView):
    template_name = "fieldsight/organization_dashboard.html"

    def dispatch(self, request, *args, **kwargs):

        return redirect('/fieldsight/application/#/team-dashboard/{}'.format(self.kwargs.get('pk')))


    def get_context_data(self, **kwargs):
        # dashboard_data = super(Organization_dashboard, self).get_context_data(**kwargs)
        obj = Organization.objects.get(pk=self.kwargs.get('pk'))
        peoples_involved = obj.organization_roles.filter(ended_at__isnull=True).distinct('user_id')
        sites = Site.objects.filter(project__organization=obj,is_survey=False, is_active=True)[:100]
        data = serialize('custom_geojson', sites, geometry_field='location',
                         fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone', 'id'))
        projects = Project.objects.filter(organization_id=obj.pk)
        total_projects = len(projects)
        total_sites = Site.objects.filter(project__organization=obj,is_survey=False, is_active=True).count()
        outstanding, flagged, approved, rejected = obj.get_submissions_count()
        bar_graph = {} #BarGenerator(sites)
        line_chart = [] #LineChartGeneratorOrganization(obj)
        line_chart_data = {} #line_chart.data()
        # user = User.objects.filter(pk=self.kwargs.get('pk'))
        roles_org = UserRole.objects.filter(organization_id = self.kwargs.get('pk'), ended_at__isnull=True, group__name="Organization Admin")
        # key = settings.STRIPE_PUBLISHABLE_KEY
        has_user_free_package = Subscription.objects.filter(stripe_sub_id="free_plan", stripe_customer__user=self.request.user,
                                                            organization=obj).exists()
        is_owner = obj.owner == self.request.user
        dashboard_data = {
            'obj': obj,
            'projects': projects,
            'sites': sites,
            'peoples_involved': peoples_involved,
            'total_projects': total_projects,
            'total_sites': total_sites,
            'outstanding': outstanding,
            'flagged': flagged,
            'approved': approved,
            'rejected': rejected,
            'data': data,
            'cumulative_data': [], #line_chart_data.values(),
            'cumulative_labels': [], #line_chart_data.keys(),
            'progress_data': [], #bar_graph.data.values(),
            'progress_labels': [] , #bar_graph.data.keys(),
            'roles_org': roles_org,
            'total_submissions': flagged + approved + rejected + outstanding,
            # 'key': key,
            'has_user_free_package': has_user_free_package,
            'is_owner': is_owner
        }
        return dashboard_data


class ProjectDashboard(TemplateView):
    template_name = "fieldsight/project_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.is_super_admin:
            return super(ProjectDashboard, self).dispatch(request, *args, **kwargs)
        print(self.kwargs)

        project_id = self.kwargs.get('pk')
        user_id = request.user.id
        user_role = request.roles.filter(user_id=user_id, project_id=project_id, group__name__in=['Project Manager',
                                                                                                  'Project Donor'])

        if user_role:
            return super(ProjectDashboard, self).dispatch(request, *args, **kwargs)
        organization_id = Project.objects.get(pk=project_id).organization.id
        user_role_asorgadmin = request.roles.filter(user_id=user_id, organization_id=organization_id, group_id=1)

        if user_role_asorgadmin:
            return super(ProjectDashboard, self).dispatch(request, *args, **kwargs)

        raise PermissionDenied()

    def get_context_data(self, **kwargs):
        obj = get_object_or_404(Project, pk=self.kwargs.get('pk'), is_active=True)
        peoples_involved = obj.project_roles.filter(ended_at__isnull=True).distinct('user').count()
        total_sites = obj.sites.filter(is_active=True, is_survey=False,
                                       site__isnull=True
                                       ).count()
        total_survey_sites = obj.sites.filter(is_survey=True)
        outstanding, flagged, approved, rejected = obj.get_submissions_count()
        one_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
        instances = Instance.objects.filter(fieldsight_instance__project_id=obj.id, date_created__gte=one_week_ago)
        new_submissions = instances.count()
        active_supervisors = instances.distinct('user').count()
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=obj).exists()

        try:
            site_visits_query = settings.MONGO_DB.instances.aggregate([{"$match":{"fs_project": obj.id, "start": { '$gte' : one_week_ago.isoformat() } } },  { "$group" : { 
                  "_id" :  {        
                    "fs_site": "$fs_site",
                    "date": { "$substr": [ "$start", 0, 10 ] }
                  },
               }
             }, { "$group": { "_id": "$_id.fs_site", "visits": { '$sum': 1}
             }},
             {"$group": {"_id": None, "total_sum": {'$sum': '$visits'}}}
             ], cursor={})
            site_visits_query = list(site_visits_query)
            if not site_visits_query:
                site_visits = 0
            else:
                site_visits = site_visits_query[0]['total_sum']
        except:
            site_visits = "Error occured."
        
        #     data = []
        #     sites = []
        # else:
        #     sites = obj.sites.filter(is_active=True, is_survey=False).prefetch_related('site_forms', "site_instances")
        #     data = serialize('custom_geojson', sites, geometry_field='location',
        #                  fields=('location', 'id',))
        #     bar_graph = BarGenerator(sites)
        #     progress_data = bar_graph.data.values()
        #     progress_labels = bar_graph.data.keys()
        #     line_chart = LineChartGenerator(obj)
        #     line_chart_data = line_chart.data()
        #     cumulative_labels = line_chart_data.keys()
        #     cumulative_data = line_chart_data.values()
        #
        # roles_project = UserRole.objects.filter(organization__isnull=False,
        #                                         project_id = self.kwargs.get('pk'),
        #                                         site__isnull=True, ended_at__isnull=True)
        dashboard_data = {
            # 'sites': sites,
            'peoples_involved': peoples_involved,
            'obj': obj,
            'total_sites': total_sites,
            'total_survey_sites': total_survey_sites,
            'outstanding': outstanding,
            'flagged': flagged,
            'approved': approved,
            'rejected': rejected,
            'total_submissions': flagged + approved + rejected + outstanding,
            'site_visits' : site_visits,
            'active_supervisors' : active_supervisors,
            'new_submissions' : new_submissions,
            'gsuit_meta_json': json.dumps(obj.gsuit_meta),
            'terms_and_labels': terms_and_labels
            
    }

        return dashboard_data


class SiteSurveyListView(LoginRequiredMixin, ProjectMixin, TemplateView):
    def get(self, request, pk):
        return TemplateResponse(request, "fieldsight/site_survey_list.html", {'project':pk})


class SiteDashboardView(TemplateView):
    template_name = 'fieldsight/site_dashboard.html'

    def dispatch(self, request, *args, **kwargs):

        if request.is_super_admin:
            return super(SiteDashboardView, self).dispatch(request, is_supervisor_only=False, *args, **kwargs)

        site_id = self.kwargs.get('pk')
        site = Site.objects.get(id=site_id)
        region = site.region
        user_id = request.user.id

        organization_id = Site.objects.get(pk=site_id).project.organization_id
        user_role_org_admin = request.roles.filter(organization_id=organization_id, group__name="Organization Admin")
        if user_role_org_admin:
            return super(SiteDashboardView, self).dispatch(request, is_supervisor_only=False, *args, **kwargs)

        project = Site.objects.get(pk=site_id).project
        user_role_as_manager = request.roles.filter(project_id=project.id, group__name__in=["Project Manager",
                                                                                            "Project Donor"])
        if user_role_as_manager:
            return super(SiteDashboardView, self).dispatch(request, is_supervisor_only=False, *args, **kwargs)

        if region is not None:
            user_role_as_region_reviewer_supervisor = request.roles.filter(group__name__in=["Region Reviewer",
                                                                                            "Region Supervisor"],
                                                                           region_id__in=region.get_parent_regions())

            if user_role_as_region_reviewer_supervisor:
                return super(SiteDashboardView, self).dispatch(request, is_supervisor_only=True, *args, **kwargs)

        if region is None:
            user_role_as_region_reviewer_supervisor = request.roles.filter(group__name__in=["Region Reviewer",
                                                                                            "Region Supervisor"],
                                                                           region=region)

            if user_role_as_region_reviewer_supervisor:
                return super(SiteDashboardView, self).dispatch(request, is_supervisor_only=True, *args, **kwargs)

        if site.site is not None:
            user_role = request.roles.filter(group__name__in=["Site Supervisor", "Reviewer"],
                                             site_id__in=site.get_parent_sites())
            if user_role:
                return super(SiteDashboardView, self).dispatch(request, is_supervisor_only=True, *args, **kwargs)

        if site.site is None:
            user_role = request.roles.filter(group__name__in=["Site Supervisor", "Reviewer"],
                                             site=site)
            if user_role:
                return super(SiteDashboardView, self).dispatch(request, is_supervisor_only=True, *args, **kwargs)

        raise PermissionDenied()

    def get_context_data(self, is_supervisor_only, **kwargs):
        # dashboard_data = super(SiteDashboardView, self).get_context_data(**kwargs)
        obj = get_object_or_404(Site, pk=self.kwargs.get('pk'), is_active=True)
        peoples_involved = UserRole.objects.filter(ended_at__isnull=True).filter(
            Q(site=obj) | Q(region__project=obj.project)).select_related('user').distinct('user_id').count()
        data = serialize('custom_geojson', [obj], geometry_field='location',
                         fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone', 'id'))

        line_chart = LineChartGeneratorSite(obj)
        line_chart_data = line_chart.data()
        progress_chart = ProgressGeneratorSite(obj)
        progress_chart_data = progress_chart.data()
        has_progress_chart = True if len(progress_chart_data.keys()) > 0 else False
        meta_questions = obj.project.site_meta_attributes
        meta_answers = obj.site_meta_attributes_ans
        mylist =[]
        for question in meta_questions:
            if question['question_name'] in meta_answers:
                mylist.append({question['question_text'] : meta_answers[question['question_name']]})
        myanswers = mylist

        result = get_images_for_sites_count(obj.id)
        
        countlist = list(result)
        if countlist:
            total_count = countlist[0]['count']
        else:
            total_count = 0
        outstanding, flagged, approved, rejected = obj.get_site_submission()
        response = obj.get_site_submission_count()
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=obj.project).exists()

        dashboard_data = {
            'obj': obj,
            'peoples_involved': peoples_involved,
            'outstanding': outstanding,
            'flagged': flagged,
            'approved': approved,
            'rejected': rejected,
            'data': data,
            'cumulative_data': line_chart_data.values(),
            'cumulative_labels': line_chart_data.keys(),
            'progress_chart_data_data': progress_chart_data.keys(),
            'progress_chart_data_labels': progress_chart_data.values(),
            'has_progress_chart': has_progress_chart,
            'meta_data': myanswers,
            'is_supervisor_only': is_supervisor_only,
            'next_photos_count':total_count - 5 if total_count > 5 else 0,
            'total_photos': total_count,
            'terms_and_labels': terms_and_labels,
            'total_submissions': response['flagged'] + response['approved'] + response['rejected'] + response['outstanding']
            
        }
        return dashboard_data


class GenerateSiteReport(SiteRoleMixin, TemplateView):
    template_name = 'fieldsight/generate_site_report.html'

    def get_context_data(self, is_supervisor_only, **kwargs):
        obj = get_object_or_404(Site, pk=self.kwargs.get('pk'), is_active=True)
        peoples_involved = UserRole.objects.filter(ended_at__isnull=True).filter(
            Q(site=obj) | Q(region__project=obj.project)).select_related('user').distinct('user_id').count()
        data = serialize('custom_geojson', [obj], geometry_field='location',
                         fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone', 'id'))

        meta_questions = obj.project.site_meta_attributes
        meta_answers = obj.site_meta_attributes_ans
        mylist = []
        for question in meta_questions:
            if question['question_name'] in meta_answers:
                mylist.append({question['question_text']: meta_answers[question['question_name']]})
        myanswers = mylist

        result = get_images_for_sites_count(obj.id)

        countlist = list(result)
        if countlist:
            total_count = countlist[0]['count']
        else:
            total_count = 0
        outstanding, flagged, approved, rejected = obj.get_site_submission()
        response = obj.get_site_submission_count()
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=obj.project).exists()

        dashboard_data = {
            'obj': obj,
            'peoples_involved': peoples_involved,
            'outstanding': outstanding,
            'flagged': flagged,
            'approved': approved,
            'rejected': rejected,
            'data': data,
            'meta_data': myanswers,
            'is_supervisor_only': is_supervisor_only,
            'next_photos_count': total_count - 5 if total_count > 5 else 0,
            'total_photos': total_count,
            'terms_and_labels': terms_and_labels,


        }
        return dashboard_data


class OrganizationView(object):
    model = Organization
    paginate_by = 51
    queryset = Organization.objects.all()
    success_url = reverse_lazy('fieldsight:organizations-list')
    form_class = OrganizationForm



class UserDetailView(object):
    model = User
    success_url = reverse_lazy('users:users')
    form_class = RegistrationForm


class OrganizationListView(OrganizationView, SuperUserRoleMixin, ListView):
    pass


class OrganizationCreateView(OrganizationView, CreateView):

    @method_decorator(login_required(login_url='/users/accounts/login/?next=/'))
    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated():
            if request.roles.filter(group__name="Super Admin").exists() or not request.user.organizations.all():
                return super(OrganizationCreateView, self).dispatch(request, *args, **kwargs)
        raise PermissionDenied()

    def get_context_data(self, **kwargs):
        context = super(OrganizationCreateView, self).get_context_data(**kwargs)
        context['base_template'] = "fieldsight/fieldsight_base.html"
        return context

    def form_valid(self, form):

        self.object = form.save()
        self.object.owner = self.request.user
        self.object.save()
        noti = self.object.logs.create(source=self.request.user, type=9, title="new Organization",
                                       organization=self.object, content_object=self.object,
                                       description=u"{0} created a new Team "
                                                   u"named {1}".
                                       format(self.request.user, self.object.name))

        user = self.request.user
        user_id = User.objects.get(username=user).id
        profile = user.user_profile
        if not profile.organization:
            profile.organization = self.object
            profile.save()

        # subscribed to free plan
        if not user.is_superuser:
            free_package = Package.objects.get(plan=0)
            customer = Customer.objects.create(user=self.request.user, stripe_cust_id="free_cust_id")
            Subscription.objects.create(stripe_sub_id="free_plan", stripe_customer=customer, initiated_on=datetime.datetime.now(),
                                        package=free_package, organization=self.object)
            user_id = user_id
            email_after_subscribed_plan.delay(user_id)

        project = Project.objects.get(name="Example Project", organization_id=self.object.id)
        sites = Site.objects.filter(project=project)

        task_obj = CeleryTaskProgress.objects.create(user=user,
                                                     description="Auto Clone and Deployment of Forms",
                                                     task_type=15, content_object=self.object)
        if task_obj:
            project_id = Project.objects.get(name="Example Project", organization_id=self.object.id).id

            clone_form.delay(user_id, project_id, task_obj.id)

        if self.request.roles.filter(group__name="Unassigned").exists() or self.request.user.organizations.all():
            previous_group = UserRole.objects.filter(user=self.request.user, group__name="Unassigned").exists()
            if previous_group:
                unassigned_group = UserRole.objects.filter(user=self.request.user, group__name="Unassigned")
                unassigned_group.delete()

            new_group = Group.objects.get(name="Organization Admin")
            UserRole.objects.create(user=self.request.user, group=new_group, organization=self.object)

            group = Group.objects.get(name='Site Supervisor')
            for site in sites:
                UserRole.objects.get_or_create(user=user, group=group, organization=self.object, project_id=project.id,
                                           site_id=site.id)

            return HttpResponseRedirect(self.object.get_absolute_url())

        return HttpResponseRedirect(self.get_success_url())


class OrganizationUpdateView(OrganizationView, OrganizationRoleMixin, UpdateView):
    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super(OrganizationUpdateView, self).get_context_data(**kwargs)
        context['level'] = "2"
        context['obj'] = Organization.objects.get(id=self.kwargs['pk'])
        context['base_template'] = "fieldsight/manage_base.html"
        return context

    def form_valid(self, form):
        self.object = form.save()
        noti = self.object.logs.create(source=self.request.user, type=13, title="edit Team",
                                       organization=self.object, content_object=self.object,
                                       description=u"{0} changed the details "
                                                   u"of Team named {1}".
                                       format(self.request.user.get_full_name(),
                                              self.object.name))

        return HttpResponseRedirect(self.get_success_url())



class OrganizationDeleteView(OrganizationView, SuperUserRoleMixin, DeleteView):
    pass

@login_required
@group_required('admin')
def alter_org_status(request, pk):
    try:
        obj = Organization.objects.get(pk=int(pk))
            # alter status method on custom user
        if obj.is_active:
            obj.is_active = False
            messages.info(request, u'Organization {0} Deactivated.'.format(
                obj.name))
        else:
            obj.is_active = True
            messages.info(request, u'Organization {0} Activated.'.format(
                obj.name))
        obj.save()
    except:
        messages.info(request, u'Organization {0} not found.'.format(obj.name))
    return HttpResponseRedirect(reverse('fieldsight:organizations-list'))

#
# @login_required
# @group_required('admin')
# def add_org_admin_old(request, pk):
#     obj = get_object_or_404(
#         Organization, id=pk)
#     if request.method == 'POST':
#         form = SetOrgAdminForm(request.POST)
#         user = int(form.data.get('user'))
#         group = Group.objects.get(name__exact="Organization Admin")
#         role = UserRole(user_id=user, group=group, organization=obj)
#         role.save()
#         messages.add_message(request, messages.INFO, 'Organization Admin Added')
#         return HttpResponseRedirect(reverse('fieldsight:organizations-list'))
#     else:
#         form = SetOrgAdminForm(instance=obj)
#     return render(request, "fieldsight/add_admin.html", {'obj':obj,'form':form})

class OrganizationadminCreateView(LoginRequiredMixin, OrganizationRoleMixin, TemplateView):

    def get(self, request, pk=None):
        organization = get_object_or_404(Organization, id=pk)
        form = AssignOrgAdmin(request=request)
        scenario = 'Assign'
        return render(request, 'fieldsight/add_admin_form.html',
                      {'form': form, 'scenario': scenario, 'obj': organization})

    def post(self, request):
        organization = get_object_or_404(Organization, id=id)
        group = Group.objects.get(name__exact="Organization Admin")
        role_obj = UserRole(organization=organization, group=group)
        form = AssignOrgAdmin(data=request.POST, instance=role_obj, request=request)
        if form.is_valid():
            role_obj = form.save(commit=False)
            user_id = request.POST.get('user')
            role_obj.user_id = int(user_id)
            role_obj.save()
            messages.add_message(request, messages.INFO, 'Team Admin Added')
            return HttpResponseRedirect(reverse("fieldsight:organizations-dashboard", kwargs={'pk': id}))


@login_required
@group_required('Organization')
def alter_proj_status(request, pk):
    try:
        obj = Project.objects.get(pk=int(pk))
            # alter status method on custom user
        if obj.is_active:
            obj.is_active = False
            messages.info(request, u'Project {0} Deactivated.'.format(obj.name))
        else:
            obj.is_active = True
            messages.info(request, u'Project {0} Activated.'.format(obj.name))
        obj.save()
    except:
        messages.info(request, u'Project {0} not found.'.format(obj.name))
    return HttpResponseRedirect(reverse('fieldsight:projects-list'))
    

@login_required
@group_required('Project')
def add_proj_manager(request, pk):
    obj = get_object_or_404(
        Project, pk=pk, is_active=True)
    group = Group.objects.get(name__exact="Project Manager")
    role_obj = UserRole(project=obj, group=group)
    scenario = 'Assign'
    if request.method == 'POST':
        form = SetProjectManagerForm(data=request.POST, instance=role_obj, request=request)
        if form.is_valid():
            role_obj = form.save(commit=False)
            user_id = request.POST.get('user')
            role_obj.user_id = int(user_id)
            role_obj.save()
        messages.add_message(request, messages.INFO, 'Project Manager Added')
        return HttpResponseRedirect(reverse("fieldsight:project-dashboard", kwargs={'pk': obj.pk}))
    else:
        form = SetProjectManagerForm(instance=role_obj, request=request)
    return render(request, "fieldsight/add_project_manager.html", {'obj':obj,'form':form, 'scenario':scenario})


@login_required
@group_required('Project')
def alter_site_status(request, pk):
    try:
        obj = Site.objects.get(pk=int(pk))
        if obj.is_active:
            obj.is_active = False
            messages.info(request, u'Site {0} Deactivated.'.format(obj.name))
        else:
            obj.is_active = True
            messages.info(request, u'Site {0} Activated.'.format(obj.name))
        obj.save()
    except:
        messages.info(request, u'Site {0} not found.'.format(obj.name))
    return HttpResponseRedirect(reverse('fieldsight:sites-list'))


@login_required
@group_required('Reviewer')
def add_supervisor(request, pk):
    obj = get_object_or_404(
        Site, pk=int(pk), is_active=True)
    group = Group.objects.get(name__exact="Site Supervisor")
    role_obj = UserRole(site=obj, group=group)
    if request.method == 'POST':
        form = SetSupervisorForm(data=request.POST, instance=role_obj, request=request)
        if form.is_valid():
            role_obj = form.save(commit=False)
            user_id = request.POST.get('user')
            role_obj.user_id = int(user_id)
            role_obj.save()
        messages.add_message(request, messages.INFO, 'Site Supervisor Added')
        return HttpResponseRedirect(reverse("fieldsight:site-dashboard", kwargs={'pk': obj.pk}))
    else:
        form = SetSupervisorForm(instance=role_obj, request=request)
    return render(request, "fieldsight/add_supervisor.html", {'obj':obj,'form':form})


@login_required
@group_required('Project')
def add_central_engineer(request, pk):
    obj = get_object_or_404(
        Project, pk=pk, is_active=True)
    group = Group.objects.get(name__exact="Reivewer")
    role_obj = UserRole(project=obj, group=group)
    scenario = 'Assign'
    if request.method == 'POST':
        form = SetProjectRoleForm(data=request.POST, instance=role_obj, request=request)
        if form.is_valid():
            role_obj = form.save(commit=False)
            user_id = request.POST.get('user')
            role_obj.user_id = int(user_id)
            role_obj.save()
        messages.add_message(request, messages.INFO, 'Reviewer Added')
        return HttpResponseRedirect(reverse("fieldsight:project-dashboard", kwargs={'pk': obj.pk}))
    else:
        form = SetProjectRoleForm(instance=role_obj, request=request,)
    return render(request, "fieldsight/add_central_engineer.html", {'obj':obj,'form':form, 'scenario':scenario})


@login_required
@group_required('Project')
def add_project_role(request, pk):
    obj = get_object_or_404(
        Project, pk=pk, is_active=True)
    role_obj = UserRole(project=obj)
    scenario = 'Assign People'
    form = SetProjectRoleForm(instance=role_obj, request=request)
    if request.method == 'POST':
        form = SetProjectRoleForm(data=request.POST, instance=role_obj, request=request)
        if form.is_valid():
            role_obj = form.save(commit=False)
            user_id = request.POST.get('user')
            role_obj.user_id = int(user_id)
            role_obj.save()
            messages.add_message(request, messages.INFO, u'{} Added'.format(
                role_obj.group.name))
            return HttpResponseRedirect(reverse("fieldsight:project-dashboard", kwargs={'pk': obj.pk}))
    existing_staffs = obj.get_staffs
    return render(request, "fieldsight/add_central_engineer.html", {'obj':obj,'form':form, 'scenario':scenario,
                                                                    "existing_staffs":existing_staffs})


class ProjectView(object):
    model = Project
    success_url = reverse_lazy('fieldsight:project-list')
    form_class = ProjectForm

class ProjectRoleView(object):
    model = Project
    success_url = reverse_lazy('fieldsight:project-list')
    form_class = ProjectForm

class ProjectListView(ProjectRoleView, OrganizationMixin, ListView):
    pass
    


class ProjectCreateView(ProjectView, OrganizationRoleMixin, CreateView):
    
    def get_context_data(self, **kwargs):
        context = super(ProjectCreateView, self).get_context_data(**kwargs)
        context['org'] = Organization.objects.get(pk=self.kwargs.get('pk'))
        context['pk'] = self.kwargs.get('pk')
        context['base_template'] = "fieldsight/fieldsight_base.html"

        sectors = Sector.objects.filter(sector=None)
        sector_list = []
        for sect in sectors:
            sector_dict = {}
            sub_sector_list = []
            sub_sectors = Sector.objects.filter(sector=sect)
            for item in sub_sectors:
                sub_sector_list.append({item.id: str(item.name)})
            sector_dict[str(sect.name)] = sub_sector_list
            sector_list.append(dict(sector_dict))

        context['sub_sectors'] = sector_list

        return context

    def get_form_kwargs(self):
        kwargs = super(ProjectCreateView, self).get_form_kwargs()
        kwargs.update({
            'organization_id': self.kwargs.get('pk'),
            'new': True,
        })
        return kwargs

    def form_valid(self, form):
        self.object = form.save(organization_id=self.kwargs.get('pk'), new=True)
        
        noti = self.object.logs.create(source=self.request.user, type=10, title="new Project",
                                       organization=self.object.organization, content_object=self.object,
                                       description=u'{0} created new project '
                                                   u'named {1}'.format(
                                           self.request.user.get_full_name(), self.object.name))
        return HttpResponseRedirect(self.object.get_absolute_url())


class ProjectUpdateView(ProjectView, ProjectRoleMixin, UpdateView):
    def get_success_url(self):
        return reverse('fieldsight:project-dashboard', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(ProjectUpdateView, self).get_context_data(**kwargs)
        context['level'] = "1"
        context['obj'] = self.object
        context['base_template'] = "fieldsight/manage_base.html"
        context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=self.object).exists()


        sectors = Sector.objects.filter(sector=None)
        sector_list = []
        for sect in sectors:
            sector_dict = {}
            sub_sector_list = []
            sub_sectors = Sector.objects.filter(sector=sect)
            for item in sub_sectors:
                sub_sector_list.append({item.id: str(item.name)})
            sector_dict[str(sect.name)] = sub_sector_list
            sector_list.append(dict(sector_dict))

        context['sub_sectors'] = sector_list

        return context

    def form_valid(self, form):
        self.object = form.save(new=False)

        noti = self.object.logs.create(source=self.request.user, type=14, title="Edit Project",
                                       organization=self.object.organization,
                                       project=self.object, content_object=self.object,
                                       description=u'{0} changed the details '
                                                   u'of project named {1}'.format(
                                           self.request.user.get_full_name(), self.object.name))

        return HttpResponseRedirect(self.get_success_url())


class ProjectDeleteView(ProjectRoleMixinDeleteView, View):
    def get(self, *args, **kwargs):
        project = get_object_or_404(Project, pk=self.kwargs.get('pk'), is_active=True)
        project.is_active = False
        project.save()
        task_obj=CeleryTaskProgress.objects.create(user=self.request.user, description="Removal of UserRoles After project delete", task_type=7, content_object = project)
        if task_obj:
            task = UnassignAllProjectRolesAndSites.delay(task_obj.id, project.id)
            task_obj.task_id = task.id
            task_obj.save()
        
        noti = task_obj.logs.create(source=self.request.user, type=36, title="Delete Project",
                               organization=project.organization, extra_message="project",
                               project=project, content_object=project, extra_object=project.organization,
                               description=u'{0} deleted of project named {'
                                           u'1}'.format(
                                   self.request.user.get_full_name(), project.name))

        return HttpResponseRedirect(reverse('fieldsight:org-project-list', kwargs={'pk': project.organization_id }))


class ProjectGeoLayerView(ProjectRoleMixin, UpdateView):

    model = Project
    template_name = 'fieldsight/project_geo_layer.html'
    form_class = ProjectGeoLayerForm

    def get_success_url(self):
        return reverse('fieldsight:project-dashboard', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(ProjectGeoLayerView, self).get_context_data(**kwargs)
        context['level'] = "1"
        context['obj'] = self.object
        context['base_template'] = "fieldsight/manage_base.html"
        context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=self.object).exists()

        return context

    def get_form_kwargs(self):
        kwargs = super(ProjectGeoLayerView, self).get_form_kwargs()
        proj = Project.objects.get(id=self.kwargs['pk'])
        kwargs.update({
            'organization_id': proj.organization.id,
        })
        return kwargs

    # def form_valid(self, form):
    #     self.object = form.save(new=False)
    #
    #     noti = self.object.logs.create(source=self.request.user, type=14, title="Edit Project",
    #                                    organization=self.object.organization,
    #                                    project=self.object, content_object=self.object,
    #                                    description='{0} changed the details of project named {1}'.format(
    #                                        self.request.user.get_full_name(), self.object.name))

        # return HttpResponseRedirect(self.get_success_url())


def project_terms_label_create(request, pk):

    if request.method == 'POST':
        donor = request.POST.get('donor')
        site = request.POST.get('site')
        site_supervisor = request.POST.get('site_supervisor')
        site_reviewer = request.POST.get('site_reviewer')
        region = request.POST.get('region')
        region_supervisor = request.POST.get('region_supervisor')
        region_reviewer = request.POST.get('region_reviewer')
        project = get_object_or_404(Project, id=pk)

        ProjectLevelTermsAndLabels.objects.create(project=project, donor=donor, site=site, site_supervisor=site_supervisor,
                                                  site_reviewer=site_reviewer, region=region, region_supervisor=region_supervisor,
                                                  region_reviewer=region_reviewer)
        return HttpResponseRedirect(reverse("fieldsight:terms_and_labels", kwargs={'pk': project.id}))
    else:
        return JsonResponse({'error': 'Not Allowed'})


class ProjectTermsLabelUpdate(UpdateView):

    model = ProjectLevelTermsAndLabels
    template_name = 'fieldsight/project_terms_and_label_update.html'
    fields = ('donor', 'site', 'site_supervisor', 'site_reviewer', 'region', 'region_supervisor', 'region_reviewer',)

    def get_context_data(self, **kwargs):
        context = super(ProjectTermsLabelUpdate, self).get_context_data(**kwargs)
        context['obj'] = self.object.project
        context['level'] = "1"

        return context

    def get_success_url(self):
        return reverse('fieldsight:terms_and_labels', kwargs={'pk': self.object.project.id})


class ProjectTermsAndLabelView(ProjectRoleMixin, TemplateView):
    template_name = "fieldsight/project_terms_and_label.html"

    def get_context_data(self, **kwargs):
        context = super(ProjectTermsAndLabelView, self).get_context_data(**kwargs)
        terms = ProjectLevelTermsAndLabels.objects.filter(project_id=self.kwargs['pk']).exists()
        if terms:
            context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project_id=self.kwargs['pk']).get()
        context['terms_exists'] = terms
        context['obj'] = Project.objects.get(pk=self.kwargs['pk'])
        context['level'] = "1"

        return context


class SiteView(object):
    model = Site
    # success_url = reverse_lazy('fieldsight:org-site-list')
    form_class = SiteForm


class SiteListView(SiteView, ReviewerRoleMixin, ListView):
    def get_context_data(self, **kwargs):
        context = super(SiteListView, self).get_context_data(**kwargs)
        context['form'] = SiteForm()
        return context


class SiteCreateView(SiteView, ProjectRoleMixin, CreateView):
    def get_context_data(self, **kwargs):
        context = super(SiteCreateView, self).get_context_data(**kwargs)
        project = Project.objects.get(pk=self.kwargs.get('pk'))
        context['project'] = project
        context['pk'] = self.kwargs.get('pk')
        context['json_questions'] = json.dumps(project.site_meta_attributes)
        context['obj'] = project
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()
        context['terms_and_labels'] = terms_and_labels
        context['region'] = project.cluster_sites

        if terms_and_labels:

            context['site_name'] = project.terms_and_labels.site
            context['region_name'] = project.terms_and_labels.region

        else:
            context['site_name'] = "Site"
            context['region_name'] = "Region"

        return context
        
    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):

        existing_identifier = Site.objects.filter(identifier=form.cleaned_data.get('identifier'),
                                                    project_id=self.kwargs.get('pk'))
        if existing_identifier:
            messages.add_message(self.request, messages.INFO,
                                 'Your identifier "' + form.cleaned_data.get(
                'identifier') + '" conflict with existing site please use different identifier to create site')

            return HttpResponseRedirect(reverse(
                'fieldsight:site-add',
                kwargs={
                    'pk': self.kwargs.get('pk'),
                }
            ))

        self.object = form.save(project_id=self.kwargs.get('pk'), new=True)

        noti = self.object.logs.create(source=self.request.user, type=11, title="new Site",
                                       organization=self.object.project.organization,
                                       project=self.object.project, content_object=self.object, extra_object=self.object.project,
                                       description=u'{0} created a new site '
                                                   u'named {1} in {2}'.format(self.request.user.get_full_name(),
                                                                                 self.object.name, self.object.project.name))
        return HttpResponseRedirect(self.get_success_url())

    def get_form(self, *args, **kwargs):

        form = super(SiteCreateView, self).get_form(*args, **kwargs)
        project = Project.objects.get(pk=self.kwargs.get('pk'))
        form.project = project
        form.fields['region'].queryset = form.fields['region'].queryset.filter(project=project)
        if hasattr(form.Meta, 'project_filters'):
            for field in form.Meta.project_filters:
                form.fields[field].queryset = form.fields[field].queryset.filter(project=form.project, deleted=False)
        del form.fields['weight']

        return form


class SubSiteCreateView(SiteView, ProjectRoleMixin, CreateView):
    def get_context_data(self, **kwargs):
        context = super(SubSiteCreateView, self).get_context_data(**kwargs)
        project = Project.objects.get(pk=self.kwargs.get('pk'))
        site = Site.objects.get(pk=self.kwargs.get('site'))
        context['project'] = project
        context['site'] = site
        context['pk'] = self.kwargs.get('pk')
        context['site'] = self.kwargs.get('site')
        context['json_questions'] = json.dumps(project.site_meta_attributes)
        context['obj'] = project
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()
        context['terms_and_labels'] = terms_and_labels
        if terms_and_labels:

            context['site_name'] = project.terms_and_labels.site

        else:
            context['site_name'] = "Site"

        return context

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):

        existing_identifier = Site.objects.filter(identifier=form.cleaned_data.get('identifier'),
                                                    project_id=self.kwargs.get('pk'))
        if existing_identifier:
            messages.add_message(self.request, messages.INFO,
                                 'Your identifier "' + form.cleaned_data.get(
                'identifier') + '" conflict with existing site please use different identifier to create site')

            return HttpResponseRedirect(reverse(
                'fieldsight:sub-site-add',
                kwargs={
                    'pk': self.kwargs.get('pk'),
                    'site': self.kwargs.get('site'),
                }
            ))

        self.object = form.save(project_id=self.kwargs.get('pk'), new=True, site_id=self.kwargs.get('site'))
        noti = self.object.logs.create(source=self.request.user, type=110,
                                       title="new sub Site",
                                       site=self.object.site,
                                       organization=self.object.project.organization,
                                       project=self.object.project,
                                       content_object=self.object,
                                       extra_object=self.object.site,
                                       description=u'{0} created a new Sub '
                                                   u'site named {1} in {2}'.format(self.request.user.get_full_name(),
                                                                                 self.object.name, self.object.project.name))


        return HttpResponseRedirect(self.get_success_url())

    def get_form(self, *args, **kwargs):

        form = super(SubSiteCreateView, self).get_form(*args, **kwargs)
        # form.project = Project.objects.get(pk=self.kwargs.get('pk'))
        # form.site = Site.objects.get(pk=self.kwargs.get('site'))
        if hasattr(form.Meta, 'project_filters'):
            for field in form.Meta.project_filters:
                form.fields[field].queryset = form.fields[field].queryset.filter(project_id=self.kwargs.get('pk'), deleted=False)
        form.fields['weight'].required = True
        return form


class SiteUpdateView(SiteView, ReviewerRoleMixin, UpdateView):
    def get_context_data(self, **kwargs):
        context = super(SiteUpdateView, self).get_context_data(**kwargs)
        site = Site.objects.get(pk=self.kwargs.get('pk'))
        context['project'] = site.project
        context['pk'] = self.kwargs.get('pk')
        context['json_questions'] = json.dumps(site.project.site_meta_attributes)
        context['json_answers'] = json.dumps(site.site_meta_attributes_ans)
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=site.project).exists()
        context['terms_and_labels'] = terms_and_labels
        context['region'] = site.project.cluster_sites

        if terms_and_labels:
            context['site_name'] = site.project.terms_and_labels.site
            context['region_name'] = site.project.terms_and_labels.region

        else:
            context['site_name'] = 'Site'
            context['region_name'] = 'Region'

        return context

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        site = Site.objects.get(pk=self.kwargs.get('pk'))
        old_meta = site.site_meta_attributes_ans
        previous_identifier = Site.objects.get(pk=self.kwargs.get('pk')).identifier

        existing_identifier = Site.objects.filter(identifier=form.cleaned_data.get('identifier'), project_id=self.object.project_id)
        check_identifier = previous_identifier == form.cleaned_data.get('identifier')

        if not check_identifier and existing_identifier:
            messages.add_message(self.request, messages.INFO, 'Your identifier "' + form.cleaned_data.get(
                'identifier') + '" conflict with existing site please use different identifier to update site')
            return HttpResponseRedirect(reverse(
                'fieldsight:site-edit',
                kwargs={
                    'pk': self.object.pk,
                }
            ))

        self.object = form.save(project_id=self.kwargs.get('pk'), new=False)
        new_meta = json.loads(self.object.site_meta_attributes_ans)


        extra_json = None
        if old_meta != new_meta:
            updated = {}
            meta_questions = site.project.site_meta_attributes
            for question in meta_questions:
                key = question['question_name']
                label = question['question_text']
                if old_meta.get(key) != new_meta.get(key):
                    updated[key] = {'label': label, 'data':[old_meta.get(key, 'null'), new_meta.get(key, 'null')]}
            extra_json = updated

        description = u'{0} changed the details of site named {1}'.format(
            self.request.user.get_full_name(), self.object.name
        )

        noti = self.object.logs.create(
            source=self.request.user, type=15, title="edit Site",
            organization=self.object.project.organization,
            project=self.object.project, content_object=self.object,
            description=description,
            extra_json=extra_json,
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_form(self, *args, **kwargs):

        form = super(SiteUpdateView, self).get_form(*args, **kwargs)
        project = form.instance.project
        form.fields['region'].queryset = form.fields['region'].queryset.filter(project=project)
        if hasattr(form.Meta, 'project_filters'):
            for field in form.Meta.project_filters:
                form.fields[field].queryset = form.fields[field].queryset.filter(project=project, deleted=False)
        if not form.instance.site:
            del form.fields['weight']
        return form


class SiteDeleteView(SiteDeleteRoleMixin, View):
    def get(self, *args, **kwargs):
        site = get_object_or_404(Site, pk=self.kwargs.get('pk'), is_active=True)
        site.is_active = False
        site.identifier = site.identifier+str('_'+ self.kwargs.get('pk'))
        site.save()

        instances = site.site_instances.all().values_list('instance', flat=True)

        Instance.objects.filter(id__in=instances).update(deleted_at=datetime.datetime.now())

        # update in mongo

        result = settings.MONGO_DB.instances.update({"_id": {"$in": list(instances)}},
                                                    {"$set": {'_deleted_at': datetime.datetime.now()}}, multi=True)

        FInstance.objects.filter(instance_id__in=instances).update(is_deleted=True)

        task_obj=CeleryTaskProgress.objects.create(user=self.request.user, description="Removal of UserRoles After Site delete", task_type=7, content_object = site)

        if task_obj:
            task = UnassignAllSiteRoles.delay(task_obj.id, site.id)
            task_obj.task_id = task.id
            task_obj.save()

        noti = task_obj.logs.create(source=self.request.user, type=36, title="Delete Site",
                               organization=site.project.organization, extra_object=site.project,
                               project=site.project, extra_message="site", site=site, content_object=site,
                               description=u'{0} deleted of site named {'
                                           u'1}'.format(
                                   self.request.user.get_full_name(), site.name))
        return HttpResponseRedirect('/fieldsight/application/?project=' + str(site.project.id) + '#/project-sitelist')


@group_required("Project")
@api_view(['POST'])
def ajax_upload_sites(request, pk):
    form = UploadFileForm(request.POST, request.FILES)
    if form.is_valid():
        count = 0
        project = Project(pk=pk)
        try:
            sites = request.FILES['file'].get_records()
            count = len(sites)
            with transaction.atomic():
                for site in sites:
                    site = dict((k,v) for k,v in site.iteritems() if v is not '')
                    lat = site.get("longitude", 85.3240)
                    long = site.get("latitude", 27.7172)
                    location = Point(lat, long, srid=4326)
                    type_id = int(site.get("type", "0"))
                    _site, created = Site.objects.get_or_create(identifier=str(site.get("id")), name=site.get("name"),
                                                                project=project, type_id=type_id)
                    _site.phone = site.get("phone")
                    _site.address = site.get("address")
                    _site.public_desc = site.get("public_desc"),
                    _site.additional_desc = site.get("additional_desc")
                    _site.location=location
                    if type_id:
                        _site.type = SiteType.objects.get(pk=type_id)
                    _site.save()
            if count:
                noti = project.logs.create(source=request.user, type=12, title="Bulk Sites",
                                       organization=project.organization,
                                       project=project, content_object=project,
                                       extra_message=count + "Sites",
                                       description='{0} created a {1} sites in {2}'.
                                           format(request.user.get_full_name(), count, project.name))
            return Response({'msg': 'ok'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'file':e.message}, status=status.HTTP_400_BAD_REQUEST)
    return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)


@group_required("Project")
@api_view(['POST'])
def ajax_save_site(request):
    id = request.POST.get('id', False)
    if id =="undefined":
        id = False
    if id:
        instance = Site.objects.get(pk=id)
        form = SiteForm(request.POST, request.FILES, instance)
    else:
        form = SiteForm(request.POST, request.FILES)
    if form.is_valid():
        form.save()
        return Response({'msg': 'ok'}, status=status.HTTP_200_OK)
    return Response({'error': 'Invalid Site Data'}, status=status.HTTP_400_BAD_REQUEST)


@group_required("Organization")
@api_view(['POST'])
def ajax_save_project(request):
    id = request.POST.get('id', False)
    if id =="undefined":
        id = False
    if id:
        instance = Project.objects.get(pk=id)
        form = ProjectFormKo(request.POST, request.FILES, instance)
    else:
        form = ProjectFormKo(request.POST, request.FILES)
    if form.is_valid():
        form.save()
        return Response({'msg': 'ok'}, status=status.HTTP_200_OK)
    return Response({'error': 'Invalid Project Data'}, status=status.HTTP_400_BAD_REQUEST)


class UploadSitesView(ProjectRoleMixin, TemplateView):
    def get(self, request, pk):
        obj = get_object_or_404(Project, pk=pk, is_active=True)
        form = UploadFileForm()
        regions = obj.project_region.filter(is_active=True)
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=obj).exists()
        selected_regions = request.GET.get('regions')
        if selected_regions:
            selected_regions = selected_regions.split(',')

        return render(
            request, 'fieldsight/upload_sites.html',
            {
                'obj': obj,
                'form': form,
                'project': pk,
                'regions': regions,
                'selected_regions': selected_regions,
                'terms_and_labels': terms_and_labels
            }
        )

    def post(self, request, pk=id):
        obj = get_object_or_404(Project, pk=pk, is_active=True)
        form = UploadFileForm(request.POST, request.FILES)
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=obj).exists()

        if form.is_valid():
            try:
                sitefile = request.FILES['file']
                user = request.user
                task_obj = CeleryTaskProgress.objects.create(user=user, content_object=obj, task_type=0, file=sitefile)
                if task_obj:
                    task = bulkuploadsites.delay(task_obj.pk, pk)
                    task_obj.task_id = task.id
                    task_obj.save()
                    if terms_and_labels:
                        messages.success(request, obj.terms_and_labels.site + ' are being uploaded. You will be notified in notifications list as well.')
                    else:
                        messages.success(request, 'Sites are being uploaded. You will be notified in notifications list as well.')

                else:
                    if terms_and_labels:

                        messages.success(request, obj.terms_and_labels.site +' cannot be updated a the moment.')
                    else:
                        messages.success(request, 'Sites cannot be updated a the moment.')

                return HttpResponseRedirect('/fieldsight/application/?project={}#/project-sitelist'.format(pk))
            except Exception as e:
                form.full_clean()
                if terms_and_labels:
                    form._errors[NON_FIELD_ERRORS] = form.error_class([obj.terms_and_labels.site + ' Upload Failed, UnSupported Data', e])
                    messages.warning(request, obj.terms_and_labels.site + ' Upload Failed, UnSupported Data ')
                else:
                    form._errors[NON_FIELD_ERRORS] = form.error_class(['Sites Upload Failed, UnSupported Data', e])
                    messages.warning(request, 'Site Upload Failed, UnSupported Data ')

        return render(request, 'fieldsight/upload_sites.html', {'obj': obj, 'form': form, 'project': pk})


def download(request):
    sheet = excel.pe.Sheet([[1, 2],[3, 4]])
    return excel.make_response(sheet, "csv")


class UserListView(ProjectMixin, OrganizationViewFromProfile, ListView):
    def get_template_names(self):
        return ['fieldsight/user_list.html']

    def get_context_data(self, **kwargs):
        context = super(UserListView, self).get_context_data(**kwargs)
        context['groups'] = Group.objects.all()
        return context


class FilterUserView(TemplateView):
    def get(self, *args, **kwargs):
        return redirect('fieldsight:user-list')

    def post(self, request, *args, **kwargs):
        name = request.POST.get('name')
        role = request.POST.get('role')
        groups = Group.objects.all()
        object_list = User.objects.filter(is_active=True, pk__gt=0)
        if name:
            object_list = object_list.filter(
                Q(first_name__contains=name) | Q(last_name__contains=name) | Q(username__contains=name))
        if role and role != '0':
            object_list = object_list.filter(user_roles__group__id=role)
        if hasattr(request, "organization") and request.organization:
            object_list = object_list.filter(user_roles__organization=request.organization)
        return render(request, 'fieldsight/user_list.html', {'object_list': object_list, 'groups': groups})



class CreateUserView(LoginRequiredMixin, SuperAdminMixin, UserDetailView, RegistrationView):
    def register(self, request, form, *args, **kwargs):
        with transaction.atomic():
            new_user = super(CreateUserView, self).register(
                request, form, *args, **kwargs)
            is_active = form.cleaned_data['is_active']
            new_user.first_name = request.POST.get('name', '')
            new_user.is_active = is_active
            new_user.is_superuser = True
            new_user.save()
            organization = int(form.cleaned_data['organization'])
            org = Organization.objects.get(pk=organization)
            profile = UserProfile(user=new_user, organization=org)
            profile.save()
        return new_user

class BluePrintsView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        site = Site.objects.get(pk=self.kwargs.get('id'))
        blueprints = site.blueprints.all()
        count = 10 - blueprints.count()
        ImageFormSet = modelformset_factory(BluePrints, form=BluePrintForm, extra=count, can_delete=True)
        formset = ImageFormSet(queryset=blueprints)
        return render(request, 'fieldsight/blueprints_form.html', {'site': site, 'formset': formset,'id': self.kwargs.get('id'),
                                                                   'blueprints':blueprints},)

    def post(self, request, id):
        site = Site.objects.get(pk=self.kwargs.get('id'))
        blueprints = site.blueprints.all()
        count = 10 - blueprints.count()
        ImageFormSet = modelformset_factory(BluePrints, form=BluePrintForm, extra=count, can_delete=True)
        formset = ImageFormSet(request.POST, request.FILES, queryset=blueprints)

        if formset.is_valid():
            instances = formset.save(commit=False)
            for item in instances:
                item.site_id = id
                item.save()

            try:
                # For Django 1.7+
                for item in formset.deleted_objects:
                    item.delete()
            except AssertionError:
                # Django 1.6 and earlier already deletes the objects, trying to
                # delete them a second time raises an AssertionError.
                pass

        return HttpResponseRedirect(reverse("fieldsight:site-blue-prints",
                                            kwargs={'id': id}))

        # if formset.is_valid():
        #     for form in formset.cleaned_data:
        #         if 'image' in form:
        #             image = form['image']
        #             photo = BluePrints(site_id=id, image=image)
        #             photo.save()
        #     messages.success(request,
        #                      "Blueprints saved!")
        #     site = Site.objects.get(pk=id)
        #     blueprints = site.blueprints.all()

        #     ImageFormSet = modelformset_factory(BluePrints, form=BluePrintForm, extra=5)
        #     formset = ImageFormSet(queryset=BluePrints.objects.none())
        #     return render(request, 'fieldsight/blueprints_form.html', {'site': site, 'formset': formset,'id': self.kwargs.get('id'),
        #                                                            'blueprints':blueprints},)

        #     # return HttpResponseRedirect(reverse("fieldsight:site-dashboard", kwargs={'pk': id}))

        # formset = ImageFormSet(queryset=BluePrints.objects.none())
        # return render(request, 'fieldsight/blueprints_form.html', {'formset': formset, 'id': self.kwargs.get('id')}, )


class ManagePeopleSiteView(LoginRequiredMixin, ReviewerRoleMixin, TemplateView):
    def get(self, request, pk):
        obj = get_object_or_404(Site, id=self.kwargs.get('pk'), is_active=True)
        project = Site.objects.get(pk=pk).project
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        return render(request, 'fieldsight/manage_people_site.html', {'obj': obj, 'pk': pk, 'level': "0",
                                                                      'category': "site", 'organization': project.organization.id,
                                                                      'project': project.id, 'site': pk,
                                                                      'terms_and_labels': terms_and_labels
                                                                      })


class ManagePeopleProjectView(LoginRequiredMixin, ProjectRoleMixin, TemplateView):

    def get(self, request, pk):
        obj = get_object_or_404(Project, id=self.kwargs.get('pk'), is_active=True)
        project = Project.objects.get(pk=pk)
        organization=project.organization_id
        regional_supervisor = UserRole.objects.filter(organization_id=organization, group__name="Regional Supervisor")
        regional_reviewer = UserRole.objects.filter(organization_id=organization, group__name="Regional Reviewer")
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        return render(request, 'fieldsight/manage_people_site.html', {'obj': obj, 'pk': pk, 'level': "1",
                                                                      'category':"Project Manager", 'organization': organization,
                                                                      'project': pk, 'type':'project', 'obj':project,
                                                                      'regional_supervisor': regional_supervisor,
                                                                      'regional_reviewer': regional_reviewer,
                                                                      'terms_and_labels': terms_and_labels,

                                                                      })


class ManagePeopleOrganizationView(LoginRequiredMixin, OrganizationRoleMixin, TemplateView):
    def get(self, request, pk):
        obj = get_object_or_404(Organization, id=self.kwargs.get('pk'))
        return render(request, 'fieldsight/manage_people_site.html',
                      {'obj': obj, 'pk': pk, 'level': "2", 'category':"Organization Admin", 'organization': pk,
                       'type':'org'})


class ManagePeopleSuperOrganizationView(LoginRequiredMixin, SuperOrganizationRoleMixin, TemplateView):

    def get(self, request, pk):
        obj = get_object_or_404(SuperOrganization, id=self.kwargs.get('pk'))
        return render(request, 'fieldsight/manage_people_site.html',
                      {'obj': obj, 'pk': pk, 'level': "3", 'category': "Super Organization Admin",
                       'super_organization': pk, 'type': 'super_org'})

def all_notification(user,  message):
    pass


class RolesView(LoginRequiredMixin, TemplateView):
    template_name = "fieldsight/roles_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super(RolesView, self).get_context_data(**kwargs)
        context['org_admin'] = self.request.roles.filter(
            group__name="Organization Admin", organization__is_active=True,
            ended_at__isnull=True)
        context['proj_manager'] = self.request.roles.filter(
            group__name="Project Manager", project__is_active=True,
            ended_at__isnull=True)
        context['proj_donor'] = self.request.roles.filter(
            group__name="Project Donor", project__is_active=True)
        context['site_reviewer'] = self.request.roles.filter(
            group__name="Reviewer", site__is_active=True, ended_at__isnull=True)
        context['site_supervisor'] = self.request.roles.filter(
            group__name="Site Supervisor",
            site__is_active=True, ended_at__isnull=True)

        context['region_supervisor'] = self.request.roles.filter(
            group__name="Region Supervisor",
            region__is_active=True, ended_at__isnull=True)
        context['region_reviewer'] = self.request.roles.filter(
            group__name="Region Reviewer",
            region__is_active=True, ended_at__isnull=True)

        context['staff_project_manager'] = self.request.roles.filter(
            group__name="Staff Project Manager",
            staff_project__is_deleted = False, ended_at__isnull=True)
        context['unassigned'] = self.request.roles.filter(
            group__name="Unassigned")
        has_user_profile = UserProfile.objects.filter(
            user=self.request.user).exists()

        context['has_user_profile'] = has_user_profile
        if has_user_profile:
            context['base_template'] = "fieldsight/fieldsight_base.html"

        else:
            context['base_template'] = \
                "fieldsight/fieldsight_not_user_base.html"

        if Team.objects.filter(leader_id=self.request.user.id).exists():
            context['staff_teams'] = Team.objects.filter(
                leader_id=self.request.user.id, is_deleted=False)
        else:
            context['staff_teams'] = []
        return context


class OrgProjectList(OrganizationRoleMixin, ListView):
    model = Project
    paginate_by = 51
    def get_context_data(self, **kwargs):
        context = super(OrgProjectList, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['tree'] = "organization_projects"
        context['obj'] = Organization.objects.get(pk=self.kwargs.get('pk'))
        return context
    def get_queryset(self):
        queryset = Project.objects.filter(organization_id=self.kwargs.get('pk'))
        return queryset


class OrgSiteList(OrganizationRoleMixin, ListView):
    model = Site
    template_name = 'fieldsight/site_list.html'
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super(OrgSiteList, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['type'] = "org"
        return context
    def get_queryset(self):
        queryset = Site.objects.filter(project__organization_id=self.kwargs.get('pk'), is_survey=False, is_active=True)
        return queryset

class ProjSiteList(ProjectRoleMixin, ListView):
    model = Site
    template_name = 'fieldsight/site_list.html'
    paginate_by = 90

    def get_context_data(self, **kwargs):
        context = super(ProjSiteList, self).get_context_data(**kwargs)
        project = get_object_or_404(Project, id=self.kwargs.get('pk'))
        context['pk'] = self.kwargs.get('pk')
        context['region_id'] = None
        context['type'] = "project"
        context['obj'] = project
        context['level'] = "1"
        context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        return context

    def get_queryset(self):
        queryset = Site.objects.filter(project_id=self.kwargs.get('pk'),is_survey=False, is_active=True)
        return queryset


class ManageProjectSites(ProjectRoleMixin, ListView):
    model = Site
    template_name = 'fieldsight/manage_project_site.html'
    paginate_by = 90

    def get_context_data(self, **kwargs):
        context = super(ManageProjectSites, self).get_context_data(**kwargs)
        project = get_object_or_404(Project, id=self.kwargs.get('pk'))
        context['pk'] = self.kwargs.get('pk')
        context['region_id'] = None
        context['type'] = "project"
        context['obj'] = project
        context['level'] = "1"
        context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        return context

    def get_queryset(self):
        queryset = Site.objects.filter(project_id=self.kwargs.get('pk'),is_survey=False, is_active=True)
        return queryset


class DonorProjSiteList(ReadonlyProjectLevelRoleMixin, ListView):
    model = Site
    template_name = 'fieldsight/donor_site_list.html'
    paginate_by = 90
    
    def get_context_data(self, **kwargs):
        context = super(DonorProjSiteList, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['type'] = "project"
        context['is_form_proj'] = True
        context['is_donor_only'] = kwargs.get('is_donor_only', False)
        return context

    def get_queryset(self):
        queryset = Site.objects.filter(project_id=self.kwargs.get('pk'),is_survey=False, is_active=True)
        return queryset


class OrgUserList(OrganizationRoleMixin, ListView):
    model = UserRole
    paginate_by = 90
    template_name = "fieldsight/user_list_updated.html"

    def get_context_data(self, **kwargs):
        context = super(OrgUserList, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['obj'] = Organization.objects.get(pk=self.kwargs.get('pk'))
        context['organization_id'] = self.kwargs.get('pk')
        context['type'] = "organization"
        return context

    def get_queryset(self):

        queryset = UserRole.objects.select_related('user').filter(organization_id=self.kwargs.get('pk'), ended_at__isnull=True).distinct('user_id')
        return queryset


class ProjUserList(ListView):
    model = UserRole
    paginate_by = 90
    template_name = "fieldsight/user_list_updated.html"

    def dispatch(self, request, *args, **kwargs):
        if request.is_super_admin:
            return super(ProjUserList, self).dispatch(request, *args, **kwargs)
        print(self.kwargs)

        project_id = self.kwargs.get('pk')
        user_id = request.user.id
        user_role = request.roles.filter(user_id=user_id, project_id=project_id, group__name__in=['Project Manager',
                                                                                                  'Project Donor'])

        if user_role:
            return super(ProjUserList, self).dispatch(request, *args, **kwargs)
        organization_id = Project.objects.get(pk=project_id).organization.id
        user_role_asorgadmin = request.roles.filter(user_id=user_id, organization_id=organization_id, group_id=1)

        if user_role_asorgadmin:
            return super(ProjUserList, self).dispatch(request, *args, **kwargs)

        raise PermissionDenied()

    def get_context_data(self, **kwargs):
        context = super(ProjUserList, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['obj'] = Project.objects.get(pk=self.kwargs.get('pk'))
        context['organization_id'] = Project.objects.get(pk=self.kwargs.get('pk')).organization.id
        context['type'] = "project"
        return context

    def get_queryset(self):
        queryset = UserRole.objects.select_related('user').filter(project_id=self.kwargs.get('pk'), ended_at__isnull=True).distinct('user_id')
        return queryset


class SiteUserList(ListView):
    model = UserRole
    paginate_by = 50
    template_name = "fieldsight/user_list_updated.html"

    def dispatch(self, request, *args, **kwargs):

        if request.is_super_admin:
            return super(SiteUserList, self).dispatch(request, *args, **kwargs)

        site_id = self.kwargs.get('pk')
        site = Site.objects.get(id=site_id)
        region = site.region
        user_id = request.user.id
        if region is not None:
            user_role_as_region_reviewer_supervisor = request.roles.filter(group__name="Region Supervisor",
                                                                           region_id__in=region.get_parent_regions())

            if user_role_as_region_reviewer_supervisor:
                return super(SiteUserList, self).dispatch(request, *args, **kwargs)

        if region is None:
            user_role_as_region_reviewer_supervisor = request.roles.filter(group__name="Region Supervisor",
                                                                           region=region)

            if user_role_as_region_reviewer_supervisor:
                return super(SiteUserList, self).dispatch(request, *args, **kwargs)

        if site.site is not None:
            user_role = request.roles.filter(group__name="Site Supervisor",
                                             site_id__in=site.get_parent_sites())
            if user_role:
                return super(SiteUserList, self).dispatch(request, *args, **kwargs)

        if site.site is None:
            user_role = request.roles.filter(group__name="Site Supervisor",
                                             site=site)
            if user_role:
                return super(SiteUserList, self).dispatch(request, *args, **kwargs)
        user_role = request.roles.filter(user_id=user_id, site_id=site_id, group__name="Site Supervisor")

        if user_role:
            return super(SiteUserList, self).dispatch(request, *args, **kwargs)

        project = Site.objects.get(pk=site_id).project
        user_role_aspadmin = request.roles.filter(user_id=user_id, project_id=project.id, group__name__in=['Project Manager',
                                                                                                           'Project Donor'])
        if user_role_aspadmin:
            return super(SiteUserList, self).dispatch(request, *args, **kwargs)

        if Site.objects.filter(pk=site_id, region__isnull=False).values('region').exists():
            region = Site.objects.get(pk=site_id).region
            user_role_region_reviewer = request.roles.filter(user_id=user_id, project_id=project.id,
                                                             region_id=region.id, group__name="Region Supervisor")
            if user_role_region_reviewer:
                return super(SiteUserList, self).dispatch(request, *args, **kwargs)

        organization_id = project.organization.id
        user_role_asorgadmin = request.roles.filter(user_id=user_id, organization_id=organization_id, group_id=1)
        if user_role_asorgadmin:
            return super(SiteUserList, self).dispatch(request, *args, **kwargs)

        raise PermissionDenied()

    def get_context_data(self, **kwargs):
        context = super(SiteUserList, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['obj'] = Site.objects.get(pk=self.kwargs.get('pk'))
        context['organization_id'] = Site.objects.get(pk=self.kwargs.get('pk')).project.organization.id
        context['type'] = "site"
        return context

    def get_queryset(self):
        site = Site.objects.get(id=self.kwargs.get('pk'))
        region = site.region
        if region is not None:
            queryset = UserRole.objects.filter(ended_at__isnull=True).filter(Q(site=site) | Q(region=region)).select_related('user').distinct('user_id')
        else:
            queryset = UserRole.objects.filter(ended_at__isnull=True, site_id=self.kwargs.get('pk')).select_related('user').distinct('user_id')

        return queryset

@login_required()
def ajaxgetuser(request):
    user = User.objects.filter(email=request.POST.get('email'))
    html = render_to_string('fieldsight/ajax_temp/ajax_user.html', {'department': User.objects.filter(email=user)})
    return HttpResponse(html)

def RepresentsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False


@login_required()
def senduserinvite(request):
    emails = request.POST.getlist('emails[]')
    group = Group.objects.get(name=request.POST.get('group'))

    organization_id = None
    project_id =[]
    site_id =[]


    if RepresentsInt(request.POST.get('organization_id')):
        organization_id = request.POST.get('organization_id')
    if RepresentsInt(request.POST.get('project_id')):
        project_id = [request.POST.get('project_id')]
    if RepresentsInt(request.POST.get('site_id')):
        site_id = [request.POST.get('site_id')]

    response = ""

    for email in emails:
        email = email.strip()
        
        userinvite = UserInvite.objects.filter(email__iexact=email, organization_id=organization_id, group=group, project__in=project_id,  site__in=site_id, is_used=False)

        if userinvite:
            if group.name == "Unassigned":
                response += 'Invite for '+ email + ' has already been sent.<br>'
            else:
                response += 'Invite for '+ email + ' in ' + group.name +' role has already been sent.<br>'
            continue

        user = User.objects.filter(email__iexact=email)
        if user:
            userrole = UserRole.objects.filter(user=user[0], group=group, organization_id=organization_id, project__in=project_id, site__in=site_id, ended_at__isnull=True).order_by('-id') 

            if userrole:
                if group.name == "Unassigned":
                    response += userrole[0].user.first_name + ' ' + userrole[0].user.last_name + ' ('+ email + ')' + ' has already joined this Team.<br>'
                else:
                    response += userrole[0].user.first_name + ' ' + userrole[0].user.last_name + ' ('+ email + ')' + ' already has the role for '+group.name+'.<br>' 
                continue
           
        invite = UserInvite(email=email, by_user_id=request.user.id, token=get_random_string(length=32), group=group, organization_id=organization_id)
        invite.save()
        invite.project = project_id
        invite.site = site_id
        current_site = get_current_site(request)

        if len(invite.project.all()) > 0:

            project = get_object_or_404(Project, id=invite.project.all()[0].id)
            terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        else:
            project = ''
            terms_and_labels = False

        subject = 'Invitation for Role'
        is_user = User.objects.filter(email=invite.email).exists()
        data ={
            'email': invite.email,
            # 'domain': current_site.domain,
            'domain': settings.SITE_URL,
            'invite_id': urlsafe_base64_encode(force_bytes(invite.pk)),
            'token': invite.token,
            'invite': invite,
            'terms_and_labels': terms_and_labels,
            'project': project,
            'is_user': is_user
            }
        message = get_template('fieldsight/email_sample.html').render(Context(data))
        email_to = (invite.email,)
        
        msg = EmailMessage(subject, message, None, email_to)
        msg.content_subtype = "html"
        msg.send()
        if group.name == "Unassigned":
            response += "Sucessfully invited "+ email +" to join this Team.<br>"
        else:
            if len(invite.project.all()) > 0:
                project = get_object_or_404(Project, id=invite.project.all()[0].id)
                labels = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()
                if labels:

                    TERMS_AND_LABELS = {'Project Donor': 'Project '+project.terms_and_labels.donor, 'Organization Admin':
                                        'Team Admin', 'Project Manager': 'Project Manager', 'Reviewer': project.terms_and_labels.site_reviewer,
                                        'Site Supervisor': project.terms_and_labels.site_supervisor, 'Super Admin': 'Super Admin',
                                        'Staff Project Manager': 'Staff Project Manager', 'Region Supervisor': project. terms_and_labels.region_supervisor,
                                        'Region Reviewer': project.terms_and_labels.region_reviewer

                                        }
                    response += "Sucessfully invited " + email +" for "+ TERMS_AND_LABELS[group.name] + " role.<br>"
                else:
                    response += "Sucessfully invited " + email + " for " + group.name + " role.<br>"

            else:
                if group.name == 'Organization Admin':

                    response += "Sucessfully invited " + email +" for Team Admin role."
                else:
                    response += "Sucessfully invited " + email +" for "+ group.name +" role.<br>"

        continue

    return HttpResponse(response)


@login_required()
def sendmultiroleuserinvite(request):
    data = json.loads(request.body)
    emails = data.get('emails')
    levels = data.get('levels')
    leveltype = data.get('leveltype')
    group = Group.objects.get(name=data.get('group'))

    response = ""
    region_ids = []

    if leveltype == "region":
        region = Region.objects.get(id=levels[0]);
        project_ids = [region.project_id]
        organization_id = region.project.organization_id  
        site_ids = Site.objects.filter(Q(region_id__in=levels) |
                                       Q(region_id__parent__in=levels) |
                                       Q(region_id__parent__parent__in=levels)).values_list('id', flat=True)

        region_ids = Region.objects.filter(id__in=levels).values_list('id', flat=True)

    elif leveltype == "project":
        project_ids = levels
        organization_id = Project.objects.get(pk=project_ids[0]).organization_id
        site_ids = []
        region_ids = []

    elif leveltype == "site":
        site_ids = levels
        site = Site.objects.get(pk=site_ids[0])
        project_ids = [site.project_id]
        region_ids = []
        organization_id = site.project.organization_id

    for email in emails:
        userinvite = UserInvite.objects.filter(email__iexact=email, organization_id=organization_id, group=group, project__in=project_ids,  site__in=site_ids, is_used=False).exists()
        
        if userinvite:
            response += 'Invite for '+ email + ' in ' + group.name +' role has already been sent.<br>'
            continue

        invite = UserInvite(email=email, by_user_id=request.user.id, token=get_random_string(length=32), group=group, organization_id=organization_id)
        invite.save()
        invite.project = project_ids
        invite.site = site_ids
        invite.regions = region_ids
        project = get_object_or_404(Project, id=project_ids[0])
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()
        subject = 'Invitation for Role'
        is_user = User.objects.filter(email=invite.email).exists()

        data = {
            'user': invite.email,
            'domain': settings.SITE_URL,
            'invite_id': urlsafe_base64_encode(force_bytes(invite.pk)),
            'token': invite.token,
            'invite': invite,
            'terms_and_labels': terms_and_labels,
            'project': project,
            'is_user': is_user
            }
        message = get_template('fieldsight/email_sample.html').render(Context(data))
        email_to = (invite.email,)
        msg = EmailMessage(subject, message, None, email_to)
        msg.content_subtype = "html"
        msg.send()
        
        if group.name == "Unassigned":
            response += "Sucessfully invited " + email + " to join this organization.<br>"
        else:    
            response += "Sucessfully invited " + email + " for " + group.name + " role.<br>"
        continue

    return HttpResponse(response)


def delete_unassigned_group(user):
    """

    Args:
        user: User object

    Returns:

    """
    if UserRole.objects.filter(user=user).count() > 1:
        unassigned_group = UserRole.objects.filter(user=user, group__name="Unassigned")
        if unassigned_group.exists():
            unassigned_group.delete()

   
class ActivateRole(TemplateView):
    def dispatch(self, request, invite_idb64, token):
        invite_id = force_text(urlsafe_base64_decode(invite_idb64))
        invite = UserInvite.objects.filter(id=invite_id, token=token, is_used=False)
        if invite:
            return super(ActivateRole, self).dispatch(request, invite[0], invite_idb64, token)
        return HttpResponseRedirect(reverse('login'))

    def get(self, request, invite, invite_idb64, token):
        if invite.is_used==True:
            return HttpResponseRedirect(reverse('login'))
        user = User.objects.filter(email__iexact=invite.email)

        if user:
            return render(request, 'fieldsight/invite_action.html',{'invite':invite, 'is_used': False, 'status':'',})
        else:
            # return render(request, 'fieldsight/invited_user_reg.html',{'invite':invite, 'is_used': False, 'status':'',})
            return render(request, 'users/register_with_google.html',{'invite':invite, 'is_used': False, 'status':'',})

    def post(self, request, invite, *args, **kwargs):
        user_exists = User.objects.filter(email__iexact=invite.email)
        if user_exists:
            if request.POST.get('response') != "accept":
                invite.is_declined = True
                invite.is_used = True
                invite.save()
                return HttpResponseRedirect(reverse('login'))
            user = user_exists[0]
            profile, created = UserProfile.objects.get_or_create(user=user)

            if not profile.organization:
                profile.organization = invite.organization
                profile.save()
        else:
            username = request.POST.get('username')
            if len(request.POST.get('username')) < 6:
                return render(request, 'fieldsight/invited_user_reg.html',{'invite':invite, 'is_used': False, 'status':'error-6', 'username':request.POST.get('username'), 'firstname':request.POST.get('firstname'), 'lastname':request.POST.get('lastname')})

            for i in username:
                if i.isupper():
                    return render(request, 'fieldsight/invited_user_reg.html',{'invite':invite, 'is_used': False, 'status':'error-3', 'username':request.POST.get('username'), 'firstname':request.POST.get('firstname'), 'lastname':request.POST.get('lastname')})
                    break
                if not i.isalnum():
                    return render(request, 'fieldsight/invited_user_reg.html',{'invite':invite, 'is_used': False, 'status':'error-1', 'username':request.POST.get('username'), 'firstname':request.POST.get('firstname'), 'lastname':request.POST.get('lastname')})
                    break
            
            if request.POST.get('password1') != request.POST.get('password2'):
                return render(request, 'fieldsight/invited_user_reg.html',{'invite':invite, 'is_used': False, 'status':'error-4', 'username':request.POST.get('username'), 'firstname':request.POST.get('firstname'), 'lastname':request.POST.get('lastname')})

            if User.objects.filter(username__iexact=request.POST.get('username')).exists():
                return render(request, 'fieldsight/invited_user_reg.html',{'invite':invite, 'is_used': False, 'status':'error-2', 'username':request.POST.get('username'), 'firstname':request.POST.get('firstname'), 'lastname':request.POST.get('lastname')})

            if request.POST.get('password1') != request.POST.get('password2'):
                return render(request, 'fieldsight/invited_user_reg.html',{'invite':invite, 'is_used': False, 'status':'error-4', 'username':request.POST.get('username'), 'firstname':request.POST.get('firstname'), 'lastname':request.POST.get('lastname')})


            if request.POST.get('password1') == request.POST.get('password2') and len(request.POST.get('password1')) < 8:
                return render(request, 'fieldsight/invited_user_reg.html',{'invite':invite, 'is_used': False, 'status':'error-5', 'username':request.POST.get('username'), 'firstname':request.POST.get('firstname'), 'lastname':request.POST.get('lastname')})
            

            user = User(username=request.POST.get('username'), email=invite.email, first_name=request.POST.get('firstname'), last_name=request.POST.get('lastname'))
            user.set_password(request.POST.get('password1'))
            user.save()
            
            codenames=['add_asset', 'change_asset','delete_asset', 'view_asset', 'share_asset', 'add_finstance', 'change_finstance', 'add_instance', 'change_instance']
            permissions = Permission.objects.filter(codename__in=codenames)
            for permission in permissions:
                user.user_permissions.add(permission)


            profile, created = UserProfile.objects.get_or_create(user=user, organization=invite.organization)

        site_ids = invite.site.all().values_list('pk', flat=True)
        project_ids = invite.project.all().values_list('pk', flat=True)

        if invite.regions.all().values_list('pk', flat=True).exists():
            regions_id = invite.regions.all().values_list('pk', flat=True)
            for region_id in regions_id:
                project_id = Region.objects.get(id=region_id).project.id
                userrole, created = UserRole.objects.get_or_create(user=user, group=invite.group,
                                                               organization=invite.organization, project_id=project_id,
                                                               site_id=None, region_id=region_id)
            delete_unassigned_group(user)
        else:
            for project_id in project_ids:
                for site_id in site_ids:
                    userrole, created = UserRole.objects.get_or_create(user=user, group=invite.group, organization=invite.organization, project_id=project_id, site_id=site_id)
                    delete_unassigned_group(user)

                if not site_ids:
                    try:
                        userrole, created = UserRole.objects.get_or_create(user=user, group=invite.group, organization=invite.organization, project_id=project_id, site=None)
                    except AttributeError:
                        invite.is_used = True
                        invite.save()
                    delete_unassigned_group(user)

        if not project_ids:
            userrole, created = UserRole.objects.get_or_create(user=user, group=invite.group, organization=invite.organization, project=None, site=None, region=None)
            delete_unassigned_group(user)
            if invite.group_id == 1:
                permission = Permission.objects.filter(codename='change_finstance')
                user.user_permissions.add(permission[0])


        invite.is_used = True
        invite.save()
        extra_msg = ""
        site=None
        project=None
        region=None
        if invite.group.name == "Organization Admin":
            noti_type = 1
            content = invite.organization

        elif invite.group.name == "Project Manager":
            if invite.project.all().count() == 1:
                noti_type = 2
                content = invite.project.all()[0]
            else:
                noti_type = 26
                extra_msg = invite.project.all().count()
                content = invite.organization
            project = invite.project.all()[0]
        
        elif invite.group.name == "Reviewer":
            if invite.site.all().count() == 1:
                noti_type = 3
                content = invite.site.all()[0]
            else:
                noti_type = 27
                extra_msg = invite.site.all().count()
                content = invite.project.all()[0]
            project=invite.project.all()[0]
        
        elif invite.group.name == "Site Supervisor":
            if invite.site.all().count() == 1:
                noti_type = 4
                content = invite.site.all()[0]
            else:
                noti_type = 28
                extra_msg = invite.site.all().count()
                content = invite.project.all()[0]
            project=invite.project.all()[0]

        elif invite.group.name == "Region Reviewer":
            if invite.regions.all().count() == 1:
                noti_type = 37
                content = invite.regions.all()[0]
            else:
                noti_type = 39
                extra_msg = invite.regions.all().count()
                content = invite.project.all()[0]
            project = invite.project.all()[0]

        elif invite.group.name == "Region Supervisor":
            if invite.regions.all().count() == 1:
                noti_type = 38
                content = invite.regions.all()[0]
            else:
                noti_type = 40
                extra_msg = invite.regions.all().count()
                content = invite.project.all()[0]
            project = invite.project.all()[0]

        elif invite.group.name == "Unassigned":
            noti_type = 24
            # if invite.site.all():
            #     content = invite.site.all()[0]
            #     project = invite.project.all()[0]
            #     site = invite,project.all()[0]
            # elif invite.project.all().count():
            #     content = invite.project.all()[0]
            #     project = invite.project.all()[0]
            # else:   
            content = invite.organization

        elif invite.group.name == "Project Donor":
            noti_type = 25
            content = invite.project.all()[0]

        noti = invite.logs.create(source=user, type=noti_type, title="new Role", organization=invite.organization, extra_message=extra_msg, project=project, site=site, content_object=content, extra_object=invite.by_user,
                                       description=u"{0} was added as the {1} of {2} by {3}.".
                                       format(user.username, invite.group.name, content.name, invite.by_user))
        return HttpResponseRedirect(reverse('login'))


@login_required()
def checkemailforinvite(request):
    user = User.objects.select_related('user_profile').filter(email__icontains=request.POST.get('email'))
    if user:
        return render(request, 'fieldsight/invite_response.html', {'users': user,})
    else:
        return HttpResponse("No existing User found.<a href='#' onclick='sendnewuserinvite()'>send</a>")

def checkusernameexists(request):
    user = User.objects.get(username=request.POST.get('email'))
    if user:
        return render(request, 'fieldsight/invite_response.html', {'users': user,})
    else:
        return HttpResponse("No existing User found.<a href='#' onclick='sendnewuserinvite()'>send</a>")


class ProjectSummaryReport(LoginRequiredMixin, ProjectRoleMixin, TemplateView):
    def get(self, request, pk):
        obj = Project.objects.get(pk=self.kwargs.get('pk'))
        organization = Organization.objects.get(pk=obj.organization_id)
        peoples_involved = obj.project_roles.filter(group__name__in=["Project Manager", "Reviewer"]).distinct('user')
        project_managers = obj.project_roles.select_related('user').filter(group__name__in=["Project Manager"]).distinct('user')
        if obj.sites.filter(is_active=True, is_survey=False).count() <= 1000:
            sites = obj.sites.filter(is_active=True, is_survey=False)    
        else:
            sites = obj.sites.filter(is_active=True, is_survey=False)[:100]
        
        data = serialize('custom_geojson', sites, geometry_field='location',
                         fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone','id',))

        total_sites = len(sites)
        total_survey_sites = obj.sites.filter(is_survey=True).count()
        outstanding, flagged, approved, rejected = obj.get_submissions_count()
        bar_graph = BarGenerator(sites)

        line_chart = LineChartGenerator(obj)
        line_chart_data = line_chart.data()
        dashboard_data = {
            'sites': sites,
            'obj': obj,
            'peoples_involved': peoples_involved,
            'total_sites': total_sites,
            'total_survey_sites': total_survey_sites,
            'pending': outstanding,
            'flagged': flagged,
            'approved': approved,
            'rejected': rejected,
            'data': data,
            'cumulative_data': line_chart_data.values(),
            'cumulative_labels': line_chart_data.keys(),
            'progress_data': bar_graph.data.values(),
            'progress_labels': bar_graph.data.keys(),
            'project_managers':project_managers,
            'organization': organization,
            'total_submissions': line_chart_data.values()[-1],
        }
        return render(request, 'fieldsight/project_summary_report.html', dashboard_data)


class UserActivityReport(ProjectRoleMixin, TemplateView):

    def get(self, request, pk, *args, **kwargs):
        start_date = self.kwargs.get('start_date')
        end_date = self.kwargs.get('end_date')
        split_startdate = start_date.split('-')
        split_enddate = end_date.split('-')

        new_startdate = datetime.date(int(split_startdate[0]), int(split_startdate[1]), int(split_startdate[2]))
        end = datetime.date(int(split_enddate[0]), int(split_enddate[1]), int(split_enddate[2]))

        new_enddate = end + datetime.timedelta(days=1)

        query = {}
        query['pending'] = Sum(
            Case(
                When(supervisor__instance__date_created__range=[new_startdate, new_enddate],supervisor__form_status=0, supervisor__project_id=pk, then=1),
                default=0, output_field=IntegerField()
            ))

        query['rejected'] = Sum(
            Case(
                When(supervisor__instance__date_created__range=[new_startdate, new_enddate],supervisor__form_status=1, supervisor__project_id=pk, then=1),
                default=0, output_field=IntegerField()
            ))

        query['flagged'] = Sum(
            Case(
                When(supervisor__instance__date_created__range=[new_startdate, new_enddate],supervisor__form_status=2, supervisor__project_id=pk, then=1),
                default=0, output_field=IntegerField()
            ))

        query['approved'] = Sum(
            Case(
                When(supervisor__instance__date_created__range=[new_startdate, new_enddate],supervisor__form_status=3, supervisor__project_id=pk, then=1),
                default=0, output_field=IntegerField()
            ))    

        query['re_approved'] = Sum(
            Case(
                When(submission_comments__date__range=[new_startdate, new_enddate], submission_comments__finstance__project_id=pk, submission_comments__new_status=3, then=1),
                default=0, output_field=IntegerField()
            ))

        query['re_rejected'] = Sum(
            Case(
                When(submission_comments__date__range=[new_startdate, new_enddate], submission_comments__finstance__project_id=pk, submission_comments__new_status=1, then=1),
                default=0, output_field=IntegerField()
            ))        

        query['re_flagged'] = Sum(
            Case(
                When(submission_comments__date__range=[new_startdate, new_enddate], submission_comments__finstance__project_id=pk, submission_comments__new_status=2, then=1),
                default=0, output_field=IntegerField()
            ))        

        query['resolved'] = Sum(
            Case(
                When(submission_comments__date__range=[new_startdate, new_enddate], submission_comments__finstance__project_id=pk, submission_comments__old_status__in=[1,2], submission_comments__new_status=3, then=1),
                default=0, output_field=IntegerField()
            ))


        user = User.objects.filter(pk=self.kwargs.get('user_id')).annotate(**query).first()
        roles = user.user_roles.filter(project_id=pk, ended_at__isnull=True).distinct('group_id').values_list('group__name', flat=True)
        # recent_images = settings.MONGO_DB.instances.aggregate([{"$match":{"_submitted_by": "santoshkhatri"}, "start": { 
        #                     '$gte' : new_startdate.isoformat(),
        #                     '$lte' : end.isoformat() 
        #                 }
        #                 }, {"$unwind":"$_attachments"},{"$match":{"_attachments.mimetype" : "image/jpeg"}},  {"$project" : {"_attachments.download_url":1, }},{ "$sort" : { "_id": -1 }}, { "$limit": 3 }])
        coords = settings.MONGO_DB.instances.aggregate([
            {
                "$match":
                    {
                        "_submitted_by": user.username,
                        "_submission_time": { 
                                '$gte' : new_startdate.isoformat(),
                                '$lte' : end.isoformat() 
                        },
                        "_geolocation": {
                                "$not":{ "$elemMatch": { "$eq": None }}
                        },
                        "fs_project": {'$in' : [str(pk), int(pk)]}
                    }
            },
            {
                "$project" :
                    {
                        "_id":0, "type": {"$literal": "Feature"},
                        "geometry":{
                            "type": {"$literal": "Point"},
                            "coordinates": "$_geolocation"
                        },
                        "properties": {
                            "id":"$_id",
                            "fs_uuid":"$fs_uuid",
                            "submitted_by":"$_submitted_by"
                        }
                    }
            }], cursor={})
        coords = list(coords)
        response_coords = {'features': coords, 'type':'FeatureCollection'}
        submission_queryset = user.supervisor.filter(project_id=pk, instance__date_created__range=[new_startdate, new_enddate])
        approved = submission_queryset.filter(form_status=3).count()
        rejected = submission_queryset.filter(form_status=1).count()
        pending = submission_queryset.filter(form_status=0).count()
        flagged = submission_queryset.filter(form_status=2).count()
             
        total_submissions = submission_queryset.count()
        submissions = submission_queryset.values_list(
            'project_fxf__xf__title',
            'instance__date_created',
            'site__name',
            'submitted_by__username'
        )
        visits_and_worked = settings.MONGO_DB.instances.aggregate(
            [
                {
                    "$match":{
                        "_submitted_by": user.username,
                        "start": { 
                            '$gte' : new_startdate.isoformat(),
                            '$lte' : new_enddate.isoformat() 
                        },
                        "fs_project": {'$in' : [str(pk), int(pk)]}
                    }
                },
                { 
                    "$group" : { 
                        "_id" :  { 
                            "user": "$_submitted_by",
                            "fs_site": "$fs_site",
                            "date": { 
                                "$substr": [ "$start", 0, 10 ]
                            }
                        },
                            "submissions": {'$sum':1}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "_user":"$_id.user",
                            "_fs_site": "$_id.fs_site"
                        },
                        "submissions": {'$sum': '$submissions'},
                        "visits": { '$sum': 1}
                    }
                },
                {
                    "$group": {
                        "_id": "$_id._user",
                        "total_worked_days": {'$sum': '$visits'},
                        "submissions": {'$sum': '$submissions'},
                        "sites_visited": {'$sum': 1}
                    }
                }
            ], cursor={}
        )
        visits_and_worked = list(visits_and_worked)
        try:
            vac = visits_and_worked[0]
        except:
            vac = {
                '_id': user.username,
                'sites_visited': 0,
                'submissions': 0,
                'total_worked_days': 0
            }

        dashboard_data = {
            'user': user,
            'roles': roles,
            # 'recent_images': recent_images,
            'data': json.dumps(response_coords, cls=DjangoJSONEncoder, ensure_ascii=False).encode('utf8'),
            'submissions': submissions,
            'visits_and_worked': vac,
            'total_submissions': total_submissions,
            'approved': approved,
            'pending': pending,
            'rejected': rejected,
            'flagged': flagged,
            
            're_total': user.re_approved + user.re_rejected + user.re_flagged,
            'resolved': user.resolved,
            're_approved': user.re_approved,
            're_rejected': user.re_rejected,
            're_flagged': user.re_flagged,

        }
        return render(request, 'fieldsight/user_activity_report.html', dashboard_data)


class SiteSummaryReport(LoginRequiredMixin, TemplateView):

    def get(self, request, **kwargs):
        obj = Site.objects.get(pk=self.kwargs.get('pk'))
        project = Project.objects.get(pk=obj.project_id)
        peoples_involved = obj.site_roles.filter(ended_at__isnull=True).distinct('user')
        data = serialize('custom_geojson', [obj], geometry_field='location',
                         fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone', 'id'))
        supervisor = obj.site_roles.select_related('user').filter(group__name__in=["Site Supervisor"]).distinct('user')
        reviewer = obj.site_roles.select_related('user').filter(group__name__in=["Reviewer"]).distinct('user')
        line_chart = LineChartGeneratorSite(obj)
        line_chart_data = line_chart.data()

        outstanding, flagged, approved, rejected = obj.get_site_submission()


        recent_resp_imgs = get_images_for_site(obj.pk)
        three_recent_imgs = list(recent_resp_imgs)[:2]



        dashboard_data = {
            'obj': obj,
            'peoples_involved': peoples_involved,
            'outstanding': outstanding,
            'flagged': flagged,
            'approved': approved,
            'rejected': rejected,
            'data': data,
            'cumulative_data': line_chart_data.values(),
            'cumulative_labels': line_chart_data.keys(),
            'project': project,
            'supervisor' : supervisor,
            'reviewer' : reviewer,
            'metas': generateSiteMetaAttribs(obj.id),
            'recent_images': three_recent_imgs,
            'total_submissions': line_chart_data.values()[-1],

        }
        return render(request, 'fieldsight/site_summary_report.html', dashboard_data)


class MultiUserAssignSiteView(ProjectRoleMixin, TemplateView):
    def get(self, request, pk):
        project_obj = Project.objects.get(pk=pk)
        return render(request, 'fieldsight/multi_user_assign.html',{'type': "site", 'pk':pk})

    def post(self, request, pk, *args, **kwargs):
        data = json.loads(self.request.body)
        sites = data.get('sites')
        users = data.get('users')
        group = Group.objects.get(name=data.get('group'))
        user = request.user
        project = get_object_or_404(Project, pk=pk, is_active=True)
        task_obj =CeleryTaskProgress.objects.create(user=user, content_object = project, task_type=2)
        if task_obj:
            task = multiuserassignsite.delay(task_obj.pk, pk, sites, users, group.id)
            task_obj.task_id = task.id
            task_obj.save()
            return HttpResponse('sucess')
        else:
            return HttpResponse('Failed')

class MultiUserAssignProjectView(OrganizationRoleMixin, TemplateView):

    def post(self, request, pk, *args, **kwargs):
        data = json.loads(self.request.body)
        projects = data.get('projects')
        users = data.get('users')
        group = Group.objects.get(name=data.get('group'))
        group_id = Group.objects.get(name="Project Manager").id
        user = request.user
        org = get_object_or_404(Organization, pk=pk)
        task_obj = CeleryTaskProgress.objects.create(user=user, content_object = org, task_type=1)
        if task_obj:
            task = multiuserassignproject.delay(task_obj.pk, pk, projects, users, group_id)
            task_obj.task_id=task.id
            task_obj.save()
            return HttpResponse("Success")
        else:
            return HttpResponse("Failed")


def viewfullmap(request):
    data = serialize('full_detail_geojson',
                     Site.objects.prefetch_related('site_instances').filter(is_survey=False, is_active=True),
                     geometry_field='location',
                     fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone', 'id'))

    dashboard_data = {

        'data': data,
    }
    return render(request, 'fieldsight/map.html', dashboard_data)


class OrgFullmap(LoginRequiredMixin, OrganizationRoleMixin, TemplateView):
    template_name = "fieldsight/map.html"
    def get_context_data(self, **kwargs):
        obj = Organization.objects.get(pk=self.kwargs.get('pk'))
        dashboard_data = {
            'obj': obj,
            'mapfor': "organization"
            }
        return dashboard_data


class ProjFullmap(ReadonlyProjectLevelRoleMixin, TemplateView):
    template_name = "fieldsight/map.html"

    def get_context_data(self, **kwargs):
        obj = Project.objects.get(pk=self.kwargs.get('pk'))
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=obj).exists()
        regions = Region.objects.filter(project=obj, is_active=True)
        site_types = SiteType.objects.filter(project=obj, deleted=False)

        dashboard_data = {
            'obj': obj,
            'mapfor': "project",
            'terms_and_labels': terms_and_labels,
            'regions': regions,
            'site_types': site_types
            }
        return dashboard_data

class SiteFullmap(ReadonlySiteLevelRoleMixin, TemplateView):
    template_name = "fieldsight/map.html"

    def get_context_data(self, **kwargs):
        obj = Site.objects.get(pk=self.kwargs.get('pk'))
        data = serialize('full_detail_geojson', [obj], geometry_field='location',
                         fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone', 'id'))
        dashboard_data = {
            'data': data,
            'geo_layers': obj.project.geo_layers.all(),
            'is_donor_only': kwargs.get('is_donor_only', False)
        }
        return dashboard_data


class OrganizationdataSubmissionView(TemplateView):
    template_name = "fieldsight/organizationdata_submission.html"

    def get_context_data(self, **kwargs):
        data = super(OrganizationdataSubmissionView, self).get_context_data(**kwargs)
        data['obj'] = Organization.objects.get(pk=self.kwargs.get('pk'))
        data['pending'] = FInstance.objects.filter(project__organization=self.kwargs.get('pk'), form_status='0').order_by('-date')
        data['rejected'] = FInstance.objects.filter(project__organization=self.kwargs.get('pk'), form_status='1').order_by('-date')
        data['flagged'] = FInstance.objects.filter(project__organization=self.kwargs.get('pk'), form_status='2').order_by('-date')
        data['approved'] = FInstance.objects.filter(project__organization=self.kwargs.get('pk'), form_status='3').order_by('-date')
        data['type'] = self.kwargs.get('type')
        return data


class ProjectdataSubmissionView(ReadonlyProjectLevelRoleMixin, TemplateView):
    template_name = "fieldsight/projectdata_submission.html"

    def get_context_data(self, **kwargs):
        data = super(ProjectdataSubmissionView, self).get_context_data(**kwargs)
        data['obj'] = Project.objects.get(pk=self.kwargs.get('pk'))
        data['pending'] = FInstance.objects.filter(project_id=self.kwargs.get('pk'), project_fxf_id__isnull=False, form_status='0').order_by('-date')
        data['rejected'] = FInstance.objects.filter(project_id=self.kwargs.get('pk'), project_fxf_id__isnull=False, form_status='1').order_by('-date')
        data['flagged'] = FInstance.objects.filter(project_id=self.kwargs.get('pk'), project_fxf_id__isnull=False, form_status='2').order_by('-date')
        data['approved'] = FInstance.objects.filter(project_id=self.kwargs.get('pk'), project_fxf_id__isnull=False, form_status='3').order_by('-date')
        data['type'] = self.kwargs.get('type')
        data['is_donor_only'] = kwargs.get('is_donor_only', False)

        return data


class SitedataSubmissionView(ReadonlySiteLevelRoleMixin, TemplateView):
    template_name = "fieldsight/sitedata_submission.html"

    def get_context_data(self, **kwargs):
        data = super(SitedataSubmissionView, self).get_context_data(**kwargs)
        data['obj'] = Site.objects.get(pk=self.kwargs.get('pk'))
        data['pending'] = FInstance.objects.filter(site_id = self.kwargs.get('pk'), form_status = '0').order_by('-date')
        data['rejected'] = FInstance.objects.filter(site_id = self.kwargs.get('pk'), form_status = '1').order_by('-date')
        data['flagged'] = FInstance.objects.filter(site_id = self.kwargs.get('pk'), form_status = '2').order_by('-date')
        data['approved'] = FInstance.objects.filter(site_id = self.kwargs.get('pk'), form_status = '3').order_by('-date')
        data['type'] = self.kwargs.get('type')
        data['is_donor_only'] = kwargs.get('is_donor_only', False)

        return data


class RegionView(object):
    model = Region
    success_url = reverse_lazy('fieldsight:region-list')
    form_class = RegionForm


class RegionListView(RegionView, ProjectRoleMixin, ListView):
    def get_context_data(self, **kwargs):
        context = super(RegionListView, self).get_context_data(**kwargs)
        project = Project.objects.get(pk=self.kwargs.get('pk'))
        context['obj'] = project
        context['pk'] = self.kwargs.get('pk')
        context['type'] = "region"
        context["level"] = "1"
        context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        return context

    def get_queryset(self):
        queryset = Region.objects.filter(project_id=self.kwargs.get('pk'), is_active=True,
                                         parent=None)
        return queryset


class ProjectRegionSitesView(ProjectRoleMixin, ListView):
    model = Region
    template_name = "fieldsight/project_region_sites.html"

    def get_context_data(self, **kwargs):
        context = super(ProjectRegionSitesView, self).get_context_data(**kwargs)
        project = Project.objects.get(pk=self.kwargs.get('pk'))
        context['project'] = project
        context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        return context

    def get_queryset(self):
        if self.request.GET.get("q"):
            query = self.request.GET.get("q")
            queryset = Region.objects.filter(project_id=self.kwargs.get('pk'), parent=None, is_active=True).\
                filter(Q(name__icontains=query) | Q(identifier__icontains=query))
        else:
            queryset = Region.objects.filter(project_id=self.kwargs.get('pk'), parent=None, is_active=True)
        return queryset


class RegionCreateView(RegionView, ProjectRoleMixin, CreateView):
    def get_context_data(self, **kwargs):
        context = super(RegionCreateView, self).get_context_data(**kwargs)
        project = Project.objects.get(pk=self.kwargs.get('pk'))
        context['obj'] = project
        context['pk'] = self.kwargs.get('pk')
        context['level'] = "1"
        context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        if self.kwargs.get('parent_pk'):
            context['parent_identifier'] = Region.objects.get(pk=self.kwargs.get('parent_pk')).get_concat_identifier()
            print context['parent_identifier']
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)

        self.object.project_id = self.kwargs.get('pk')
        self.object.parent_id = self.kwargs.get('parent_pk')
        if self.kwargs.get('parent_pk'):
            parent_identifier = Region.objects.get(pk=self.kwargs.get('parent_pk')).get_concat_identifier()
            form.cleaned_data['identifier'] = parent_identifier + form.cleaned_data.get('identifier')
        
        existing_identifier = Region.objects.filter(identifier=form.cleaned_data.get('identifier'), project_id=self.kwargs.get('pk'))

        if existing_identifier:
            messages.add_message(self.request, messages.INFO, 'Your identifier conflict with existing region please use different identifier to create region')

            if not self.kwargs.get('parent_pk'):
                return HttpResponseRedirect(reverse(
                    'fieldsight:region-add',
                    kwargs={'pk': self.kwargs.get('pk')},
                ))
            else:
                return HttpResponseRedirect(reverse(
                    'fieldsight:sub-region-add',
                    kwargs={
                        'pk': self.kwargs.get('pk'),
                        'parent_pk': self.kwargs.get('parent_pk'),
                    }
                ))
        else:
            self.object.identifier = form.cleaned_data.get('identifier')
            self.object.save()
            if ProjectLevelTermsAndLabels.objects.filter(project=self.object.project).exists():
                region = ProjectLevelTermsAndLabels.objects.filter(project=self.object.project)[0].region
                messages.add_message(self.request, messages.INFO, 'Sucessfully new' + region + ' is created')
            else:
                messages.add_message(self.request, messages.INFO, 'Sucessfully new region is created')

            return HttpResponseRedirect(self.get_success_url())
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        if not self.kwargs.get('parent_pk'):
            return reverse(
                'fieldsight:region-list',
                kwargs={
                    'pk': self.kwargs.get('pk'),
                }
            )
        else:
            return reverse(
                'fieldsight:region-update',
                kwargs={
                    'pk': self.kwargs.get('parent_pk'),
                }
            )



class RegionDeleteView(RegionView, RegionRoleMixin, DeleteView):
    def dispatch(self, request, *args, **kwargs):
        site = Site.objects.filter(region_id=self.kwargs.get('pk'))
        site.update(region_id=None)
        return super(RegionDeleteView, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('fieldsight:region-list', kwargs={'pk': self.object.project.id})


# class RegionDeactivateView(View):
#
#     def get(self, request, pk, *args, **kwargs):
#         region = Region.objects.get(pk=pk)
#         project_id = region.project.id
#         site=Site.objects.filter(region_id=self.kwargs.get('pk'))
#         site.update(region=None)
#         region.is_active = False
#         region.save()
#
#         return HttpResponseRedirect(reverse('fieldsight:project-dashboard', kwargs={'pk':region.project.id}))


class RegionUpdateView(RegionView, RegionRoleMixin, UpdateView):

    def get_context_data(self, **kwargs):
        context = super(RegionUpdateView, self).get_context_data(**kwargs)
        region = Region.objects.get(pk=self.kwargs.get('pk'))
        context['obj'] = region.project
        context['pk'] = self.kwargs.get('pk')
        context['level'] = "1"
        context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=region.project).exists()

        context['subregion_list'] = Region.objects.filter(
            parent__pk=self.kwargs.get('pk')
        )
        region = Region.objects.get(pk=self.kwargs.get('pk'))
        if region.parent:
            context['parent_identifier'] = region.parent.get_concat_identifier()
            idfs = region.identifier.split('_')
            context['current_identifier'] = idfs[len(idfs)-1]
        return context

    def form_valid(self, form):
        def replace_idfs(region, previous_identifier, new_identifier):
            identifier = region.identifier
            identifiers =  identifier.split(previous_identifier)
            
            if len(identifiers) == 2:
                region.identifier = new_identifier+identifiers[1]
                region.save()

            for sub_region in region.children.all():
                replace_idfs(sub_region, previous_identifier, new_identifier)

        previous_identifier = Region.objects.get(pk=self.kwargs.get('pk')).identifier
        self.object = form.save(commit=False)
        if self.object.parent:
            parent_identifier = self.object.parent.get_concat_identifier()
            form.cleaned_data['identifier'] = parent_identifier + form.cleaned_data.get('identifier')

        existing_identifier = Region.objects.filter(identifier=form.cleaned_data.get('identifier'), project_id=self.object.project.id)
        check_identifier = previous_identifier == form.cleaned_data.get('identifier')

        if not check_identifier and existing_identifier:
            messages.add_message(self.request, messages.INFO, 'Your identifier "'+ form.cleaned_data.get('identifier') +'" conflict with existing region please use different identifier to update region')
            return HttpResponseRedirect(reverse(
                'fieldsight:region-update',
                kwargs={
                    'pk': self.object.pk,
                }
            ))
        else:
            self.object.identifier = form.cleaned_data.get('identifier')
            self.object.save()
            for sub_region in self.object.children.all():
                replace_idfs(sub_region, previous_identifier, self.object.identifier)
            messages.add_message(self.request, messages.INFO, 'Sucessfully saved.')
        
        if self.object.parent:
            return HttpResponseRedirect(reverse(
                'fieldsight:region-update',
                kwargs={
                    'pk': self.object.parent.pk,
                }
            ))
        else:
            return HttpResponseRedirect(reverse(
                'fieldsight:region-list',
                kwargs={
                    'pk': self.object.project_id,
                }
            ))


class RegionalSitelist(RegionSupervisorReviewerMixin, ListView):
    model = Site
    template_name = 'fieldsight/site_list.html'
    paginate_by = 90

    def get_context_data(self, **kwargs):
        context = super(RegionalSitelist, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['region_id'] = self.kwargs.get('region_id')
        context['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project_id=self.kwargs.get('pk')).exists()
        context['project'] = get_object_or_404(Project, id=self.kwargs.get('pk'))

        if self.kwargs.get('region_id') == "0":
            context['type'] = "Unregioned"
            context['project_id'] = self.kwargs.get('pk')
        else:
            context['type'] = "region"
            context['obj'] = get_object_or_404(Region, id=self.kwargs.get('region_id'))
        return context

    def get_queryset(self, **kwargs):
        queryset = Site.objects.filter(project_id=self.kwargs.get('pk'),
                                       is_survey=False, is_active=True).select_related('project')
        
        if self.kwargs.get('region_id') == "0":
            object_list = queryset.filter(region=None)
        else:    
            object_list = queryset.filter(region_id=self.kwargs.get('region_id'))
        return object_list


class DonorRegionalSitelist(ReadonlyProjectLevelRoleMixin, ListView):
    model = Site
    template_name = 'fieldsight/donor_site_list.html'
    paginate_by = 90

    def get_context_data(self, **kwargs):
        context = super(DonorRegionalSitelist, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['region_id'] = self.kwargs.get('region_id')
        context['is_donor_only'] = kwargs.get('is_donor_only', False)
        if self.kwargs.get('region_id') == "0":
            context['type'] = "Unregioned"
            context['project_id'] = self.kwargs.get('pk')
        else:
            context['type'] = "region"
            context['obj'] = get_object_or_404(Region, id=self.kwargs.get('region_id'))
        return context
    def get_queryset(self, **kwargs):
        queryset = Site.objects.filter(project_id=self.kwargs.get('pk'), is_survey=False, is_active=True)
        
        if self.kwargs.get('region_id') == "0":
            object_list = queryset.filter(region=None)
        else:    
            object_list = queryset.filter(region_id=self.kwargs.get('region_id'))
        return object_list

# class RegionalSitelist(ProjectRoleMixin, TemplateView):
#     def get(self, request, *args, **kwargs):
#         queryset = Site.objects.filter(project_id=self.kwargs.get('pk'), is_survey=False, is_active=True)
#         if self.kwargs.get('region_id') == "0":
#             object_list = queryset.filter(region=None)
#         else:    
#             object_list = queryset.filter(region_id=self.kwargs.get('region_id'))
#         if self.kwargs.get('region_id') == "0":
#             return render(request, 'fieldsight/site_list.html',{'object_list':object_list, 'project_id':self.kwargs.get('pk'),'type':"Unregioned", 'pk': self.kwargs.get('pk'),'region_id':self.kwargs.get('region_id'),})
        
#         obj = get_object_or_404(Region, id=self.kwargs.get('region_id'))
#         return render(request, 'fieldsight/site_list.html',{'object_list':object_list, 'obj':obj, 'type':"region", 'pk': self.kwargs.get('pk'), 'region_id':self.kwargs.get('region_id'),})

# class RegionalSitelist(ProjectRoleMixin, ListView):
#     paginate_by = 10
#     def get(self, request, *args, **kwargs):
#         if self.kwargs.get('region_pk') == "0":
#             sites = Site.objects.filter(region=None)
#             return render(request, 'fieldsight/site_list.html' ,{'all_sites':sites, 'project_id':self.kwargs.get('pk'),'type':"Unregioned",'pk':self.kwargs.get('region_pk'),})

#         obj = get_object_or_404(Region, id=self.kwargs.get('region_pk'))
#         sites = Site.objects.filter(region_id=self.kwargs.get('region_pk'))
#         return render(request, 'fieldsight/site_list.html',{'all_sites':sites, 'obj':obj, 'type':"region",'pk':self.kwargs.get('region_pk'),})


class RegionalSiteCreateView(SiteView, RegionSupervisorReviewerMixin, CreateView):

    def get_context_data(self, **kwargs):
        context = super(RegionalSiteCreateView, self).get_context_data(**kwargs)
        project =Project.objects.get(pk=self.kwargs.get('pk'))
        context['project'] = project
        context['json_questions'] = json.dumps(project.site_meta_attributes)
        context['pk'] = self.kwargs.get('pk')
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()
        context['labels'] = terms_and_labels
        context['region'] = project.cluster_sites


        if terms_and_labels:

            context['site_name'] = project.terms_and_labels.site
            context['region_name'] = project.terms_and_labels.region

        else:
            context['site_name'] = "Site"
            context['region_name'] = "Region"

        return context

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_form(self, *args, **kwargs):
        form = super(RegionalSiteCreateView, self).get_form(*args, **kwargs)
        project = Project.objects.get(pk=self.kwargs.get('pk'))
        form.fields['region'].queryset = form.fields['region'].queryset.filter(project=project)
        del form.fields['weight']
        return form

    def form_valid(self, form):
        self.object = form.save(project_id=self.kwargs.get('pk'),
                                region_id=self.kwargs.get('region_pk'),
                                new=True, weight=0)
        noti = self.object.logs.create(source=self.request.user, type=11, title="new Site",
                                       organization=self.object.project.organization,
                                       project=self.object.project, content_object=self.object, extra_object=self.object.project,
                                       description=u'{0} created a new site '
                                                   u'named {1} in {2}'.format(self.request.user.get_full_name(),
                                                                                 self.object.name, self.object.project.name))

        return HttpResponseRedirect(self.get_success_url())

#
# class MultiUserAssignRegionView(ProjectRoleMixin, TemplateView):
#     def get(self, request, pk):
#         project_obj = Project.objects.get(pk=pk)
#         return render(request, 'fieldsight/multi_user_assign.html',{'type': "site", 'pk':pk})
#
#     def post(self, request, pk, *args, **kwargs):
#         data = json.loads(self.request.body)
#         # import ipdb; ipdb.set_trace()
#         regions = data.get('regions')
#         users = data.get('users')
#         group = Group.objects.get(name=data.get('group'))
#         user = request.user
#         project = get_object_or_404(Project, pk=pk, is_active=True)
#         task_obj = CeleryTaskProgress.objects.create(user=user, content_object = project, task_type=2)
#         if task_obj:
#             task = multiuserassignregion.delay(task_obj.pk, pk, regions, users, group.id)
#             task_obj.task_id = task.id
#             task_obj.save()
#             return HttpResponse('sucess')
#         else:
#             return HttpResponse('Failed')


class MultiUserAssignRegionView(ProjectRoleMixin, TemplateView):

    def get(self, request, pk):
        project_obj = Project.objects.get(pk=pk)
        return render(request, 'fieldsight/multi_user_assign.html',{'type': "site", 'pk':pk})

    def post(self, request, pk, *args, **kwargs):
        data = json.loads(self.request.body)
        regions = data.get('regions')
        users = data.get('users')
        group = Group.objects.get(name=data.get('group'))

        user = request.user
        project = get_object_or_404(Project, pk=pk, is_active=True)
        task_obj = CeleryTaskProgress.objects.create(user=user, content_object=project, task_type=2)
        if task_obj:
            task = multiuserassignregion.delay(task_obj.pk, pk, regions, users, group.id)
            task_obj.task_id = task.id
            task_obj.save()
            return HttpResponse('sucess')
        else:
            return HttpResponse('Failed')


class AssignUsersToRegionsView(ProjectRoleMixin, TemplateView):
    """
    Assign multiple users to multiple regions as Region Supervisor or Region Reviewer if project has cluster_sites
    """

    def get(self, request, pk):
        project_obj = Project.objects.get(pk=pk)
        return render(request, 'fieldsight/multi_user_assign.html',{'type': "site", 'pk':pk})

    def post(self, request, pk, *args, **kwargs):
        data = json.loads(self.request.body)

        regions = data.get('regions')
        users = data.get('users')
        group = Group.objects.get(name=data.get('group'))

        user = request.user
        project = get_object_or_404(Project, pk=pk, is_active=True)

        task_obj = CeleryTaskProgress.objects.create(user=user, content_object=project, task_type=13)

        if task_obj:
            task = multi_users_assign_regions.delay(task_obj.pk, pk, regions, users, group.id)
            task_obj.task_id = task.id
            task_obj.save()
            return HttpResponse('Success')
        else:
            return HttpResponse('Failed')


class AssignUsersToEntireProjectView(ProjectRoleMixin, TemplateView):
    """
    Assign multiple users to entire project, if project has cluster_sites
    """

    def get(self, request, pk):
        project_obj = Project.objects.get(pk=pk)
        return render(request, 'fieldsight/multi_user_assign.html',{'type': "site", 'pk':pk})

    def post(self, request, pk, *args, **kwargs):
        data = json.loads(self.request.body)

        users = data.get('users')

        user = request.user
        project = get_object_or_404(Project, pk=pk, is_active=True)
        regions = project.project_region.all().values_list('id', flat=True)
        unassigned_sites = project.sites.filter(region=None).values_list('id', flat=True)

        task_obj = CeleryTaskProgress.objects.create(user=user, content_object=project, task_type=14)

        if task_obj:
            task = multi_users_assign_to_entire_project.delay(task_obj.pk, pk, regions, users, unassigned_sites)
            task_obj.task_id = task.id
            task_obj.save()
            return HttpResponse('Success')
        else:
            return HttpResponse('Failed')


def project_html_export(request, pk):
    
    # site_responses_report(forms)
    # # data = {}
    # # for fsxf in forms:
    # #     data['form_detail'] = fsxf
    # #     xform = fsxf.xf
    # #     id_string = xform.id_string
    # #     data['form_responces'] = get_instances_for_project_field_sight_form(fsxf_id)
    # forms = Organization.objects.all()
    buffer = BytesIO()
    site = Site.objects.get(pk=pk)
    response = HttpResponse(content_type='application/pdf')
    file_name=site.name +"_summary.pdf"
    response['Content-Disposition'] = 'attachment; filename="'+file_name+'"'
    base_url = request.get_host()
    report = PDFReport(buffer, 'Letter')
    pdf = report.generateFullReport(pk, base_url)

    buffer.seek(0)

    #     with open('arquivo.pdf', 'wb') as f:
    #         f.write()
    response.write(buffer.read())

    # Get the value of the BytesIO buffer and write it to the response.
    pdf = buffer.getvalue()
    buffer.close()

    return response

class OrganizationSearchView(ListView):
    model = Organization
    template_name = 'fieldsight/organization_list.html'

    def get_queryset(self):
        query = self.request.GET.get("q")
        return self.model.objects.filter(name__icontains=query)


class ProjectSearchView(ListView):
    model = Project
    template_name = 'fieldsight/project_list.html'

    def get_context_data(self, **kwargs):
        context = super(ProjectSearchView, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['type'] = "project"
        return context

    def get_queryset(self):
        query = self.request.GET.get("q")
        return self.model.objects.filter(name__icontains=query)


class OrganizationUserSearchView(ListView):
    model = UserRole
    template_name = "fieldsight/user_list_updated.html"

    def get_context_data(self, **kwargs):
        context = super(OrganizationUserSearchView, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        return context

    def get_queryset(self):
        query = self.request.GET.get("q")
        return self.model.objects.filter(organization_id=self.kwargs.get('pk'), ended_at__isnull=True).\
            filter(Q(user__username__icontains=query) | Q(user__first_name__icontains=query) |
                   Q(user__last_name__icontains=query) | Q(user__email__icontains=query)).distinct('user')


class ProjectUserSearchView(ListView):
    model = UserRole
    template_name = "fieldsight/user_list_updated.html"

    def get_context_data(self, **kwargs):
        context = super(ProjectUserSearchView, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['obj'] = Project.objects.get(pk=self.kwargs.get('pk'))
        context['organization_id'] = Project.objects.get(pk=self.kwargs.get('pk')).organization.id
        context['type'] = "project"
        return context

    def get_queryset(self):
        query = self.request.GET.get("q")
        return self.model.objects.select_related('user').filter(project_id=self.kwargs.get('pk'), ended_at__isnull=True).\
            filter(Q(user__username__icontains=query) | Q(user__first_name__icontains=query) |
                   Q(user__last_name__icontains=query) | Q(user__email__icontains=query)).distinct('user_id')


class SiteUserSearchView(ListView):
    model = UserRole
    template_name = "fieldsight/user_list_updated.html"

    def get_context_data(self, **kwargs):
        context = super(SiteUserSearchView, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['obj'] = Site.objects.get(pk=self.kwargs.get('pk'))
        context['organization_id'] = Site.objects.get(pk=self.kwargs.get('pk')).project.organization.id
        context['type'] = "site"
        return context

    def get_queryset(self):
        query = self.request.GET.get("q")
        project = Site.objects.get(pk=self.kwargs.get('pk')).project
        return self.model.objects.select_related('user').filter(ended_at__isnull=True).\
            filter(Q(site_id=self.kwargs.get('pk')) | Q(region__project=project)).\
            filter(Q(user__username__icontains=query) | Q(user__first_name__icontains=query) |
                   Q(user__last_name__icontains=query) | Q(user__email__icontains=query)).distinct('user_id')



class DefineProjectSiteMeta(RegionSupervisorReviewerMixin, TemplateView):
    def get(self, request, pk):
        project_obj = Project.objects.get(pk=pk)
        level = "1"
        json_questions = json.dumps(project_obj.site_meta_attributes)
        site_basic_info = json.dumps(project_obj.site_basic_info)
        site_featured_images = json.dumps(project_obj.site_featured_images)
        
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=project_obj).exists()

        return render(request, 'fieldsight/project_define_site_meta.html', {'obj': project_obj, 'json_questions':
            json_questions, 'level': level, 'site_basic_info': site_basic_info, 'site_featured_images': site_featured_images, 'terms_and_labels': terms_and_labels})


    def post(self, request, pk, *args, **kwargs):
        project = Project.objects.get(pk=pk)
        old_meta = project.site_meta_attributes
        # print old_meta===================================
        # print "----"
        project.site_meta_attributes = request.POST.get('json_questions');
        project.site_basic_info = request.POST.get('site_basic_info');
        project.site_featured_images = request.POST.get('site_featured_images');
        new_meta = json.loads(project.site_meta_attributes)
        # print new_meta
        updated_json = None
        if old_meta != new_meta:
            deleted = []

            for meta in old_meta:
                if meta not in new_meta:
                    deleted.append(meta)

            for other_project in Project.objects.filter(organization_id=project.organization_id):
                
                for meta in other_project.site_meta_attributes:
                
                    if meta['question_type'] == "Link":
                        if str(project.id) in meta['metas']:
                            for del_meta in deleted:
                                if del_meta in meta['metas'][str(project.id)]:
                                    del meta['metas'][str(project.id)][meta['metas'][str(project.id)].index(del_meta)]
                
                other_project.save()
        project.save()
        return HttpResponseRedirect(reverse('fieldsight:project-dashboard', kwargs={'pk': self.kwargs.get('pk')}))


class SiteMetaForm(ReviewerRoleMixin, TemplateView):
    def get(self, request, pk):
        site_obj = Site.objects.get(pk=pk)
        json_answers = json.dumps(site_obj.site_meta_attributes_ans)
        json_questions = json.dumps(site_obj.project.site_meta_attributes)
        return render(request, 'fieldsight/site_meta_form.html', {'obj': site_obj, 'json_questions': json_questions, 'json_answers': json_answers})

    def post(self, request, pk, *args, **kwargs):
        project = Project.objects.get(pk=pk)
        project.site_meta_attributes = request.POST.get('json_questions');
        project.save()
        return HttpResponseRedirect(reverse('fieldsight:project-dashboard', kwargs={'pk': self.kwargs.get('pk')}))

class MultiSiteAssignRegionView(ProjectRoleMixin, TemplateView):
    def get(self, request, pk):
        project = get_object_or_404(Project, id=pk)
        level = "1"

        if project.cluster_sites is False:
            raise PermissionDenied()

        return render(request, 'fieldsight/multi_site_assign_region.html', {'project':project})

    def post(self, request, pk, *args, **kwargs):
        data = json.loads(self.request.body)
        region = data.get('region')
        sites = data.get('sites')
        if len(region) == 0:
            sitetoassign = Site.objects.filter(pk__in=sites)
            sitetoassign.update(region=None)
        else:        
            sitetoassign = Site.objects.filter(pk__in=sites)
            sitetoassign.update(region_id=region[0])

        return HttpResponse("Success")


class ExcelBulkSiteSample(ProjectRoleMixin, View):
    def get(self, request, pk, edit=0):
        source_user = self.request.user   
        project = get_object_or_404(Project, pk=self.kwargs.get('pk'))
        terms_and_labels = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        content_type = ContentType.objects.get(model='project', app_label='fieldsight')
        regions = request.GET.get('regions', None)

        if edit == 0:
            response = HttpResponse(content_type='application/ms-excel')
            response['Content-Disposition'] = 'attachment; filename="bulk_upload_sites.xls"'

            wb = xlwt.Workbook(encoding='utf-8')
            ws = wb.add_sheet('Sites')

            # Sheet header, first row
            row_num = 0

            font_style = xlwt.XFStyle()
            font_style.font.bold = True

            columns = ['identifier', 'name', 'type', 'phone', 'address', 'public_desc', 'additional_desc', 'latitude', 'longitude', 'root_site_identifier']
            if project.cluster_sites:
                columns += ['region_identifier',]
            meta_ques = project.site_meta_attributes
            for question in meta_ques:
                columns += [question['question_name']]
            for col_num in range(len(columns)):
                ws.write(row_num, col_num, columns[col_num], font_style)

            # Sheet body, remaining rows
            font_style = xlwt.XFStyle()

            wb.save(response)
            return response

        if regions:
            regions = regions.split(',')
        task_obj = CeleryTaskProgress.objects.create(user=source_user, content_object=project, task_type=8)
        if task_obj:
            task = generateSiteDetailsXls.delay(task_obj.pk, self.kwargs.get('pk'), regions)
            task_obj.task_id = task.id
            task_obj.save()
            if terms_and_labels:
                messages.info(request, 'The '+ project.terms_and_labels.site +' details xls file is being generated. You will be notified after the file is generated.')
            else:
                messages.info(request, 'The sites details xls file is being generated. You will be notified after the file is generated.')


        else:
            messages.info(request, 'Error occured please try again.')

        return HttpResponseRedirect(reverse('fieldsight:site-upload', kwargs={'pk': project.pk}))

    def write_site(self, row, site, ws):
        columns = [
            site.identifier,
            site.name,
            site.type and site.type.identifier,
            site.phone,
            site.address,
            site.public_desc,
            site.additional_desc,
            site.latitude,
            site.longitude,
        ]

        if site.project.cluster_sites:
            columns += [site.region and site.region.identifier]

        meta_ques = site.project.site_meta_attributes
        meta_ans = site.site_meta_attributes_ans

        if not isinstance(meta_ans, dict):
            meta_ans = None

        for question in meta_ques:
            columns += [
                meta_ans.get(question['question_name'], '') if meta_ans else ''
            ]

        for col in range(len(columns)):
            ws.write(row, col, columns[col] or '')


class SiteSearchView(ListView):
    model = Site
    template_name = 'fieldsight/site_list.html'
    paginate_by = 90

    def get_context_data(self, **kwargs):
        context = super(SiteSearchView, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['region_id'] = self.kwargs.get('region_id', None)
        return context

    def get_queryset(self, **kwargs):
        region_id = self.kwargs.get('region_id', None)
        # import pdb; pdb.set_trace()
        query = self.request.GET.get('q')
        if query:

            if region_id:
                if region_id == "0":
                    filtered_objects = self.model.objects.filter(region=None, project_id=self.kwargs.get('pk'))

                else:
                    filtered_objects = self.model.objects.filter(region_id=region_id, project_id=self.kwargs.get('pk'))
            else:
                filtered_objects = self.model.objects.filter(project_id=self.kwargs.get('pk'))
            # import pdb; pdb.set_trace()
            return filtered_objects.filter(Q(name__icontains=query) | Q(identifier__icontains=query))
        else:
            return Site.objects.none()


class SiteSearchLiteView(ListView):
    model = Site
    template_name = 'fieldsight/donor_site_list.html'
    paginate_by = 90

    def get_context_data(self, **kwargs):
        context = super(SiteSearchLiteView, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['region_id'] = self.kwargs.get('region_id', None)
        return context

    def get_queryset(self, **kwargs):
        region_id = self.kwargs.get('region_id', None)
        query = self.request.GET.get('q')

        if query:
            if region_id:
                if region_id == "0":
                    filtered_objects = self.model.objects.filter(region=None, project_id=self.kwargs.get('pk'))

                else:
                    filtered_objects = self.model.objects.filter(region_id=region_id, project_id=self.kwargs.get('pk'))
            else:
                filtered_objects = self.model.objects.filter(project_id=self.kwargs.get('pk'))
            return filtered_objects.filter(Q(name__icontains=query) | Q(identifier__icontains=query))
        else:
            return Site.objects.none()

# def get_project_stage_status(request, pk, q_keyword,page_list):
#     data = []
#     ss_id = []
#     stages_rows = []
#     head_row = ["Site ID", "Name"]
#     project = get_object_or_404(Project, pk=pk)
    
#     stages = project.stages.filter(stage__isnull=True).prefetch_related('parent')
    
#     table_head = []
#     substages =[]
#     table_head.append({"name":"Site Id", "rowspan":2, "colspan":1 })
#     table_head.append({"name":"Site Name", "rowspan":2, "colspan":1 })
    
#     stage_count=0
#     for stage in stages:
#         stage_count+=1

#         sub_stages = stage.parent.filter(stage_forms__is_deleted=False)
#         if len(sub_stages) > 0:
#             stages_rows.append("Stage :"+stage.name)
#             table_head.append({"name":stage.name, "stage_order": "Stage " +str(stage_count), "rowspan":1, "colspan":len(sub_stages) })
#             sub_stage_count=0
#             for ss in sub_stages:
#                 sub_stage_count+=1
#                 head_row.append("Sub Stage :"+ss.name)
#                 ss_id.append(ss.id)
#                 substages.append([ss.name, str(stage_count)+"."+str(sub_stage_count)])

    

#     # data.append(head_row)
#     def filterbyvalue(seq, value):
#         for el in seq:
#             if el.project_stage_id==value: yield el

#     def getStatus(el):
#         if el is not None and el.form_status==3: return "Approved", "cell-success" 
#         elif el is not None and el.form_status==2: return "Flagged", "cell-warning"
#         elif el is not None and el.form_status==1: return "Rejected", "cell-danger"
#         else: return "Pending", "cell-primary"
#     if q_keyword is not None:
#         site_list = project.sites.filter(name__icontains=q_keyword, is_active=True, is_survey=False).prefetch_related(Prefetch('stages__stage_forms__site_form_instances', queryset=FInstance.objects.order_by('-id')))
#         get_params = "?q="+q_keyword +"&page="
#     else:
#         site_list_pre = FInstance.objects.filter(project_id=pk, project_fxf_id__is_staged=True, site__is_active=True, site__is_survey=False).distinct('site_id').order_by('site_id').only('pk')
#         # site_list = Site.objects.get()

#         FInstance.objects.filter(pk__in=site_list_pre).order_by('-id').prefetch_related(Prefetch('project__stages__stage_forms__project_form_instances', queryset=FInstance.objects.filter().order_by('-id')))
#         get_params = "?page="
#     paginator = Paginator(site_list, page_list) # Show 25 contacts per page
#     page = request.GET.get('page')
#     try:
#         sites = paginator.page(page)
#     except PageNotAnInteger:
#         # If page is not an integer, deliver first page.
#         sites = paginator.page(1)
#     except EmptyPage:
#     # If page is out of range (e.g. 9999), deliver last page of results.
#         sites = paginator.page(paginator.num_pages)
#     for site in sites:
#         site_row = ["<a href='"+site.site.get_absolute_url()+"'>"+site.site.identifier+"</a>", "<a href='"+site.site.get_absolute_url()+"'>"+site.site.name+"</a>"]
#         for v in ss_id:

#             substage = filterbyvalue(site.site.stages.all(), v)
#             substage1 = next(substage, None)
#             if substage1 is not None:
#                 if  substage1.stage_forms.site_form_instances.all():
#                      get_status = getStatus(substage1.stage_forms.site_form_instances.all()[0])
#                      status, style_class = get_status
#                      submission_count = substage1.stage_forms.site_form_instances.all().count()
#                 else:
#                     status, style_class = "No submission.", "cell-inactive"
#                     submission_count = 0
#             else:
#                  status, style_class = "-", "cell-inactive"
#                  submission_count = 0
#             site_row.append([status, submission_count, style_class])
        
#         data.append(site_row)

#     if sites.has_next():
#         next_page_url = request.build_absolute_uri(reverse('fieldsight:ProjectStageResponsesStatus', kwargs={'pk': pk})) + get_params + str(sites.next_page_number())
#     else:
#         next_page_url =  None
#     content={'head_cols':table_head, 'sub_stages':substages, 'rows':data}
#     main_body = {'next_page':next_page_url,'content':content}
#     return main_body


def get_project_stage_status(request, pk, q_keyword,page_list):
    data = []
    ss_id = []
    ss_id_string = []
    stats = {}
    stages_rows = []
    stats = {}
    head_row = ["Site ID", "Name"]
    project = get_object_or_404(Project, pk=pk, is_active=True)
    
    stages = project.stages.filter(stage__isnull=True).prefetch_related('parent')
    
    table_head = []
    substages =[]
    table_head.append({"name":"Site Id", "rowspan":2, "colspan":1 })
    table_head.append({"name":"Site Name", "rowspan":2, "colspan":1 })
    
    stage_count=0
    for stage in stages:
        stage_count+=1

        sub_stages = stage.parent.filter(stage_forms__is_deleted=False)
        if len(sub_stages) > 0:
            stages_rows.append("Stage :"+stage.name)
            table_head.append({"name":stage.name, "stage_order": "Stage " +str(stage_count), "rowspan":1, "colspan":len(sub_stages) })
            sub_stage_count=0
            for ss in sub_stages:
                sub_stage_count+=1
                head_row.append("Sub Stage :"+ss.name)
                ss_id.append(ss.id)
                ss_id_string.append(str(ss.stage_forms.id))
                substages.append([ss.name, str(stage_count)+"."+str(sub_stage_count)])

    table_head.extend([{"name":"Site Visits", "rowspan":2, "colspan":1 }, {"name":"Total Submissions", "rowspan":2, "colspan":1 }, {"name":"Flagged Submissions", "rowspan":2, "colspan":1 }, {"name":"Rejected Submissions", "rowspan":2, "colspan":1 }])


    # data.append(head_row)
    def filterbyvalue(seq, value):
        for el in seq:
            if el.id==value: yield el



    def getStatus(datas, site_id):
        el = None
        count = 0 
        for data in datas:
            
            if data.site_id == site_id:
                if el is None:
                    el = data
                count += 1

        if el is not None and el.form_status==3: return "Approved", "cell-success", count 
        elif el is not None and el.form_status==2: return "Flagged", "cell-warning", count 
        elif el is not None and el.form_status==1: return "Rejected", "cell-danger", count
        elif el is not None and el.form_status==0: return "Pending", "cell-primary", count
        else: return "No submission", "cell-inactive", count

    def setStatistics(submissions):
        for sub in submissions:
            if sub.site:
                if not sub.site_id in stats:
                    stats[sub.site_id] = {}

                if sub.form_status == 1:
                    stats[sub.site_id]['rejected'] = stats.get(sub.site_id, {}).get('rejected', 0) + 1
                elif sub.form_status == 2:
                    stats[sub.site_id]['flagged'] = stats.get(sub.site_id, {}).get('flagged', 0) + 1

                stats[sub.site_id]['submission_count'] = stats.get(sub.site_id, {}).get('submission_count', 0) + 1
                stats[sub.site_id]['submission_dates'] = stats.get(sub.site_id, {}).get('submission_dates', []) + [sub.date.date()]

    if q_keyword is not None:
        site_list = Site.objects.filter(project_id=pk, name__icontains=q_keyword, is_active=True, is_survey=False)
        get_params = "?q="+q_keyword +"&page="
    else:
        site_list_pre = FInstance.objects.filter(project_id=pk, project_fxf_id__is_staged=True, site__is_active=True, site__is_survey=False).distinct('site_id').order_by('site_id').values('site_id')
        site_list = Site.objects.filter(pk__in=site_list_pre)

        
        # FInstance.objects.filter(pk__in=site_list_pre).order_by('-id').prefetch_related(Prefetch('project__stages__stage_forms__project_form_instances', queryset=FInstance.objects.filter().order_by('-id')))
        get_params = "?page="
    
    
    paginator = Paginator(site_list, page_list) # Show how many contacts per page
    page = request.GET.get('page')
    try:
        sites = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        sites = paginator.page(1)
    except EmptyPage:
    # If page is out of range (e.g. 9999), deliver last page of results.
        sites = paginator.page(paginator.num_pages)

    stages = Stage.objects.filter(stage__isnull=False, stage__project_id=pk).prefetch_related(Prefetch('stage_forms__project_form_instances', queryset=FInstance.objects.filter(site_id__in=sites, project_fxf_id__in=ss_id_string).order_by('-pk')))
    
    site_ids = []
    for site in sites:
        site_ids.append(str(site.id))
    
    site_visits = settings.MONGO_DB.instances.aggregate([{"$match":{"fs_site": {"$in": list(site_ids) }, "fs_project_uuid": {"$in":ss_id_string}}},  { "$group" : { 
                  "_id" :  { 
                    "fs_site": "$fs_site",
                    "date": { "$substr": [ "$start", 0, 10 ] }
                  },
               }
             }, { "$group": { "_id": "$_id.fs_site", "visits": { 
                      "$push": { 
                          "date":"$_id.date"
                      }          
                 }
             }}], cursor={})
    site_visits = list(site_visits)
    
    def filterMongolist(value):
        for el in site_visits:
            if el['_id'] == value: return el

    
    setStatisticsChecker=[]
    for site in sites:

        site_row = ["<a href='"+site.get_absolute_url()+"'>"+site.identifier+"</a>", "<a href='"+site.get_absolute_url()+"'>"+site.name+"</a>"]
        

        for v in ss_id:
            substage = filterbyvalue(stages, v)
            substage1 = next(substage, None)
            

            if substage1 is not None:
            
                if substage1.stage_forms.project_form_instances.all():
                    
                    if substage1.id not in setStatisticsChecker:
                        setStatistics(substage1.stage_forms.project_form_instances.all())
                        setStatisticsChecker.append(substage1.id)
                    status, style_class, submission_count = getStatus(substage1.stage_forms.project_form_instances.all(), site.id)
                     
                else:
                    status, style_class = "No submission.", "cell-inactive"
                    submission_count = 0
            else:
                 status, style_class = "-", "cell-inactive"
                 submission_count = 0
            
            site_row.append([status, submission_count, style_class])
        visits = filterMongolist(str(site.id))
        site_row.append([status, len(visits['visits']) if visits else 0, "cell-inactive"])
        site_row.append([status, stats.get(site.id, {}).get('submission_count', 0), "cell-inactive"])
        
        if 'flagged' in stats.get(site.id, {}):
            site_row.append([status, stats.get(site.id, {}).get('flagged', 0), "cell-warning"])
        else:
            site_row.append([status, 0, "cell-inactive"])

        if 'rejected' in stats.get(site.id, {}):
            site_row.append([status, stats.get(site.id, {}).get('rejected', 0), "cell-danger"])
        else:
            site_row.append([status, 0, "cell-inactive"])            
        data.append(site_row)

    if sites.has_next():
        next_page_url = request.build_absolute_uri(reverse('fieldsight:ProjectStageResponsesStatus', kwargs={'pk': pk})) + get_params + str(sites.next_page_number())
    else:
        next_page_url =  None
    content={'head_cols':table_head, 'sub_stages':substages, 'rows':data}
    main_body = {'next_page':next_page_url,'content':content}
    return main_body

class ProjectStageResponsesStatus(DonorRoleMixin, View): 
    def get(self, request, pk):
        q_keyword = self.request.GET.get("q", None)
        stage_data = get_project_stage_status(request, pk, q_keyword, page_list=15)
        return HttpResponse(json.dumps(stage_data), status=200)


class ProjectDashboardStageResponsesStatus(DonorRoleMixin, View): 
    def get(self, request, pk):
        q_keyword = self.request.GET.get("q", None)
        stage_data = get_project_stage_status(request, pk, q_keyword, page_list=8)
        return HttpResponse(json.dumps(stage_data), status=200)

class StageTemplateView(ReadonlyProjectLevelRoleMixin, View):
    def get(self, request, pk, **kwargs):
        obj = Project.objects.get(pk=pk)
        return render(request, 'fieldsight/ProjectStageResponsesStatus.html', {'obj':obj,})
            # return HttpResponse(table_head)\

def response_export(request, pk, remove_null_fields):
    
    buffer = BytesIO()
    response = HttpResponse(content_type='application/pdf')
    instance = FInstance.objects.get(instance_id=pk)
    if instance.site_fxf:
        form = instance.site_fxf
    else:
        form = instance.project_fxf
    file_name= form.xf.title +"_response.pdf"
    response['Content-Disposition'] = 'attachment; filename="'+ file_name +'"'
    base_url = request.get_host()
    report = PDFReport(buffer, 'Letter')
    pdf = report.print_individual_response(pk, base_url, remove_null_fields)

    buffer.seek(0)

    #     with open('arquivo.pdf', 'wb') as f:
    #         f.write()
    response.write(buffer.read())

    # Get the value of the BytesIO buffer and write it to the response.
    pdf = buffer.getvalue()
    buffer.close()

    return response

class FormlistAPI(View):
    def get(self, request, pk):
        site=get_object_or_404(Site, pk=pk, is_active=True)
        mainstages=[]
        stages = Stage.objects.filter(stage__isnull=True).filter(Q(site_id=pk, project_stage_id=0) | Q(project_id=site.project_id)).order_by('order', 'date_created')
        
        for stage in stages:
            if stage.stage_id is None:
                substages=stage.get_sub_stage_list()
                main_stage = {'id':stage.id, 'title':stage.name, 'sub_stages':list(substages)}
                # stagegroup = {'main_stage':main_stage,}
                mainstages.append(main_stage)
        
        generals = FieldSightXF.objects.filter(is_staged=False, is_deleted=False, is_scheduled=False,  is_survey=False).filter(Q(site_id=pk, from_project=False)| Q(project_id=site.project_id)).values('id','xf__title')

        schedules = FieldSightXF.objects.filter(is_deleted=False, schedule__isnull=False).filter(Q(schedule__site_id=pk, from_project=False) | Q(schedule__project_id=site.project_id)).values('id','schedule__name')

        content={'general':list(generals), 'schedule':list(schedules), 'stage':list(mainstages)}

        return JsonResponse(content, status=200)

    def post(self, request, pk, **kwargs):
        base_url = request.get_host()
        data = json.loads(self.request.body)
        fs_ids = data.get('fs_ids')
        start_date = data.get('startdate')
        end_date = data.get('enddate')
        removeNullField = data.get('removeNullField', False)
        site = get_object_or_404(Site, pk=pk, is_active=True)

        task_obj=CeleryTaskProgress.objects.create(user=request.user, content_object = site, task_type=9)
        if task_obj:
            task = generateCustomReportPdf.delay(task_obj.id, pk, base_url, fs_ids, start_date, end_date, removeNullField)
            task_obj.task_id = task.id
            task_obj.save()
            status, data = 200, {'status':'True','message':'Sucess, the report is being generated. You will be notified after the report is generated. '}
        else:
            status, data = 401, {'status':'false','message':'Error occured try again.'}
        return JsonResponse(data, status=status)

class GenerateCustomReport(ReadonlySiteLevelRoleMixin, View):
    def get(self, request, pk, **kwargs):
        schedule = FieldSightXF.objects.filter(site_id=pk, is_scheduled = True, is_staged=False, is_survey=False).values('id','xf__title','date_created')
        stage = FieldSightXF.objects.filter(site_id=pk, is_scheduled = False, is_staged=True, is_survey=False).values('id','xf__title','date_created')
        survey = FieldSightXF.objects.filter(site_id=pk, is_scheduled = False, is_staged=False, is_survey=True).values('id','xf__title','date_created')
        general = FieldSightXF.objects.filter(site_id=pk, is_scheduled = False, is_staged=False, is_survey=False).values('id','xf__title','date_created')
        content={'general':list(general), 'schedule':list(schedule), 'stage':list(stage), 'survey':list(survey)}
        return JsonResponse(json.dumps(content, cls=DjangoJSONEncoder, ensure_ascii=False).encode('utf8'), status=200)


class RecentResponseImages(ReadonlySiteLevelRoleMixin, View):
    def get(self, request, pk, **kwargs):
        recent_resp_imgs = get_images_for_site(pk)
        content = {'images': list(recent_resp_imgs)}
        return JsonResponse(content, status=200)


class SiteResponseCoordinates(ReadonlySiteLevelRoleMixin, View):
    def get(self, request, pk, **kwargs):
        coord_datas = get_site_responses_coords(pk)
        obj = Site.objects.get(pk=self.kwargs.get('pk'))
        response_coords = list(coord_datas)
        response_coords.append({'geometry': {'coordinates': [obj.latitude, obj.longitude], 'type': 'Point'},
                                              'properties': {'fs_uuid': 'None',
                                              'id':'#' ,
                                              'submitted_by': 'site_origin'},
                                              'type': 'Feature'})
        return render(request, 'fieldsight/site_response_map_view.html', {
            'co_ords': json.dumps(response_coords, cls=DjangoJSONEncoder, ensure_ascii=False).encode('utf8'),
            'geo_layers': obj.project.geo_layers.all(),
            'is_donor_only' : kwargs.get('is_donor_only', False)
        })

    def post(self, request, pk):
        coord_datas = get_site_responses_coords(pk)
        content = {'coords-data': list(coord_datas)}
        return JsonResponse(json.dumps(content, cls=DjangoJSONEncoder, ensure_ascii=False).encode('utf8'), status=200)


class DonorProjectDashboard(DonorRoleMixin, TemplateView):
    template_name = "fieldsight/project_dashboard_lite.html"
    
    def get_context_data(self, **kwargs):
        dashboard_data = super(DonorProjectDashboard, self).get_context_data(**kwargs)
        obj = get_object_or_404(Project, pk=self.kwargs.get('pk'), is_active=True)

        peoples_involved = obj.project_roles.filter(ended_at__isnull=True).distinct('user')
        total_sites = obj.sites.filter(site__isnull=True,is_active=True,
                                       is_survey=False).count()
        sites = obj.sites.filter(is_active=True, is_survey=False,
                                 site__isnull=True)[:200]
        data = serialize('custom_geojson', sites, geometry_field='location',
                         fields=('location', 'id',))

        # total_sites = sites.count()
        total_survey_sites = obj.sites.filter(is_survey=True).count()
        outstanding, flagged, approved, rejected = obj.get_submissions_count()
        bar_graph = BarGenerator(sites)
        line_chart = LineChartGenerator(obj)
        line_chart_data = line_chart.data()
        roles_project = UserRole.objects.filter(organization__isnull = False, project_id = self.kwargs.get('pk'), site__isnull = True, ended_at__isnull=True)

        one_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
        instances = Instance.objects.filter(fieldsight_instance__project_id=obj.id, date_created__gte=one_week_ago)
        new_submissions = instances.count()
        active_supervisors = instances.distinct('user').count()
        try:
            site_visits_query = settings.MONGO_DB.instances.aggregate([{"$match":{"fs_project": obj.id, "start": { '$gte' : one_week_ago.isoformat() } } },  { "$group" : { 
                  "_id" :  {        
                    "fs_site": "$fs_site",
                    "date": { "$substr": [ "$start", 0, 10 ] }
                  },
               }
             }, { "$group": { "_id": "$_id.fs_site", "visits": { '$sum': 1}
             }},
             {"$group": {"_id": None, "total_sum": {'$sum': '$visits'}}}
             ], cursor={})
            site_visits_query = list(site_visits_query)

            if not site_visits_query:
                site_visits = 0
            else:
                site_visits = site_visits_query[0]['total_sum']
        except:
            site_visits = "Error occured."

        dashboard_data = {
            'sites': sites,
            'obj': obj,
            'peoples_involved': peoples_involved,
            'total_sites': total_sites,
            'total_survey_sites': total_survey_sites,
            'outstanding': outstanding,
            'flagged': flagged,
            'approved': approved,
            'rejected': rejected,
            'data': data,
            'cumulative_data': line_chart_data.values(),
            'cumulative_labels': line_chart_data.keys(),
            'progress_data': bar_graph.data.values(),
            'progress_labels': bar_graph.data.keys(),
            'roles_project': roles_project,
            'total_submissions': outstanding + flagged + approved + rejected,
            'site_visits' : site_visits,
            'active_supervisors' : active_supervisors,
            'new_submissions' : new_submissions,
            'gsuit_meta_json': json.dumps(obj.gsuit_meta),
    }
        return dashboard_data

class DonorSiteDashboard(DonorSiteViewRoleMixin, TemplateView):
    template_name = 'fieldsight/site_dashboard_lite.html'

    def get_context_data(self, **kwargs):
        dashboard_data = super(DonorSiteDashboard, self).get_context_data(**kwargs)
        obj =  get_object_or_404(Site, pk=self.kwargs.get('pk'), is_active=True)
        peoples_involved = obj.site_roles.filter(ended_at__isnull=True).distinct('user')
        data = serialize('custom_geojson', [obj], geometry_field='location',
                         fields=('name', 'public_desc', 'additional_desc', 'address', 'location', 'phone', 'id'))

        line_chart = LineChartGeneratorSite(obj)
        line_chart_data = line_chart.data()
        progress_chart = ProgressGeneratorSite(obj)
        progress_chart_data = progress_chart.data()
        meta_questions = obj.project.site_meta_attributes
        meta_answers = obj.site_meta_attributes_ans
        mylist =[]

        for question in meta_questions:
            if question['question_name'] in meta_answers:
                mylist.append({question['question_text'] : meta_answers[question['question_name']]})

        result = get_images_for_sites_count(obj.id)
        
        countlist = list(result)
        if countlist:
            total_count = countlist[0]['count']
        else:
            total_count = 0

        myanswers = mylist
        outstanding, flagged, approved, rejected = obj.get_site_submission()
        

        dashboard_data = {
            'obj': obj,
            'peoples_involved': peoples_involved,
            'outstanding': outstanding,
            'flagged': flagged,
            'approved': approved,
            'rejected': rejected,
            'data': data,
            'cumulative_data': line_chart_data.values(),
            'cumulative_labels': line_chart_data.keys(),
            'progress_chart_data_data': progress_chart_data.keys(),
            'progress_chart_data_labels': progress_chart_data.values(),
            'meta_data': myanswers,
            'next_photos_count':total_count - 5 if total_count > 5 else 0,
            'total_photos': total_count,
            'total_submissions': outstanding + flagged + approved + rejected
        }

        return dashboard_data


class DefineProjectSiteCriteria(ProjectRoleMixin, TemplateView):
    def get(self, request, pk):
        project_obj = Project.objects.get(pk=pk)
        json_questions = json.dumps(project_obj.site_meta_attributes)
        return render(request, 'fieldsight/meta_eq_creator.html', {'obj': project_obj, 'json_questions': json_questions,})

    def post(self, request, pk, *args, **kwargs):
        project = Project.objects.get(pk=pk)
        project.site_meta_attributes = request.POST.get('json_questions');
        project.save()
        return HttpResponseRedirect(reverse('fieldsight:project-dashboard', kwargs={'pk': self.kwargs.get('pk')}))


class AllResponseImages(ReadonlySiteLevelRoleMixin, View):
    def get(self, request, pk, **kwargs):
        all_imgs = get_images_for_site_all(pk)
        return render(request,
                      'fieldsight/gallery.html',
                      {'is_donor_only': kwargs.get('is_donor_only', False),
                       'all_imgs': json.dumps(all_imgs,
                                              cls=DjangoJSONEncoder, ensure_ascii=False).encode('utf8')})


class SitesTypeView(ProjectRoleMixin, TemplateView):
    template_name = "fieldsight/project_site_types.html"

    def get_context_data(self, **kwargs):
        data = super(SitesTypeView, self).get_context_data(**kwargs)
        project = Project.objects.get(pk=kwargs.get('pk'))
        types = project.types.filter(deleted=False)
        data['types'] = types
        data['obj'] = project
        data['level'] = "1"
        data['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        return data


class AddSitesTypeView(ProjectRoleMixin, CreateView):
    model = SiteType
    form_class = SiteTypeForm

    def get_context_data(self, **kwargs):
        data = super(AddSitesTypeView, self).get_context_data(**kwargs)
        project = Project.objects.get(pk=self.kwargs.get('pk'))
        data['obj'] = project
        data['level'] = "1"
        data['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        return data

    def get_success_url(self):
        return reverse('fieldsight:site-types', kwargs={'pk': self.kwargs['pk']})

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.project = Project.objects.get(pk=self.kwargs.get('pk'))
        if not SiteType.objects.filter(project=self.object.project, identifier=self.object.identifier).exists():
            self.object.save()
        else:
            form.add_error(None, "ID duplicate, please try again by adding new one.")
            return self.render_to_response(self.get_context_data(form=form))
        return HttpResponseRedirect(self.get_success_url())


class DeleteSitesTypeView(DeleteView):
    model = SiteType
    form_class = SiteTypeForm

    # def delete(self, request, *args, **kwargs):
    #     """
    #     Calls the delete() method on the fetched object and then
    #     redirects to the success URL.
    #     """
    #     self.object = self.get_object()
    #     success_url = self.get_success_url()
    #     obj = self.object
    #     obj.deleted = True
    #     obj.save()
    #     return HttpResponseRedirect(success_url)

    def get_success_url(self):
        project = self.object.project
        return reverse('fieldsight:site-types', kwargs={'pk': project.pk})

    def dispatch(self, request, *args, **kwargs):
        if is_super_admin:
            return super(DeleteSitesTypeView, self).dispatch(request, *args, **kwargs)

        type_id = self.kwargs.get('pk')
        type = SiteType.objects.get(pk=type_id)
        project_id = type.project.id
        user_id = request.user.id
        user_role = request.roles.filter(user_id=user_id, project_id=project_id, group_id=2)

        if user_role:
            return super(DeleteSitesTypeView, self).dispatch(request, *args, **kwargs)
        organization_id = Project.objects.get(pk=project_id).organization.id
        user_role_asorgadmin = request.roles.filter(user_id=user_id, organization_id=organization_id, group_id=1)

        if user_role_asorgadmin:
            return super(DeleteSitesTypeView, self).dispatch(request, *args, **kwargs)

        raise PermissionDenied()


class EditSitesTypeView(UpdateView):
    model = SiteType
    form_class = SiteTypeForm

    def dispatch(self, request, *args, **kwargs):
        if request.is_super_admin:
            return super(EditSitesTypeView, self).dispatch(request, *args, **kwargs)

        type_id = self.kwargs.get('pk')
        type = SiteType.objects.get(pk=type_id)
        project_id = type.project.id
        user_id = request.user.id
        user_role = request.roles.filter(user_id=user_id, project_id=project_id, group_id=2)

        if user_role:
            return super(EditSitesTypeView, self).dispatch(request, *args, **kwargs)
        organization_id = Project.objects.get(pk=project_id).organization.id
        user_role_asorgadmin = request.roles.filter(user_id=user_id, organization_id=organization_id, group_id=1)

        if user_role_asorgadmin:
            return super(EditSitesTypeView, self).dispatch(request, *args, **kwargs)

        raise PermissionDenied()

    def get_context_data(self, **kwargs):
        data = super(EditSitesTypeView, self).get_context_data(**kwargs)
        project = self.object.project
        data['obj'] = project
        data['level'] = "1"
        data['terms_and_labels'] = ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        return data

    def get_success_url(self):
        project = self.object.project
        return reverse('fieldsight:site-types', kwargs={'pk': project.pk})

    def form_valid(self, form):
        self.object = form.save(commit=False)
        if not SiteType.objects.filter(project=self.object.project, identifier=self.object.identifier).exclude(pk=self.object.pk).exists():
            self.object.save()
        else:
            form.add_error(None, "ID duplicate, please try again by adding new one.")
            return self.render_to_response(self.get_context_data(form=form))
        return HttpResponseRedirect(self.get_success_url())


@api_view(["GET"])
def project_dashboard_peoples(request, pk):
    name = request.query_params.get('name', False)

    new_people_url = reverse('fieldsight:manage-people-project', kwargs={'pk': pk})
    if name:
        roles = UserRole.objects.filter(project_id=pk, ended_at__isnull=True, group__name="Project Manager",
                                        user__first_name__icontains=name).select_related("user", "user__user_profile")
    else:
        roles = UserRole.objects.filter(project_id=pk, ended_at__isnull=True, group__name="Project Manager").\
            select_related("user", "user__user_profile")

    users = []
    user_data = []
    for role in roles:
        if role.user.username not in users:
            profile = UserProfile.objects.get_or_create(user=role.user)
            user_data.append(dict(roles=[role.group.name],
                                  name=role.user.get_full_name(),
                                  email=role.user.email,
                                  phone=role.user.user_profile.phone,
                                  url=reverse("users:profile",args=(role.user.id,)),
                                  image=role.user.user_profile.profile_picture.url))
            users.append(role.user.username)

    return Response({'peoples':user_data, 'new_people_url':new_people_url})


@api_view(["GET"])
def project_managers(request, pk):

    users = User.objects.filter(user_roles__site__isnull=True, user_roles__project_id=pk, user_roles__group_id__in=[4, 9]).distinct('id')
    user_data = []
    for user in users:
        user_data.append(dict(label=user.get_full_name(),
                              email=user.email,
                              id=user.id,
                              ))


    return Response(user_data)

@api_view(["GET"])
def project_dashboard_map(request, pk):
    sites = Site.objects.filter(project__id=pk)[:100]
    data = serialize('custom_geojson', sites, geometry_field='location', fields=('location', 'id', 'name'))
    return Response(data)

@api_view(["GET"])
def project_dashboard_graphs(request, pk):
    project = Project.objects.get(pk=pk)

    # bar_graph = ProgressBarGenerator(project)
    # progress_labels = bar_graph.data.keys()
    # progress_data = bar_graph.data.values()

    bar_graph = ProgressBarGenerator(project)
    progress_labels = bar_graph.data.keys()
    progress_data = bar_graph.data.values()

    line_chart = LineChartGeneratorProject(project)
    submissions = line_chart.data()
    submissions_labels = submissions.keys()
    submissions_data = submissions.values()
#     temp_response = {
#     "sd": [
#         0,
#         452,
#         21549,
#         22351,
#         22351,
#         22351,
#         22356
#     ],
#     "pd": [
#         23421,
#         48,
#         0,
#         0,
#         0,
#         0,
#         0
#     ],
#     "pl": [
#         "Unstarted",
#         "< 20",
#         "20 - 40",
#         "40 - 60",
#         "60 - 80",
#         "80 <",
#         "Completed"
#     ],
#     "sl": [
#         "2018-03-15",
#         "2018-04-15",
#         "2018-05-16",
#         "2018-06-17",
#         "2018-07-18",
#         "2018-08-18",
#         "2018-09-19"
#     ]
# }
#
#     return Response(temp_response)
    return Response({'pl':progress_labels, 'pd':progress_data, 'sl': submissions_labels, 'sd':submissions_data})


def site_refrenced_metas(request, pk):

    site = Site.objects.get(pk=pk)
    project = site.project
    question_dict = project.site_meta_attributes
    all_ma_ans = OrderedDict()
    ans_dict = site.all_ma_ans
    for meta in question_dict:
        all_ma_ans[meta['question_name']] = ans_dict.get(meta['question_name'], "")
    return JsonResponse(all_ma_ans, safe=False)


def redirectToSite(request, pk):
    identifier = request.GET.get('identifier', None)
    if not identifier:
        raise Http404()
    site = get_object_or_404(Site, identifier=identifier, project_id=pk, is_active=True)
    return HttpResponseRedirect(reverse("fieldsight:site-dashboard",  kwargs={'pk': site.id}))    




class SiteBulkEditView(View):
    def get_regions(self, project, parent=None, default=[], prefix=''):
        
        regions = Region.objects.filter(project=project, parent=parent)
        if regions.count() == 0:
            return default

        result = default + [
            {
                'id': region.pk,
                u'name': '{}{} ({})'.format(
                    prefix,
                    region.name,
                    region.identifier,
                ),
                'sites': [s.id for s in Site.objects.filter(
                    region=region
                )],
            } for region in regions
        ]

        for region in regions:
            result = self.get_regions(
                project,
                region,
                result,
                '{}{} / '.format(prefix, region.name),
            )

        return result
    @staticmethod
    def get_regions_filter(project, parent=None, default=[], prefix=''):
        regions = Region.objects.filter(project=project, parent=parent)
        if regions.count() == 0:
            return default

        result = default + [
            {
                'id': region.pk,
                u'name': '{}{} ({})'.format(
                    prefix,
                    region.name,
                    region.identifier,
                ),
                'sites': [s.id for s in Site.objects.filter(
                    region=region
                )],
            } for region in regions
        ]

        for region in regions:
            result = SiteBulkEditView.get_regions_filter(
                project,
                region,
                result,
                u'{}{} / '.format(prefix, region.name),
            )

        return result

    def get(self, request, pk):
        project = Project.objects.get(pk=pk)
        context = {
            'project': project,
            'regions': SiteBulkEditView.get_regions_filter(project),
            'form': SiteBulkEditForm(project=project),
            'terms_and_labels': ProjectLevelTermsAndLabels.objects.filter(project=project).exists()

        }

        return render(
            request,
            'fieldsight/site-bulk-edit.html',
            context,
        )

    def post(self, request, pk):
        project = Project.objects.get(pk=pk)
        context = {
            'project': project,
            'regions': self.get_regions(project),
            'form': SiteBulkEditForm(project=project),
        }

        data = {}
        for attr in project.site_meta_attributes:
            q_name = attr['question_name']
            to_set = request.POST.get('set_{}'.format(q_name))
            if to_set:
                data[q_name] = request.POST.get(q_name)

        sites = request.POST.getlist('sites')
        for site_id in sites:
            site = Site.objects.get(id=site_id)
            new_data = site.site_meta_attributes_ans
            if not isinstance(new_data, dict):
                new_data = {}
            new_data.update(data)
            site.site_meta_attributes_ans = new_data
            site.save()
            
        context['done'] = True

        return render(
            request,
            'fieldsight/site-bulk-edit.html',
            context,
        )



# class ProjectRegions(ProjectRoleMixin, View):
    
#     def get_regions(self, project, parent=None, default=[], prefix=''):
        
#         regions = Region.objects.filter(project=project, parent=parent)
#         if regions.count() == 0:
#             return default

#         result = default + [
#             {
#                 'id': region.pk,
#                 'name': '{}{} ({})'.format(
#                     prefix,
#                     region.name,
#                     region.identifier,
#                 ),
#                 'sites': [s.id for s in Site.objects.filter(
#                     region=region
#                 )],
#             } for region in regions
#         ]

#         for region in regions:
#             result = self.get_regions(
#                 project,
#                 region,
#                 result,
#                 '{}{} / '.format(prefix, region.name),
#             )

#         return result

#     def get(self, request, pk)

#         return JsonResponse(metas, safe=False)

@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
def municipality_data(request):
    data = generate_municipality_data()
    return Response(data.values())


class MainRegionsAndSitesAPI(View):
    def get(self, request, pk, **kwargs):
        sites = UserRole.objects.filter(user_id = self.kwargs.get('user_id'), group_id=self.kwargs.get('group_id'), ended_at=None, project_id=pk, site__isnull=False).distinct('site_id').values('site_id')
        regions_ids = UserRole.objects.filter(user_id = self.kwargs.get('user_id'), group_id=self.kwargs.get('group_id'), ended_at=None, project_id=pk, site__isnull=False, site__region_id__isnull=False).distinct('site__region_id').values('site__region_id')
        regions = Region.objects.filter(parent = None, pk__in=regions_ids, project_id=pk).extra(select={'label': 'name'}).values('id','label', 'identifier')
        sites= Site.objects.filter(pk__in=sites, region=None).extra(select={'label': 'name'}).values('id','label', 'identifier')
        content={'regions':list(regions), 'sites':list(sites)}
        return JsonResponse(content, status=200)

class SubRegionAndSitesAPI(View):
    def get(self, request, pk, **kwargs):
        region = Region.objects.get(pk=pk)
        sites = UserRole.objects.filter(user_id = self.kwargs.get('user_id'), ended_at=None, group_id=self.kwargs.get('group_id'), project_id=region.project_id, site__isnull=False).distinct('site_id').values('site_id')
        regions_ids = UserRole.objects.filter(user_id = self.kwargs.get('user_id'), group_id=self.kwargs.get('group_id'), ended_at=None, project_id=pk, site__isnull=False, site__region_id__isnull=False).distinct('site__region_id').values('site__region_id')
        sub_regions = Region.objects.filter(parent_id = pk, pk__in=regions_ids).extra(select={'label': 'name'}).values('id','label', 'identifier')
        sites= Site.objects.filter(pk__in=sites, region_id=pk).extra(select={'label': 'name'}).values('id','label', 'identifier')
        content={'sub_regions':list(sub_regions), 'sites':list(sites)}
        return JsonResponse(content, status=200)


class UnassignUserRegionAndSites(View):
    def post(self, request, pk, **kwargs):
        data = json.loads(self.request.body)
        ids = data.get('ids')
        try:
            projects = [k for k in ids if 'p' in str(k)]
        except TypeError:
            status, data = 200, {'status': 'false', 'message': 'Please select to remove roles.'}

            return JsonResponse(data, status=status)
        ids = list(set(ids) - set(projects))
        regions = [k for k in ids if 'r' in str(k)]
        sites = list(set(ids) - set(regions))
        user_id= pk
        group_id = data.get('group')

        status, data = 200, {'status':'false','message':'PermissionDenied. You do not have sufficient rights.'}

        if request.is_super_admin:

            request_usr_org_role = UserRole.objects.filter(user_id=request.user.id, ended_at = None, group_id=1).order_by('organization_id').distinct('organization_id').values_list('organization_id', flat=True)
            if not request_usr_org_role:

                request_usr_project_role = UserRole.objects.filter(user_id=request.user.id, ended_at = None, group_id=2).order_by('project_id').distinct('project_id').values_list('project_id', flat=True)
                if not request_usr_project_role:
                    return JsonResponse(data, status=status)
                if projects:
                    project_ids = [k[1:] for k in projects]
                    if not set(project_ids).issubset(set(request_usr_project_role)):
                        return JsonResponse(data, status=status)

                if regions:
                    region_ids = [k[1:] for k in regions]

                    if len(region_ids) != Region.objects.filter(pk__in=region_ids, project_id__in=request_usr_project_role).count():
                        return JsonResponse(data, status=status)


                if sites:
                    if len(sites) != Site.objects.filter(pk__in=sites, project_id__in=request_usr_project_role).count():
                        return JsonResponse(data, status=status)


            else:

                if projects:
                    project_ids = [k[1:] for k in projects]

                    if len(project_ids) != Project.objects.filter(pk__in=project_ids, organization_id__in=request_usr_org_role).count():
                        return JsonResponse(data, status=status)

                if regions:
                    region_ids = [k[1:] for k in regions]

                    if len(region_ids) != Region.objects.filter(pk__in=region_ids, project__organization_id__in=request_usr_org_role).count():
                        return JsonResponse(data, status=status)


                if sites:
                    if len(sites) != Site.objects.filter(pk__in=sites, project__organization_id__in=request_usr_org_role).count():
                        return JsonResponse(data, status=status)


        status, data = 401, {'status':'false','message':'Error occured try again.'}

        if int(group_id) in [3,4]:
            user = get_object_or_404(User, pk=pk)
            task_obj=CeleryTaskProgress.objects.create(user=request.user, description="Removal of UserRoles", content_object = user, task_type=7)
            if task_obj:
                task = UnassignUser.delay(task_obj.id, user_id, sites, regions, projects, group_id)
                task_obj.task_id = task.id
                task_obj.save()
                status, data = 200, {'status':'True', 'ids':ids, 'projects':projects, 'regions':regions, 'sites': sites, 'message':'Sucess, the roles are being removed. You will be notified after all the roles are removed. '}

        return JsonResponse(data, status=status)



#class ProjectSiteListGeoJSON(ReadonlyProjectLevelRoleMixin, View):

class ProjectSiteListGeoJSON(FullMapViewMixin, View):
    def get(self, request, **kwargs):
        project = Project.objects.get(pk=self.kwargs.get('pk'))
        try: 
            startdate = project.project_geojson.updated_at
            #Use updated date as the submissions can be updated any time.
            sites_id = FInstance.objects.filter(project_id=project.id, date__gt=startdate, site__isnull=False).values('site_id')
            sites = Site.objects.filter(pk__in=sites_id, is_survey=False, is_active=True)
        except:
            sites = Site.objects.filter(project_id=project.id, is_survey=False, is_active=True)

        data = serialize('full_detail_geojson',
                         sites,
                         geometry_field='location',
                         fields=('name', 'location', 'id', 'identifier'))

        return JsonResponse(json.loads(data), status=200)



class DonorFullMap(FullMapViewMixin, View):
    def get(self, request, **kwargs):
        return render(request, 'fieldsight/donor_fullmap.html', {})


class GeoJSONContent(View):
    def get(self, request, **kwargs):
        geojsonfile = ProjectGeoJSON.objects.get(pk=self.kwargs.get('pk')).geoJSON
        geojsonfile.open(mode='rb') 
        lines = geojsonfile.read()
        geojsonfile.close()
        return JsonResponse(json.loads(lines), status=200)


class RequestOrganizationSearchView(TemplateView):
    template_name = 'fieldsight/request_organization_list.html'

    def get_context_data(self, **kwargs):
        context = super(RequestOrganizationSearchView, self).get_context_data(**kwargs)
        query = self.request.GET.get("q")
        context['org'] = Organization.objects.filter(name__icontains=query).values('name', 'id')

        return context


@receiver(post_save, sender=Organization)
def auto_create_project_site(instance, created, **kwargs):
    if created:
        project_type_id = ProjectType.objects.first().id
        project = Project.objects.create(name="Example Project", organization_id=instance.id, type_id=project_type_id,
                                         location=instance.location)
        Site.objects.create(name="Example Site", project=project, identifier="example site",
                            location=instance.location)


class ApplicationView(LoginRequiredMixin, TemplateView):
    template_name = "fieldsight/application.html"

    def get_context_data(self, **kwargs):
        context = super(ApplicationView, self).get_context_data(**kwargs)
        project = self.request.GET.get("project", None)
        site = self.request.GET.get("site", None)
        submission = self.request.GET.get("submission", None)
        base_url = settings.SITE_URL
        context['base_url'] = base_url
        context['kpi_base_url'] = settings.KPI_URL

        if project:

            project_obj = get_object_or_404(Project, id=int(project))
            context['project'] = project_obj
            context['organization'] = project_obj.organization.id

            return context

        elif site:
            site_obj = get_object_or_404(Site, id=int(site))
            context['site_id'] = site_obj.id
            context['project'] = site_obj.project

            if site_obj.enable_subsites is False:
                context['root_site'] = site_obj.site
            return context

        elif submission:
            try:
                context['submission'] = submission

                return context
            except ValueError:
                return context
        else:
            return context


class ProjectSyncScheduleUpdateView(UpdateView):
    template_name = 'fieldsight/project_sync_schedule.html'
    model = Project
    form_class = ProjectGsuitSyncForm

    def get_success_url(self):
        return reverse('fieldsight:sync_schedule', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        pk = self.kwargs['pk'] 
        context = super(ProjectSyncScheduleUpdateView, self).get_context_data(**kwargs)
        
        context['schedule_forms'] = FieldSightXF.objects.select_related('xf', 'sync_schedule', 'schedule').filter(project_id=pk, is_scheduled = True, is_staged=False, is_survey=False, sync_schedule__isnull=False)
        mainstage=[]
        stages = Stage.objects.filter(project_id=pk)
        for stage in stages:
            if stage.stage_id is None:
                substages=stage.get_sub_stage_list(sync_details=True)
                main_stage = {'id':stage.id, 'title':stage.name, 'sub_stages':substages}
                # stagegroup = {'main_stage':main_stage,}
                mainstage.append(main_stage)

        context['stage_forms'] = mainstage
        context['survey_forms'] = FieldSightXF.objects.select_related('xf', 'sync_schedule').filter(project_id=pk, is_scheduled = False, is_staged=False, is_survey=True, sync_schedule__isnull=False)
        context['general_forms'] = FieldSightXF.objects.select_related('xf', 'sync_schedule').filter(project_id=pk, is_scheduled = False, is_staged=False, is_survey=False, sync_schedule__isnull=False)

        context['base_template'] = "fieldsight/manage_base.html"
        context['obj'] = Project.objects.get(pk=pk)
        return context


class SyncScheduleCreateView(ProjectRoleMixin, CreateView):
    template_name = 'fieldsight/form_sync_schedule_form.html'
    model = SyncSchedule
    form_class = FieldsightFormGsuitSyncNewForm

    def get_context_data(self, **kwargs):
        context = super(SyncScheduleCreateView, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs.get('pk')
        context['base_template'] = "fieldsight/fieldsight_base.html"
        return context

    def get_form_kwargs(self):
          kwargs = super(SyncScheduleCreateView, self).get_form_kwargs()
          kwargs['pk'] = self.kwargs.get('pk')
          return kwargs

    def get_success_url(self):
        return reverse('fieldsight:sync_schedule', kwargs={'pk': self.kwargs['pk']})


class SyncScheduleUpdateView(ProjectRoleMixin, UpdateView):
    template_name = 'fieldsight/form_sync_schedule_form.html'
    model = SyncSchedule
    form_class = FieldsightFormGsuitSyncEditForm


    def get_success_url(self):
        return reverse('fieldsight:sync_schedule', kwargs={'pk': self.object.fxf.project.id})

    def get_context_data(self, **kwargs):
        context = super(SyncScheduleUpdateView, self).get_context_data(**kwargs)
        context['base_template'] = "fieldsight/fieldsight_base.html"
        return context


class SyncScheduleDeleteView(ProjectRoleMixin, DeleteView):
    model = SyncSchedule
    
    def get_success_url(self):
        return reverse('fieldsight:sync_schedule', kwargs={'pk': self.object.fxf.project.id})


# vector tile test

def mvt_tiles(request, zoom, x, y):

    """
    Custom view to serve Mapbox Vector Tiles for the custom polygon model.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT ST_AsMVT(tile) FROM (SELECT id,name, ST_AsMVTGeom(location::geometry, TileBBox(%s, %s, %s, 4326)) FROM  fieldsight_site) AS tile", [zoom, x, y])
        tile = bytes(cursor.fetchone()[0])
        # return HttpResponse(len(tile))
        # if not len(tile):
        #     raise Http404()
    return HttpResponse(tile, content_type="application/x-protobuf")


def vect_map(request):
    return render(request, 'fieldsight/vect_map.html')


def attachment_url(request, instance_id, size='medium'):
    media_file = request.GET.get('media_file')
    media_folder = request.GET.get('media_folder')
    # search for media_file with exact matching name
    try:
        attachment = Attachment.objects.filter(instance_id=instance_id, media_file_basename=media_file).first() or Attachment.objects.filter(instance_id=instance_id, media_file__contains=media_file).first() or Attachment.objects.filter(media_file__contains=media_file).filter(media_file__contains=media_folder).first()

    except ValueError:
        return HttpResponseNotFound('Attachment not found')

    media_url = image_url(attachment, size)
    response = HttpResponse()
    default_storage = get_storage_class()()
    if not isinstance(default_storage, FileSystemStorage):
        return redirect(media_url)
    else:
        return redirect(media_url)
    response["Content-Type"] = ""
    response["X-Accel-Redirect"] = protected_url
    return response
