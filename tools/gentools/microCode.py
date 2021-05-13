
# import re
# import ValueError
import logging
import os
import copy
import sys
from shutil import copyfile
import distutils
# from distutils import dir_util
# import boto3
# from botocore.exceptions import ClientError
# import sys

# from microUtils import writeYaml,loadServicesMap, loadConfig, ansibleSetup
from microUtils import ansibleSetup, describe_role, writeJSON
from microUtils import writeYaml, loadServicesMap
# from microUtils import writeJSON
# from microUtils import loadServicesMap
from microUtils import account_replace, account_inject_between
# from microUtils import describe_role

# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
# dir_path = os.path.dirname(__file__)
dir_path = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)

class CodeMolder():
    origin = None

    def __init__(self, directory):
        global dir_path
        temp = "%s/%s" % (dir_path, directory)
        self.temp = temp
        if not os.path.exists(temp):
            os.makedirs(temp)
        else:
            logger.warning(f'Directory {temp} already exists--remove or rename.')

    def get_Dynamolambdas(self, table, aconnect, nextMarker=None):
        client = aconnect.__get_client__('lambda')
        if nextMarker:
            functions = client.list_functions(Marker=nextMarker)
        else:
            functions = client.list_functions()
        all_Lambdas = functions['Functions']
        if 'NextMarker' in functions:
            nextMarker = functions['NextMarker']
            lambdas = self.get_Dynamolambdas(table, aconnect, nextMarker)
            all_Lambdas = lambdas + all_Lambdas

        filtered = []
        for ls in all_Lambdas:
            lname = ls['FunctionName']
            eventMaps = client.list_event_source_mappings(
                FunctionName=lname)['EventSourceMappings']

            for event in eventMaps:
                source = event['EventSourceArn']
                if 'dynamodb' in source and table in source:
                    ls.update(event)
                    filtered.append(ls)
                    break
        return filtered

    def scan_lambdaTriggers(self, target, aconnect, arn):
        lambdas = self.get_Dynamolambdas(target, aconnect)
        triggers = []
        for lb in lambdas:
            print(lb)
            # namein = lb['functionArn'].split('function:')[1]
            namein = lb['FunctionName']
            event_source = lb['EventSourceArn'].split('/')[:2]
            event_source = "/".join(event_source)
            obj = {"function_name": namein, "state": "present", "event_source": event_source,
                   "function_arn": lb['FunctionArn'], "source_params": None}
            state = True if lb['State'] == 'Enabled' else False
            source_params = {"source_arn": event_source, "enabled": state,
                             "starting_position": "LATEST", "batch_size": lb['BatchSize']}
            additionalParams = ["MaximumBatchingWindowInSeconds", "ParallelizationFactor", "DestinationConfig",
                                "MaximumRecordAgeInSeconds", "BisectBatchOnFunctionError", "MaximumRetryAttempts"]
            for add in additionalParams:
                if add in lb:
                    source_params.update({add: lb[add]})
            obj.update({"source_params": source_params})
            obj['TableName'] = target
            triggers.append(obj)
        return triggers


