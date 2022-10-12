# This code is used to create Ansible files for deploying Lambda's
# all that is needed is a target Lambda, tests, and it will do the rest.
# finds associate roles and policies
# creates Ansible modules based on those policies and roles
# defines the Lambdas and creates them with tests
# finds api-gateways or other events
# if api found defines the security needed. creates modules for deployment with templates
# import re
# from time import sleep
import os
from shutil import copyfile
import copy
import logging
from pprint import pprint
import distutils

from tools.gentools import awsconnect

from tools.gentools.awsconnect import awsConnect
import json

from tools.gentools.microUtils import writeYaml
from tools.gentools.microUtils import writeJSON
from tools.gentools.microUtils import account_replace
from tools.gentools.microUtils import ansibleSetup, file_replace_obj_found
from tools.gentools.microUtils import describe_role
from tools.gentools.microUtils import loadServicesMap
from tools.gentools.microUtils import s3_get
# from tools.gentools.microUtils import config_updateRestricted

# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
# dir_path = os.path.dirname(__file__)
dir_path = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)


class StorageMolder():
    origin = None
    finalDir_output = None
    bucket_path = 'data/lambdas/XX-CEDAR'
    cedar_statement_name = "CEDAR_AllowCopy"
    source_bucket = None
    source_acct = None
    # source_tmp_bucket = None
    # source_tmp_acct = None
    svc_type = 's3c'

    temp = None

    def __init__(self, directory, svc="-S3C", root=None):
        global dir_path
        self.svc_type = 's3c' if "S3C" in svc else 's3'
        
        self.directory = directory
        if root:
            temp = "%s/%s" % (root, directory)
        else:
            temp = "%s/%s" % (dir_path, directory)
        self.temp = temp
        if not os.path.exists(temp):
            os.makedirs(temp)
        else:
            logger.warning(f'Directory {temp} already exists--remove or rename.')

    def source_policy_append(self, policy, source, target, sourcebucket):
        statement = {
                "Sid": f"{ self.cedar_statement_name }",
                "Effect": "Allow",
                "Principal": {
                    "AWS": f'["{target}", "{source}"]'
                },
                "Action": [
                    "s3:ListBucket",
                    "s3:GetObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{sourcebucket}/*",
                    f"arn:aws:s3:::{sourcebucket}"
                ]
            }
        for s in policy['Statement']:
            if s['Sid'] == self.cedar_statement_name:
                del s
        policy['Statement'].append(statement)
        return statement

    def Cooker(self, target):
        self.behavior_describe(target)

    def find_bucket_files_filtered(self, aconnect, target, path):
        s3_client = aconnect.__get_client__('s3')
        response = s3_client.list_objects_v2(Bucket=target, Prefix=path)
        files = []
        for obj in response['Contents']:
            if obj['Key'].endswith('/'):
                continue
            files.append(obj['Key'])
        return files

    def behavior_describe(self, target, aconnect):
        #client = boto3.client('lambda')
        s3_client = aconnect.__get_client__('s3')
        s3_resource = aconnect.__get_resource__('s3')
        print(target)
        policy_str = s3_client.get_bucket_policy(Bucket=target)
        policy_raw = json.loads(policy_str['Policy'])
        #what roles found?
        # root_source = f"arn:aws:iam::{self.source_tmp_acct}:root"
        # root_target = f"arn:aws:iam::{self.source_acct}:root"  #this will be replaced with target later
        roles_final = []
        for s in policy_raw['Statement']:
            #find role in statements
            if 'Principal' in s:
                if 'AWS' in s['Principal']:
                    prince = s['Principal']['AWS']
                    if isinstance(prince, str):
                        if ':role/' in prince:
                            roles_final = roles_final + [prince]
                    elif isinstance(prince, list):
                        for p in prince:
                            if ':role/' in p:
                                roles_final = roles_final + [p]
        # policy = self.source_policy_append(policy_raw, root_source, root_target, target)
        bucket_triggers = s3_client.get_bucket_notification_configuration(Bucket=target)
        bucket_cors = s3_client.get_bucket_cors(Bucket=target)
        if bucket_cors:
            bucket_cor = bucket_cors['CORSRules'][0]
            bucket_cors =[{
                "allowed_origins" : bucket_cor['AllowedOrigins'],
                "allowed_methods" : bucket_cor['AllowedMethods'],
                "allowed_headers" : bucket_cor['AllowedHeaders'],
                "expose_headers" : bucket_cor['ExposeHeaders'],
                "max_age_seconds" : bucket_cor['MaxAgeSeconds']
            }]
        lambda_triggers = []
        if bucket_triggers:
            if 'LambdaFunctionConfigurations' in bucket_triggers:
                lambda_fires = bucket_triggers['LambdaFunctionConfigurations']

                for lt in lambda_fires:
                    trigger = {
                        "state" : "present",
                        "bucket" : target,
                        "id" : lt['Id'],
                        "lambda_arn": lt['LambdaFunctionArn'],
                        "events": lt['Events'],
                    }
                    # print(lt)
                    # raise
                    for fk in lt['Filter']['Key']['FilterRules']:
                        if fk['Name'] == 'Prefix':
                            if fk['Value']:
                                trigger['prefix'] = fk['Value']
                        if fk['Name'] == 'Suffix':
                            if fk['Value']:
                                trigger['suffix'] = fk['Value']
                    lambda_triggers.append(trigger)

       
        # policies = {"copy": policy, "stable": policy_raw}
        return {
                'name': target,
                'statement_copy': self.cedar_statement_name,
                'target': target,
                'roles': roles_final,
                "state": "present", # "has_instances",
            }, policy_raw , lambda_triggers, bucket_cors

    # cluster K8 -CK
    #  python microMolder.py -CK policyport-clover-dev true ENVR.yaml
    # ec2, iam, eks, asg
    # describe nodegroup

    def define(self, target, aconnect, accountOrigin, accounts=[], sendto=None):
        self.origin = accountOrigin
        acctID = acctPlus = accountOrigin['account']
        if 'sharedas' in accountOrigin:
            acctPlus = acctID + accountOrigin['sharedas']
        assumeRole = accountOrigin['assume_role']
        # target will include bucketname + path if copy
        targets = []
        old_target = target
        self.source_bucket = target
        if self.svc_type == 's3c':
            if ',' in target:
                targets = target.split(',')
            else:
                targets = [target]
            self.source_bucket = targets[0].split('/')[0]
            self.source_acct = acctID
            # self.source_tmp_acct = "CEDAR_SOURCE_ID"
            # self.source_tmp_bucket = "CEDAR_SOURCE_BUCKET"
            target = targets[0].replace('/', '_')
            raw_target = "/".join(targets[0].split('/')[1:])
            targets[0] = raw_target
        BUCKET_MAP = loadServicesMap(accountOrigin['services_map'], 'S3', self.bucket_path)
        SIGNER_MAP = loadServicesMap(accountOrigin['services_map'], 'signer', self.bucket_path)
        DOMAIN_MAP = loadServicesMap(accountOrigin['services_map'], 'domains', self.bucket_path)
        CFRONT_MAP = loadServicesMap(accountOrigin['services_map'], 'cloudfront', self.bucket_path)
        containerObj, s3_policy, bucket_triggers, bucket_cors = self.behavior_describe(self.source_bucket, aconnect)
        roles = []
        for rrls in containerObj['roles']:
            rle, resourceRole = describe_role(rrls, aconnect, self.origin['account'], False)
            roles= roles + rle


        target_file = '%s_%s' % (acctID, target)

        if self.svc_type == 's3c':
            bucket_triggers = []
            bucket_cors = []
            s3_policy = None
            # drop triggers
            # drop cors
            # drop policy

        # for trigger in triggers:
        #     trigger
        # acctTitle = None
        skipping = error_path = None
        if 'error_path' in accountOrigin:
            error_path = accountOrigin['error_path']
        if 'skipping' in accountOrigin:
            skipping = accountOrigin['skipping']
        # error_path: /Users/astro_sk/Documents/TFS/Ansible_Deployer
        if not skipping:
            skipping = {
                "methods": False,
                "options": False,
                "models": False,
                "stage": False,
                "resources": False
            }

        # taskMain, rootFolder, targetLabel = ansibleSetup( self.temp, target, True)
        taskMain, rootFolder, targetLabel = ansibleSetup(self.temp, target_file, True)
        taskWithFiles = [
            {"import_tasks": "../aws/sts.yml", "vars": {"project": '{{ project }}'}},
            {"import_tasks": "../aws/IAM.yml", "vars": {"project": '{{ project }}'}},
            # {"import_tasks": "../aws/cr_dynamodb.yml", # add ECR, EKS, ECS, ELB, Taskdef, TaskFam
            #     "vars": {"project": '{{ project }}'}}
        ]
        taskRaw = taskMain[0]
        taskMain = [taskRaw] + taskWithFiles
        taskMain.append({"import_tasks": "../aws/s3.yml",
                         "vars": {"project": '{{ project }}'}})
        #############################################
        #############################################
        # ####### write YAML to file in tasks  #######
        #############################################
        #############################################
        option = "main"
        mainIn = "%s/%s/%s" % (rootFolder, 'tasks', option)
        writeYaml(taskMain, mainIn)

        #############################################
        # ##########   END WRITE  ####################
        #############################################
        #############################################
        # if 'services_map' in accountOrigin:
        #     mapfile = accountOrigin['services_map']
        #     serviceMap = loadServicesMap(mapfile, None)
        bucket_in = {"name": self.source_bucket, "state": "present"}
        files_attached = []
        if s3_policy:
            fpIn = "%s/%s/%s" % (rootFolder, 'files', "s3_policy")
            pfile = writeJSON(s3_policy, fpIn)
            pfile_x ="/".join(fpIn.split('/')[:-1])+ "/"+ pfile
            files_attached.append(pfile_x)
            bucket_in['policy_document'] = "{{ role_path }}/files/%s" % pfile
        if bucket_cors:
            bucket_in['cors']= bucket_cors
        #####################################################
        #####################################################
        #### [START]  COPY FILES FIRST  #####################
        #####################################################
        #####################################################
        if self.svc_type == 's3c' and targets:
            # drop triggers
            # drop cors
            # drop policy
            final_targets = []
            for s3file in targets:
                s3_file = {}
                if "/" in s3file and '.' not in s3file:
                    nested_files = self.find_bucket_files_filtered(aconnect, self.source_bucket, s3file)
                    for nf in nested_files:
                        fpIn = "%s/%s/%s" % (rootFolder, 'files/bucket', nf)
                        dir = os.path.dirname(fpIn)
                        if not os.path.exists(dir):
                            os.makedirs(dir)
                        s_file, s_ext = os.path.splitext(nf)
                        if s_ext in ['.json', '.yaml', '.yml','.js','.txt'] or '.env.' in nf:
                            files_attached.append(fpIn)
                        s3_get(self.source_bucket, nf, fpIn, aconnect.__get_resource__('s3'))
                        s3_file.update({'name': nf, "s3_document": "{{ role_path }}/files/bucket/%s" % nf})
                        final_targets.append(s3_file)
                else:
                    fpIn = "%s/%s/%s" % (rootFolder, 'files/bucket', s3file)
                    dir = os.path.dirname(fpIn)
                    if not os.path.exists(dir):
                        os.makedirs(dir)
                    s_file, s_ext = os.path.splitext(s3file)
                    if s_ext in ['.json', '.yaml', '.yml','.js','.txt']:
                        files_attached.append(fpIn)

                    s3_get(self.source_bucket, s3file, fpIn, aconnect.__get_resource__('s3'))
                    s3_file.update({'name': s3file, "s3_document": "{{ role_path }}/files/bucket/%s" % s3file})
                    final_targets.append(s3_file)
            if final_targets: #simplify
                bucket_in.update({'bucket_dir': "{{ role_path }}/files/bucket"})

        #####################################################
        #### [END] ####### FILES   ABOVE --##################
        #####################################################

        for akey, account in accounts.items():
            default_region = 'us-east-1'
            if akey == acctPlus:
                acctTitle = account['title']

            eID = account['eID']
            append = suffix = ''
            if 'suffix' in account or 'prefix' in account or 'contains' in account:
                if 'suffix' in account:
                    suffix = account['suffix']

            if 'region_deploy' in account:
                default_region = account['region_deploy']
            simple_id = akey
            if "_" in simple_id:
                simple_id = simple_id.split("_")[0]
            accDetail = {
                "account_id": simple_id,
                "error_path": error_path,
                "skipping": skipping,
                "env": account['title'],
                "role_duration": 3600,
                "region": default_region,
                "eid": eID,
                "roles": [],
                "policies": [],
                "buckets": [],
            }
            
            
            if assumeRole:
                accDetail.update({"cross_acct_role": account['role']})
            defaultVar = {targetLabel: accDetail}
            #####################################
            # add Policies
            #####################################
            role_list = []
            role_policies = []

            for role in roles:
                rName = role['name']
                rData = role['data']
                rDescribe = "Default-no description found"
                if 'Description' in rData:
                    rDescribe = rData['Description']
                rNamePlcy = "%s_%s" % (rName, "trust")
                trustIn = "%s/%s/%s" % (rootFolder, 'files', rNamePlcy)
                # print ".... dude.....look up......"
                rfile = writeJSON(rData['AssumeRolePolicyDocument'], trustIn)
                pfile_x ="/".join(trustIn.split('/')[:-1])+ "/"+ rfile
                if pfile_x not in files_attached:
                    files_attached.append(pfile_x)
                # print (role)
                # exit()
                roleIn = {
                    "name": rName,
                    "trust_policy_filepath": "{{ role_path }}/files/%s" % rfile,
                    "type": "role",
                    "state": "present",
                    "aws_path": rData['Path'],
                    "description": rDescribe
                }
                # polices are in seperate list!!!!!
                plcies = role['policies']
                plcyNames = []
                # print(plcies)
                # raise
                for rp in plcies:
                    rpName = rp['PolicyName']
                    rpDoc = rp['PolicyDocument']
                    rpDescription = rp['Description']
                    rpPath = rp['Path']
                    fpIn = "%s/%s/%s" % (rootFolder, 'files', rpName)
                    pfile = writeJSON(rpDoc, fpIn)
                    pfile_x ="/".join(fpIn.split('/')[:-1])+ "/"+ pfile
                    if pfile_x not in files_attached:
                        files_attached.append(pfile_x)
                    plcyNames.append(rpName)
                    rPolicy = {
                        "name": rpName,
                        "state": "present",
                        "aws_path": rpPath,
                        "description": rpDescription,
                        "type": "policy",
                        "policy_document": "{{ role_path }}/files/%s" % pfile
                    }
                    role_policies.append(rPolicy)
                roleIn.update({"action_policy_labels": plcyNames})
                role_list.append(roleIn)
                # CREATE POLICIES

            defaultVar[targetLabel].update({"policies": role_policies})
            defaultVar[targetLabel].update({"roles": role_list})

            ########################################################

            #####################################
            # write files
            #####################################


            defaultVar[targetLabel].update({"buckets": [bucket_in]})
            defaultVar[targetLabel].update({"bucket_triggers": bucket_triggers})
            

            option = "main_%s" % account['all']
            mainIn = "%s/%s/%s" % (rootFolder, 'defaults', option)
            writeYaml(defaultVar, mainIn)
            yaml_main = "%s.yaml" % mainIn
            account_replace(yaml_main, str(targetLabel), "<environment_placeholder>")
            account_replace(yaml_main, str(acctID), str(simple_id))
            account_replace(yaml_main, "<environment_placeholder>", str(targetLabel))
            ALL_MAPS = [DOMAIN_MAP, BUCKET_MAP, SIGNER_MAP, CFRONT_MAP]
            ########################################################
            ########################################################
            # STRING REPLACE ON ALL MAPS --BEGINS--- here #####
            file_replace_obj_found(yaml_main, akey, acctPlus, ALL_MAPS)
            for file_in in files_attached:
                tmp_dir =  "%s/files_%s" % (rootFolder, account['all'])
                match_dir = "%s/%s" % (rootFolder, 'files')
                if not os.path.exists(tmp_dir):
                     os.makedirs(tmp_dir)
                clean_match = file_in.split(match_dir)[1]
                dst = "%s/%s" % (tmp_dir, clean_match[1:] if clean_match.startswith("/") else clean_match)
                dst_dir = "/".join(dst.split('/')[:-1])
                if not os.path.exists(dst_dir):
                    os.makedirs(dst_dir)
                copyfile(file_in, dst)
                file_replace_obj_found(dst, akey, acctPlus, ALL_MAPS, True)
            # STRING REPLACE ON ALL MAPS ---ENDS-- here #####
            ########################################################
            ########################################################

        if sendto:
            logger.info('Creating a main.yaml for ansible using dev')
            opt = "main_%s.yaml" % accountOrigin['all']
            src = "%s/%s/%s" % (rootFolder, 'defaults', opt)
            opt2 = "main.yaml"
            dst = "%s/%s/%s" % (rootFolder, 'defaults', opt2)
            copyfile(src, dst)
            logger.info('COPY START...')
            logger.info(f'{rootFolder} --> {sendto}')
            distutils.dir_util.copy_tree(rootFolder, sendto)
            ansibleRoot = sendto.split('roles/')[0]
            # targets = ['%s' % target]

            targets = [target_file]
            rootYML = [{"name": "micro molder for Storage-%s" % target,
                        "hosts": "dev",
                        "remote_user": "root",
                        "roles": targets}]
            # raise
            # ansibleRoot
            # print("***********************")
            # print(target)
            # print(ansibleRoot)
            # print(target_file)
            # print(sendto)
            # print(rootYML, ansibleRoot, target_file)
            # raise
            writeYaml(rootYML, ansibleRoot, target_file)

        self.finalDir_output = rootFolder
        return acctID, target, acctTitle, True


# python microContainer.py role accid
if __name__ == "__main__":
    pass
    # CMD_STRING = sys.argv
    # if len(CMD_STRING) < 3:
    #     logger.error('Not enough arguments')
    #     sys.exit()
    # role = sys.argv[1]
    # accid = sys.argv[2]
    # eid = sys.argv[3]
    # region = 'us-east-1'
    # awsconnect.stsClient_init()
    # sts_client = awsconnect.stsClient
    # print(f'   ------------------------')
    # print(f'    Account: {accid}')
    # print(f"    Account: {eid}'")
    # print(f"    Account: {role}")
    # print(f'   ------------------------')
    # aconnect = awsConnect(accid, eid, role, sts_client, region)
    # aconnect.connect()
    # cm = ContainerMolder()
    # cm.define("-CK", aconnect, origin, global_accts, sendto)

#  python microMolder.py -CF cr-portal-dev true ENVR.yaml '/Users/astro_sk/Documents/TFS/Ansible_Deployer/ansible/roles/CR-Cfront'
