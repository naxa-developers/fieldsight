import math
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.models import Func, F, Value

from onadata.apps.api.viewsets.xform_submission_api import update_mongo
from onadata.apps.logger.models import XForm, Instance
from onadata.apps.logger.models.instance import InstanceHistory


SECOND_TRANCHE = {
    "non_compliant":"com_excep",
    "compliant":"com_excep",
    "com_correc":"com_excep",

}

SECOND_TRANCHE_SUBMISSIONS = [88730,
 82132,
 88750,
 192353,
 198977,
 223765,
 224833,
 192485,
 61378,
 166424,
 231731,
 217246,
 98690,
 217002,
 90321,
 90325,
 90551,
 90555,
 91747,
 91751,
 95996,
 102564,
 82929,
 141547,
 187898,
 173665,
 178840,
 178809,
 140804,
 118297,
 193030,
 156388,
 156416,
 96424,
 64740,
 82120,
 90538,
 92554,
 122885]

THIRD_TRANCHE_SUBMISSIONS = [86483,
 154568,
 154739,
 154789,
 156072,
 187982,
 192405,
 210799,
 214020,
 227428,
 154648,
 154747,
 154773,
 154817,
 154821,
 183306,
 183313,
 187775,
 187779,
 187813,
 187823,
 187876,
 187883,
 187893,
 187909,
 187925,
 188010,
 188012,
 188025,
 188027,
 192376,
 192397,
 192401,
 192403,
 192415,
 214060,
 83501,
 103363,
 83495,
 83985,
 178668,
 178564,
 83498,
 91557,
 104200,
 105637,
 69004,
 69008,
 69012,
 69016,
 69024,
 69028,
 69036,
 69070,
 69078,
 69090,
 69122,
 69126,
 69134,
 69139,
 69143,
 69148,
 69152,
 69156,
 69201,
 69206,
 69215,
 69226,
 69258,
 69262,
 69266,
 69277,
 69281,
 69293,
 69301,
 69305,
 96289,
 96296,
 96301,
 96305,
 96309,
 96316,
 96320,
 96325,
 96337,
 96345,
 96356,
 96361,
 84038,
 96370,
 96381,
 96385,
 96389,
 96397,
 96419,
 96425,
 96446,
 96455,
 96463,
 96653,
 69094,
 69098,
 69114,
 141953,
 70323,
 145471,
 62069,
 68359,
 68947,
 68955,
 69082,
 70289,
 86748,
 68364,
 68975,
 68996,
 69000,
 204167,
 83644,
 83533,
 103705,
 103715,
 103723,
 85528,
 85523,
 85532,
 85540,
 85553,
 109841,
 83512,
 85517,
 70342,
 83593,
 83525,
 83579,
 83918,
 83926,
 70315,
 70329,
 83601,
 83688,
 83904,
 70358,
 73553,
 73553,
 83921,
 70311,
 75303,
 83893,
 75133,
 83532,
 83597,
 83913,
 83930,
 83947,
 85564,
 89980,
 89984,
 89995,
 83667,
 85525,
 85556,
 109804,
 83506,
 83538,
 83695,
 83699,
 83899,
 109812,
 85520,
 109789,
 109793,
 109798,
 109808,
 109829,
 83564,
 83618,
 83943,
 83961,
 105585,
 105589,
 105646,
 96430,
 96442,
 96450,
 96459,
 96473,
 96488,
 96495,
 96545,
 96554,
 96588,
 96621,
 96625,
 96629,
 96633,
 96637,
 96641,
 96678,
 96682,
 96707,
 96718,
 96787,
 96791,
 96795,
 96835,
 96844,
 96848,
 96852,
 96871,
 122186,
 122194,
 122225,
 122230,
 122238,
 122250,
 122254,
 122263,
 129383,
 129388,
 129399,
 129413,
 129424,
 132598,
 132625,
 132631,
 132647,
 132678,
 132760,
 132768,
 134421,
 134440,
 134450,
 134454,
 134459,
 134460,
 137050,
 172765,
 172771,
 172775,
 172778,
 172780,
 172909,
 172913,
 172917,
 206222,
 206226,
 206296,
 206312,
 206316,
 206324,
 206331,
 206345,
 206346,
 209917,
 210269,
 210281,
 113464,
 222622,
 83957,
 96481,
 83547,
 62195,
 62200,
 62213,
 62216,
 62222,
 62231,
 70295,
 59862,
 102904,
 103754,
 103822,
 112593,
 102900,
 113499,
 113528,
 118722,
 119697,
 119701,
 119717,
 119725,
 119729,
 119733,
 119738,
 122618,
 126566,
 127541,
 127566,
 127574,
 128229,
 141771,
 144354,
 144360,
 144366,
 146703,
 146709,
 146715,
 146720,
 148357,
 160408,
 161309,
 169485,
 58525,
 117739,
 117748,
 132629,
 132956,
 134148,
 176118,
 176143,
 177473,
 83784,
 91535,
 95171,
 77724,
 95173,
 95513,
 100958,
 101225,
 117734,
 115100,
 123665,
 172402,
 173354,
 104221,
 102766,
 57118,
 57322,
 70293,
 88241,
 88351,
 88356,
 88436,
 97086,
 98365,
 98373,
 98380,
 98398,
 98403,
 103515,
 104112,
 118510,
 120015,
 120018,
 129951,
 142870,
 150130,
 150160,
 150182,
 150211,
 151390,
 151411,
 151424,
 151458,
 154600,
 154612,
 154634,
 154743,
 157527,
 157724,
 157753,
 157757,
 163397,
 163419,
 163739,
 163784,
 163786,
 163787,
 168316,
 168323,
 168335,
 168339,
 168353,
 174044,
 174060,
 174065,
 174069,
 174085,
 174095,
 175608,
 175619,
 176006,
 183356,
 83918,
 191481,
 200814,
 206773,
 206774,
 156548,
 210394,
 210447,
 216825,
 216831,
 225333,
 225335,
 225357,
 227437,
 227438,
 214060,
 227442,
 227444,
 101235,
 83836,
 73993,
 101230,
 104208,
 129985,
 131772,
 150462,
 154649,
 154663,
 154673,
 154719,
 154723,
 154751,
 154756,
 154762,
 163738,
 163775,
 163776,
 163777,
 163778,
 163788,
 174076,
 174079,
 174082,
 174089,
 174098,
 174100,
 174105,
 174108,
 174121,
 174124,
 174127,
 174129,
 174131,
 175604,
 175606,
 175607,
 175609,
 175611,
 175612,
 175613,
 175614,
 175616,
 175618,
 83913,
 83921,
 185180,
 185184,
 185191,
 188623,
 188651,
 188660,
 191422,
 191430,
 191455,
 191458,
 191464,
 191466,
 191471,
 191472,
 191473,
 191474,
 191477,
 191479,
 191483,
 191486,
 191489,
 206146,
 206150,
 206172,
 206180,
 206186,
 206582,
 206675,
 206767,
 207879,
 207889,
 208620,
 210113,
 210119,
 210123,
 210129,
 210439,
 211185,
 211194,
 211709,
 213869,
 213872,
 216948,
 216954,
 80424,
 63432,
 68355,
 70300,
 124786,
 124790,
 124826,
 148563,
 58068,
 68365,
 217321,
 60397,
 99261,
 83586,
 83651,
 83713,
 120798,
 122070,
 85230,
 149809,
 113669,
 113673,
 113681,
 156531,
 156574,
 87247,
 204815,
 204822,
 204870,
 204962,
 205294,
 207851,
 210403,
 210413,
 210414,
 210415,
 210429,
 210444,
 210451,
 210430,
 226425,
 99211,
 115562,
 115578,
 116120,
 120595,
 109013,
 109894,
 109900,
 109922,
 109937,
 111568,
 111582,
 117834,
 120401,
 153474,
 153476,
 155049,
 156467,
 90327,
 98562,
 101557,
 135669,
 88353,
 94825,
 75033,
 178641,
 84702,
 84706,
 84731,
 97196,
 97443,
 101035,
 83508,
 83519,
 83531,
 83546,
 83546,
 100475,
 183314,
 57303,
 103759,
 100389,
 100405,
 100415,
 100440,
 168249,
 168275,
 168293,
 168357,
 169491,
 169804,
 169821,
 169832,
 169862,
 169866,
 169875,
 171227,
 171416,
 171429,
 171438,
 171593,
 171612,
 171617,
 171629,
 172701,
 172706,
 172710,
 172715,
 178158,
 178210,
 178228,
 178236,
 178246,
 178287,
 179338,
 179342,
 180046,
 180050,
 180059,
 183285,
 184061,
 184223,
 184255,
 201090,
 201117,
 201131,
 201139,
 201240,
 201266,
 201268,
 201295,
 202696,
 203062,
 203064,
 203122,
 68707,
 204786,
 204803,
 225297,
 141392,
 70292,
 151475,
 103365,
 129215,
 151432,
 151532,
 151544,
 151548,
 109808,
 128090,
 97211,
 151556,
 151618,
 154893,
 217011,
 217007,
 141403,
 151413,
 151508,
 151521,
 151528,
 156996,
 154902,
 157006,
 207954,
 211870,
 213146,
 157060,
 157064,
 157068,
 157080,
 157086,
 157092,
 141456,
 113904,
 100299,
 84710,
 68407,
 157010,
 154560,
 100316,
 119790,
 100322,
 103373,
 106608,
 119771,
 157151,
 157221,
 83519,
 157171,
 86707,
 103377,
 103993,
 119782,
 141415,
 151453,
 87263,
 106644,
 113908,
 113913,
 154870,
 156984,
 157177,
 157016,
 151540,
 128229,
 76071,
 103836,
 103845,
 112470,
 112609,
 112614,
 118726,
 119709,
 119721,
 120597,
 120612,
 122622,
 127519,
 127570,
 128240,
 128265,
 129176,
 129180,
 129204,
 129245,
 129412,
 141238,
 141313,
 141767,
 148349,
 148353,
 112573,
 119693,
 119713]