# - name: DynamoDB stream event mapping
#   lambda_event:
#     state: "{{ state | default('present') }}"
#     event_source: stream
#     function_name: "{{ function_name }}"
#     alias: Dev
#     source_params:
#       source_arn: arn:aws:dynamodb:us-east-1:123456789012:table/tableName/stream/2016-03-19T19:51:37.457
#       enabled: True
#       batch_size: 100
#       starting_position: TRIM_HORIZON
#   with_items: "{{ project.dynamodbs }}"
#   when: '{{ item.hash_key_name is not defined and item.read_capacity is defined and not (item.state=="absent")}}'


    def dynamoSimpleTypes(self, type):
        if "s" in type.lower():
            return "STRING"
        if "n" in type.lower():
            return "NUMBER"
        if "b" in type.lower():
            return "BINARY"
        return "STRING"

    def behavior_describe(self, target, aconnect):
        client = aconnect.__get_client__('codebuild')

        # Get job definition
        try:
            dTable = client.batch_get_projects(names=[target])['projects'][0]
        except client.exceptions.ResourceNotFoundException as ex:
            logger.error(ex)
            sys.exit('[E] Stopped')

        # cb_arn = dTable['arn']
        cb_name = dTable['name']
        cb_source = dTable['source']
        cb_source_version = dTable['sourceVersion']  # NOT SUPPORTED IN ANSIBLE
        cb_artifacts = dTable['artifacts']
        cb_service_role = dTable['serviceRole']
        cb_env = dTable['environment']
        cb_timeout = dTable['timeoutInMinutes']

        obj = {
            'name': cb_name,
            'source': cb_source,
            'sourceVersion': cb_source_version,  # NOT SUPPORTED IN ANSIBLE
            'artifacts': cb_artifacts,
            'serviceRole': cb_service_role,
            'environment': cb_env,
            'timeoutInMinutes': cb_timeout
        }
        return obj

    def define(self, target, aconnect, accountOrigin, accounts=[], sendto=None):
        self.origin = accountOrigin
        acctID = acctPlus = accountOrigin['account']

        # Support multiple regions in same account
        if 'sharedas' in accountOrigin:
            acctPlus = acctID + accountOrigin['sharedas']

        assumeRole = accountOrigin['assume_role']
        tableObj = self.behavior_describe(target, aconnect)

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
        roles, resourceRole = describe_role('codebuild-generic', aconnect, acctID, False)
        taskMain, rootFolder, targetLabel = ansibleSetup( self.temp, target, True)
        taskWithFiles = [
            {"import_tasks": "../aws/sts.yml", "vars": {"project": '{{ project }}'}},
            {"import_tasks": "../aws/IAM.yml", "vars": {"project": '{{ project }}'}},
            {"import_tasks": "../aws/codebuild.yml", "vars": {"project": '{{ project }}'}}
        ]
        taskRaw = taskMain[0]
        taskMain = [taskRaw] + taskWithFiles

        # Write
        logger.info('Writing main yaml in tasks folder...')
        writeYaml(taskMain, f'{rootFolder}/tasks/main')

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
                "policies": []
            }
            if assumeRole:
                accDetail.update({"cross_acct_role": account['role']})
            defaultVar = {targetLabel: accDetail}

            tobj_copy = copy.deepcopy(tableObj)
            t_name = tableObj['name']
            if suffix:
                t_name = "%s%s" % (t_name, suffix)
                tobj_copy.update({"name": t_name})

            # add Policies
            role_list = []
            role_policies = []

            # Building main.yaml (not tasks)
            for role in roles:
                rName = role['name']
                rData = role['data']
                rDescribe = "SB-Default no description found"
                if 'Description' in rData:
                    rDescribe = rData['Description']
                rNamePlcy = "%s_%s" % (rName, "trust")
                trustIn = "%s/%s/%s" % (rootFolder, 'files', rNamePlcy)
                # print ".... dude.....look up......"
                rfile = writeJSON(rData['AssumeRolePolicyDocument'], trustIn)
                # print (role)
                # exit()
                roleIn = {
                    "name": rName,
                    "trust_policy_filepath": "{{ role_path }}/files/%s" % rfile,
                    "type": "role",
                    "state": "present",
                    "path": rData['Path'],
                    "description": rDescribe
                }
                # polices are in seperate list!!!!!
                plcies = role['policies']
                plcyNames = []
                for rp in plcies:
                    rpName = rp['PolicyName']
                    rpDoc = rp['PolicyDocument']
                    rpDescription = rp['Description']
                    rpPath = rp['Path']
                    fpIn = "%s/%s/%s" % (rootFolder, 'files', rpName)
                    pfile = writeJSON(rpDoc, fpIn)
                    plcyNames.append(rpName)
                    rPolicy = {
                        "name": rpName,
                        "state": "present",
                        "type": "policy",
                        "policy_document": "{{ role_path }}/files/%s" % pfile
                    }
                    role_policies.append(rPolicy)
                roleIn.update({"action_policy_labels": plcyNames})
                role_list.append(roleIn)
                # CREATE POLICIES

            # DATA MANIPULATION
            current_env_name = tableObj['name'].split('-')[-1]
            target_env_name = account['all'].split('-')[-1].lower()
            # If it ends in '-{ENV}' swap env names
            if current_env_name != target_env_name:
                tobj_copy['name'] = tobj_copy['name'].replace(current_env_name, target_env_name)
            # Update env job variable
            if 'environmentVariables' in tobj_copy['environment']:
                for var in tobj_copy['environment']['environmentVariables']:
                    if 'ENV' in var['name']:
                        var['value'] = target_env_name.upper()

            defaultVar[targetLabel].update({"policies": role_policies})
            defaultVar[targetLabel].update({"roles": role_list})
            defaultVar[targetLabel].update({"codebuild": [tobj_copy]})

            option = "main_%s" % account['all']
            mainIn = "%s/%s/%s" % (rootFolder, 'defaults', option)
            writeYaml(defaultVar, mainIn)
            account_replace("%s.yaml" % mainIn, str(acctID), str(simple_id))
            verify = True
            if suffix not in target and suffix:
                account_inject_between("%s.yaml" % mainIn, ":function:", "\n", suffix, 'suffix', verify)
                account_inject_between("%s.yaml" % mainIn, "TableName: ", "\n", suffix, 'suffix', verify)
                account_inject_between("%s.yaml" % mainIn, ":table/", "\n", suffix, 'suffix', verify)

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
            targets = ['%s' % target]
            rootYML = [{"name": "micro modler for lambda-%s" % target,
                        "hosts": "dev",
                        "remote_user": "root",
                        "roles": targets}]
            # ansibleRoot
            writeYaml(rootYML, ansibleRoot, target)
        return acctID, target, acctTitle, True


if __name__ == "__main__":
    cb = CodeMolder()
    cb.define()
