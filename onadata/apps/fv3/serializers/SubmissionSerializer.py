import json
from rest_framework import serializers

from onadata.apps.fsforms.models import XformHistory, FORM_STATUS
from onadata.apps.fsforms.utils import get_version
from onadata.apps.logger.models import Instance

from django.contrib.sites.models import Site as DjangoSite
BASEURL = DjangoSite.objects.get_current().domain


class SubmissionSerializer(serializers.ModelSerializer):
    submission_data = serializers.SerializerMethodField()
    submitted_by = serializers.SerializerMethodField()
    submitted_from = serializers.SerializerMethodField()
    submmition_history = serializers.SerializerMethodField()
    status_data = serializers.SerializerMethodField()
    form_type = serializers.SerializerMethodField()

    class Meta:
        model = Instance
        fields = ('submission_data', 'date_created',  'submitted_by', 'submitted_from', 'submmition_history',
                  'status_data','form_type')

    def get_submitted_by(self, obj):
        return obj.user.username

    def get_status_data(self, obj):
        finstance = obj.fieldsight_instance
        return {
            'status_display': finstance.get_abr_form_status(),
            'status': finstance.form_status,
            'options': dict(FORM_STATUS),
            'comment': finstance.comment
        }

    def get_submmition_history(self, obj):
        finstance = obj.fieldsight_instance
        return {}

    def get_submitted_from(self, obj):
        finstance = obj.fieldsight_instance
        return {'name':finstance.site.name} if finstance.site else {}

    def get_form_type(self, obj):
        finstance = obj.fieldsight_instance

        return {
            'is_staged': finstance.site_fxf.is_staged if finstance.site_fxf else finstance.project_fxf.is_staged,
            'is_scheduled': finstance.site_fxf.is_scheduled if finstance.site_fxf else finstance.project_fxf.is_scheduled,
            'is_survey': finstance.site_fxf.is_survey if finstance.site_fxf else finstance.project_fxf.is_survey,
        }

    def get_submission_data(self, instance):
        data = []
        finstance = instance.fieldsight_instance

        def get_answer(instance):
            return instance.json

        def get_question(instance, finstance):
            submission_version = finstance.get_version
            json_data = instance.xform.json
            xml = instance.xform.xml
            xml_version = get_version(xml)
            if submission_version and submission_version == xml_version:
                return json.loads(json_data)
            else:
                if XformHistory.objects.filter(xform=instance.xform, version=submission_version).exists():
                    xf_history = XformHistory.objects.get(xform=instance.xform, version=submission_version)
                    return json.loads(str(xf_history.json))

            return json.loads(json_data)

        json_answer = get_answer(instance)
        json_question = get_question(instance, finstance)

        base_url = BASEURL
        media_folder = instance.xform.user.username

        def parse_repeat(r_object, prev_group = None):
            repeat = dict()
            if prev_group:
                r_question = prev_group + '/' + r_object['name']
            else:
                r_question = r_object['name']
            repeat['name'] = r_object['name']
            repeat['type'] = r_object['type']
            repeat['label'] = r_object.get('label')
            repeat['elements'] = []

            if r_question in json_answer:
                for gnr_answer in json_answer[r_question]:
                    for first_children in r_object['children']:
                        question_type = first_children['type']
                        question = first_children['name']
                        group_answer = json_answer[r_question]
                        answer = ''
                        if r_question + "/" + question in gnr_answer:
                            if first_children['type'] == 'note':
                                answer = ''
                            elif first_children['type'] == 'photo' or first_children['type'] == 'audio' or \
                                    first_children['type'] == 'video':
                                answer = 'http://' + base_url + '/attachment/medium?media_file=' + media_folder + '/attachments/' + \
                                         gnr_answer[r_question + "/" + question]
                            else:
                                answer = gnr_answer[r_question + "/" + question]

                        if 'label' in first_children:
                            question = first_children['label']
                        row = {'type': question_type, 'question': question, 'answer': answer}
                        repeat['elements'].append(row)
            elif r_question in json_answer:
                for gnr_answer in json_answer[r_question]:
                    for first_children in r_object['children']:
                        question_type = first_children['type']
                        question = first_children['name']
                        group_answer = json_answer[r_question]
                        answer = ''
                        if r_question + "/" + question in gnr_answer:
                            if first_children['type'] == 'note':
                                answer = ''
                            elif first_children['type'] == 'photo' or first_children['type'] == 'audio' or \
                                    first_children['type'] == 'video':
                                answer = 'http://' + base_url + '/attachment/medium?media_file=' + media_folder + '/attachments/' + \
                                         gnr_answer[r_question + "/" + question]
                            else:
                                answer = gnr_answer[r_question + "/" + question]

                        if 'label' in first_children:
                            question = first_children['label']
                        row = {'type': question_type, 'question': question, 'answer': answer}
                        repeat['elements'].append(row)
            else:
                for first_children in r_object['children']:
                    question_type = first_children['type']
                    question = first_children['name']
                    answer = ''
                    if 'label' in first_children:
                        question = first_children['label']
                    row = {'type': question_type, 'question': question, 'answer': answer}
                    repeat['elements'].append(row)
            return repeat

        def parse_group(prev_groupname, g_object):
            g_question = prev_groupname + g_object['name']
            if g_object['name'] == 'meta':
                for first_children in g_object['children']:
                    question = first_children['name']
                    question_type = first_children['type']
                    if question_type == 'group':
                        parse_group(g_question + "/", first_children)
                        continue
                    answer = ''
                    if g_question + "/" + question in json_answer:
                        if question_type == 'note':
                            answer = ''
                        elif question_type == 'photo' or question_type == 'audio' or question_type == 'video':
                            answer = 'http://' + base_url + '/attachment/medium?media_file=' + media_folder + '/attachments/' + \
                                     json_answer[g_question + "/" + question]
                        else:
                            answer = json_answer[g_question + "/" + question]

                    if 'label' in first_children:
                        question = first_children['label']
                    row = {'type': question_type, 'question': question, 'answer': answer}
                    return row
            else:
                group = dict()
                group['name'] = g_question
                group['type'] = g_object['type']
                group['label'] = g_object.get('label')
                group['elements'] = []
                # group = {'group_name': g_question, 'type': g_object['type'], 'label': g_object['label']}
                for first_children in g_object['children']:
                    question = first_children['name']
                    question_type = first_children['type']
                    if question_type == 'group':
                        group['elements'].append(parse_group(g_question + "/", first_children))
                        continue

                    if question_type == 'repeat':
                        group['elements'].append(parse_repeat(first_children, g_question))
                        continue
                    answer = ''
                    if g_question + "/" + question in json_answer:
                        if question_type == 'note':
                            answer = ''
                        elif question_type == 'photo' or question_type == 'audio' or question_type == 'video':
                            answer = 'http://' + base_url + '/attachment/medium?media_file=' + media_folder + '/attachments/' + \
                                     json_answer[g_question + "/" + question]
                        else:
                            answer = json_answer[g_question + "/" + question]

                    if 'label' in first_children:
                        question = first_children['label']
                    row = {'type': question_type, 'question': question, 'answer': answer}
                    group['elements'].append(row)
                return group

        def parse_individual_questions(parent_object):
            for first_children in parent_object:
                if first_children['type'] == "repeat":
                    data.append(parse_repeat(first_children))
                elif first_children['type'] == 'group':
                    group = parse_group("", first_children)
                    data.append(group)
                else:
                    question = first_children['name']
                    question_type = first_children['type']
                    answer = ''
                    if question in json_answer:
                        if first_children['type'] == 'note':
                            answer = ''
                        elif first_children['type'] == 'photo' or first_children['type'] == 'audio' or first_children[
                            'type'] == 'video':
                            answer = 'http://' + base_url + '/attachment/medium?media_file=' + media_folder + '/attachments/' + \
                                     json_answer[question]
                        else:
                            answer = json_answer[question]
                    if 'label' in first_children:
                        question = first_children['label']
                    row = {"type": question_type, "question": question, "answer": answer}
                    data.append(row)

            submitted_by = {'type': 'submitted_by', 'question': 'Submitted by', 'answer': json_answer['_submitted_by']}
            submission_time = {
                'type': 'submission_time', 'question': 'Submission Time',
                'answer': json_answer['_submission_time']
            }
            data.append(submitted_by)
            data.append(submission_time)

        parse_individual_questions(json_question['children'])
        return data
