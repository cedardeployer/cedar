
# import re
# import ValueError
import copy
import distutils
import logging
import os
import sys
from shutil import copyfile

from microUtils import account_replace, account_inject_between
from microUtils import ansibleSetup, describe_role, writeJSON, writeYaml

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

    def behavior_describe(self, target, aconnect):
        client = aconnect.__get_client__('codebuild')

        # Get job definition
        try:
            dTable = client.batch_get_projects(names=[target])['projects'][0]
        except client.exceptions.ResourceNotFoundException as ex:
            logger.error(ex)
            sys.exit('[E] Stopped')

        # TODO: Need custom template to support source_version aka branch of repo
        # TODO: Flesh out the rest of this data for more advanced jobs
        """
        "msg": "Unsupported parameters for (aws_codebuild) module: 
        source_version Supported parameters include: 
        artifacts, aws_access_key, aws_ca_bundle, aws_config, aws_secret_key, cache, 
        debug_botocore_endpoint_logs, description, ec2_url, encryption_key, environment, 
        name, profile, region, security_token, service_role, source, state, tags, 
        timeout_in_minutes, validate_certs, vpc_config"
        """

        obj = {
            'name': dTable['name'],
            'source': dTable['source'],
            'sourceVersion': dTable['sourceVersion'],  # NOT SUPPORTED IN ANSIBLE
            'artifacts': dTable['artifacts'],
            'serviceRole': dTable['serviceRole'],
            'environment': dTable['environment'],
            'timeoutInMinutes': dTable['timeoutInMinutes']
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
        #taskMain, rootFolder, targetLabel = ansibleSetup( self.temp, target, True)
        taskMain, rootFolder, targetLabel = ansibleSetup( self.temp, f'{acctID}_{target}', True)
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
            # Temporarily change tag with accountID so it's not overwritten
            account_replace("%s.yaml" % mainIn, str(targetLabel), str('MUST_NOT_OVERWRITE'))
            # Replace all other instances of that accountID
            account_replace("%s.yaml" % mainIn, str(acctID), str(simple_id))
            # Put the tag back
            account_replace("%s.yaml" % mainIn, str('MUST_NOT_OVERWRITE'), str(targetLabel))
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
            targets = [f'{acctID}_{target}']
            rootYML = [{"name": "micro modler for lambda-%s" % target,
                        "hosts": "dev",
                        "remote_user": "root",
                        "roles": targets}]
            # ansibleRoot
            writeYaml(rootYML, ansibleRoot, f'{acctID}_{target}')
        return acctID, target, acctTitle, True


if __name__ == "__main__":
    print('This is for defining CodeBuild jobs from options passed in by runner')
    print('ex: python mainDeployer.py -CB dev "test" "api-tests-dev" ../ENVR.yaml null true')
