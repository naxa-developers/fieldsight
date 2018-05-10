from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group
from onadata.apps.viewer.models.parsed_instance import dict_for_mongo, _encode_for_mongo, xform_instances
from django.conf import settings
from onadata.apps.viewer.models import ParsedInstance
from onadata.apps.fsforms.models import FInstance, FieldSightParsedInstance

import json
class Command(BaseCommand):
    help = 'recover form when there it is in ffinstances, instances and parseinstances.'
    

    def handle(self, *args, **options):
        ids =[ 21265, 21267, 21268, 21269, 21270, 21271, 21272, 21273, 21274,
            21275,
            21276,
            21277,
            21278,
            21279,
            21280,
            21282,
            21286,
            21287,
            21288,
            21289,
            21290,
            21291,
            21292,
            21293,
            21294,
            21295,
            21296,
            21297,
            21298,
            21299,
            21300,
            21301,
            21302,
            21303,
            21304,
            21305,
            21306,
            21307,
            21308,
            21309,
            21310,
            21311,
            21312,
            21313,
            21314,
            21316,
            21317,
            21318,
            21319,
            21320,
            21321,
            21322,
            21323,
            21324,
            21325,
            21326,
            21327,
            21328,
            21329,
            21330 ]

        main_data={21265: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41587',
          'fs_status': 0,
          'fs_uuid': '316575'},
         21267: {'fs_project': '72',
          'fs_project_uuid': '351587',
          'fs_site': '35665',
          'fs_status': 0,
          'fs_uuid': '351599'},
         21268: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41328',
          'fs_status': 0,
          'fs_uuid': '316057'},
         21269: {'fs_project': '72',
          'fs_project_uuid': '57917',
          'fs_site': '35665',
          'fs_status': 0,
          'fs_uuid': '293338'},
         21270: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41395',
          'fs_status': 0,
          'fs_uuid': '316191'},
         21271: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41406',
          'fs_status': 0,
          'fs_uuid': '316213'},
         21272: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41397',
          'fs_status': 0,
          'fs_uuid': '316195'},
         21273: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41403',
          'fs_status': 0,
          'fs_uuid': '316207'},
         21274: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41414',
          'fs_status': 0,
          'fs_uuid': '316229'},
         21275: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49549',
          'fs_status': 0,
          'fs_uuid': '332500'},
         21276: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49550',
          'fs_status': 0,
          'fs_uuid': '332502'},
         21277: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53337',
          'fs_status': 0,
          'fs_uuid': '340076'},
         21278: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41419',
          'fs_status': 0,
          'fs_uuid': '316239'},
         21279: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53309',
          'fs_status': 0,
          'fs_uuid': '340020'},
         21280: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49556',
          'fs_status': 0,
          'fs_uuid': '332514'},
         21282: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53323',
          'fs_status': 0,
          'fs_uuid': '340048'},
         21286: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49558',
          'fs_status': 0,
          'fs_uuid': '332518'},
         21287: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41381',
          'fs_status': 0,
          'fs_uuid': '316163'},
         21288: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49531',
          'fs_status': 0,
          'fs_uuid': '332464'},
         21289: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49560',
          'fs_status': 0,
          'fs_uuid': '332522'},
         21290: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41418',
          'fs_status': 0,
          'fs_uuid': '316237'},
         21291: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49553',
          'fs_status': 0,
          'fs_uuid': '332508'},
         21292: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49557',
          'fs_status': 0,
          'fs_uuid': '332516'},
         21293: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49542',
          'fs_status': 0,
          'fs_uuid': '332486'},
         21294: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41379',
          'fs_status': 0,
          'fs_uuid': '316159'},
         21295: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49548',
          'fs_status': 0,
          'fs_uuid': '332498'},
         21296: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53314',
          'fs_status': 0,
          'fs_uuid': '340030'},
         21297: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41376',
          'fs_status': 0,
          'fs_uuid': '316153'},
         21298: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53303',
          'fs_status': 0,
          'fs_uuid': '340008'},
         21299: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53297',
          'fs_status': 0,
          'fs_uuid': '339996'},
         21300: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '48958',
          'fs_status': 0,
          'fs_uuid': '331318'},
         21301: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53301',
          'fs_status': 0,
          'fs_uuid': '340004'},
         21302: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49541',
          'fs_status': 0,
          'fs_uuid': '332484'},
         21303: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41368',
          'fs_status': 0,
          'fs_uuid': '316137'},
         21304: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49968',
          'fs_status': 0,
          'fs_uuid': '333338'},
         21305: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53326',
          'fs_status': 0,
          'fs_uuid': '340054'},
         21306: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53326',
          'fs_status': 0,
          'fs_uuid': '340054'},
         21307: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53336',
          'fs_status': 0,
          'fs_uuid': '340074'},
         21308: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49546',
          'fs_status': 0,
          'fs_uuid': '332494'},
         21309: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53306',
          'fs_status': 0,
          'fs_uuid': '340014'},
         21310: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '49559',
          'fs_status': 0,
          'fs_uuid': '332520'},
         21311: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53304',
          'fs_status': 0,
          'fs_uuid': '340010'},
         21312: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '41367',
          'fs_status': 0,
          'fs_uuid': '316135'},
         21313: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53317',
          'fs_status': 0,
          'fs_uuid': '340036'},
         21314: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53318',
          'fs_status': 0,
          'fs_uuid': '340038'},
         21316: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '45826',
          'fs_status': 0,
          'fs_uuid': '325053'},
         21317: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '45827',
          'fs_status': 0,
          'fs_uuid': '325055'},
         21318: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '45825',
          'fs_status': 0,
          'fs_uuid': '325051'},
         21319: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '45829',
          'fs_status': 0,
          'fs_uuid': '325059'},
         21320: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '45832',
          'fs_status': 0,
          'fs_uuid': '325065'},
         21321: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53319',
          'fs_status': 0,
          'fs_uuid': '340040'},
         21322: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53315',
          'fs_status': 0,
          'fs_uuid': '340032'},
         21323: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53220',
          'fs_status': 0,
          'fs_uuid': '339842'},
         21324: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '45845',
          'fs_status': 0,
          'fs_uuid': '325091'},
         21325: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53263',
          'fs_status': 0,
          'fs_uuid': '339928'},
         21326: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53340',
          'fs_status': 0,
          'fs_uuid': '340082'},
         21327: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '53338',
          'fs_status': 0,
          'fs_uuid': '340078'},
         21328: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '45848',
          'fs_status': 0,
          'fs_uuid': '325097'},
         21329: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '45810',
          'fs_status': 0,
          'fs_uuid': '325021'},
         21330: {'fs_project': '137',
          'fs_project_uuid': '73732',
          'fs_site': '45807',
          'fs_status': 0,
          'fs_uuid': '325015'}}


        # f=FInstance.objects.filter(date__range=["2018-4-10","2018-5-10"]).values_list('instance', flat=True)
        # fm =list(settings.MONGO_DB.instances.find({ "_id": { "$in": list(f) } }, {"fs_site":1, "fs_uuid":1}))
        # data = [id['_id'] for id in fm]

        # data2 =[item for item in f if item not in data ]
        # fm2 =list(settings.MONGO_DB.instances.find({ "_id": { "$in": list(data2) } }, {"_submission_time":1}))
        
        nf=FInstance.objects.filter(instance_id__in=ids)
        nnf = FieldSightParsedInstance.objects.filter(instance_id__in=ids)
        change_ids ={}

        main_data={}
        for fi in nf:
            
            if fi.site is None:
                site_id = ""
            else:
                site_id =fi.site_id

            if fi.project_fxf is None:
                project_fxf_id = ""
            else:
                project_fxf_id=fi.project_fxf_id

            if fi.project is None:
                project_id = ""
            else:
                project_id = fi.project_id

            if fi.site_fxf is None:
                site_fxf_id = ""
            else:
                site_fxf_id = fi.site_fxf_id

            main_data[fi.instance_id] = {'fs_uuid': str(site_fxf_id), 'fs_status': 0,'fs_site':str(site_id), 'fs_project':str(project_id),
            'fs_project_uuid':str(project_fxf_id)}

        for finnf in nnf:
            if finnf.instance_id in main_data:
                finnf.save(update_fs_data=main_data[finnf.instance_id], async=False)

        #     settings.MONGO_DB.instances.find({ "_id": k }, { "$set": { "fs_uuid": fi.site_fxf_id } })
               
        import pdb; pdb.set_trace()