THIRD_TRANCHE = {
    "non_compliant":"compliant",
    "com_excep":"compliant",
    "com_correc":"compliant",

}

DICT = {
        "894805": THIRD_TRANCHE,
        "894804": SECOND_TRANCHE
}


def replace_all_pattern(project_form, xml):
    patterns_dict = DICT.get(str(project_form))
    for pattern, new_pattern in patterns_dict.items():
        xml = xml.replace(pattern, new_pattern)
    return xml


class Command(BaseCommand):
    ''' This command replace string in xml '''

    help = 'fixes instances whose root node names do not match their forms'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-form-pk',
            type=int,
            dest='project_fxf',
            help='consider only instances whose Project Form ID is equal '\
                 'to this number'
        )
        parser.add_argument(
            '--pattern',
            type=str,
            dest='pattern',
            help='consider only instances whose matches this pattern'
        )

    def handle(self, *args, **options):
        project_fxf = options["project_fxf"]
        pattern = options["pattern"]
        if project_fxf in ["894804", 894804]:
            instances = Instance.objects.filter(pk__in=SECOND_TRANCHE_SUBMISSIONS).only('xml')
        elif project_fxf in ["894805", 894805]:
            instances = Instance.objects.filter(pk__in=THIRD_TRANCHE_SUBMISSIONS).only('xml')
        matches = instances.annotate(
            match=Func(
                F('xml'),
                Value(pattern),
                function='regexp_matches'
            )
        ).values_list('pk', 'match')

        instances = [i[0] for i in matches]

        if not instances:
            self.stderr.write('No Instances found.')
            return
        self.stderr.write('{} instance found for  pattern {}'.format(len(instances), pattern))

        for instance_id in instances:

            queryset = Instance.objects.filter(pk=instance_id).only('xml')
            ih = InstanceHistory(xform_instance=queryset[0],xml=queryset[0].xml)
            ih.save()
            fixed_xml = replace_all_pattern(project_fxf,queryset[0].xml)
            new_xml_hash = Instance.get_hash(fixed_xml)
            queryset.update(xml=fixed_xml, xml_hash=new_xml_hash)
            new_instance = queryset[0]
            new_instance.xml = fixed_xml
            new_instance.xml_hash=new_xml_hash
            update_mongo(new_instance)

        self.stderr.write(
            '\nFinished {} '.format(
                instance_id,)
        )

