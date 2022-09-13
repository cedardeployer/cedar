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


from tools.gentools.microUtils import writeYaml
from tools.gentools.microUtils import writeJSON
from tools.gentools.microUtils import account_replace
from tools.gentools.microUtils import ansibleSetup
from tools.gentools.microUtils import describe_role
from tools.gentools.microUtils import loadServicesMap
# from tools.gentools.microUtils import config_updateRestricted

# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
# dir_path = os.path.dirname(__file__)
dir_path = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)


class ContainerMolder():
    origin = None
    finalDir_output = None
    bucket_path = 'data/lambdas/XX-CEDAR'
    svc_type = 'eks'

    temp = None

    def __init__(self, directory, svc="-CK", root=None):
        global dir_path
        if "CK" in svc:
            self.svc_type = 'eks'
        elif "CS" in svc:
            self.svc_type = 'ecs'
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

    def Cooker(self, target):
        lambda_describe(target)

    def eks_nodegroup_describe(self, client, target):
        node_groups = []
        ascale_names = []
        autoscale_group = []
        c_ngroups = client.list_nodegroups(clusterName=target)
        for ngroups in c_ngroups['nodegroups']:
            ngroup = client.describe_nodegroup(clusterName=target, nodegroupName=ngroups)
            if 'resources' in ngroup['nodegroup']:
                if 'autoScalingGroups' in ngroup['nodegroup']['resources']:
                    for ascale in ngroup['nodegroup']['resources']['autoScalingGroups']:
                        if ascale['name'] not in ascale_names:
                            ascale_names.append(ascale['name'])
            node_groups.append(ngroup['nodegroup'])
        for ascale in ascale_names:
            ascale_info = client.describe_nodegroup(clusterName=target, nodegroupName=ascale)
            autoscale_group.append(ascale_info)
        return node_groups, autoscale_group

    def eks_launchTemplates_describe(self, client, target):
        launch_templates = []
        ltemplate = client.describe_launch_templates()
        print(ltemplate['LaunchTemplates'])
        for lt in ltemplate['LaunchTemplates']:
            print("********-----**----********")
            print(lt)
            print("....")
            print(lt['LaunchTemplateId'])
            print("********-----**----********")
            lt2 = client.get_launch_template_data(InstanceId=lt['LaunchTemplateId'])
            if lt2['userData']:
                if lt2['userData'].find(target) != -1:
                    launch_templates.append(lt2)
        return launch_templates

    def eks_cluster_describe(self, client, target):
        getCL = client.describe_cluster(name=target)
        if not 'cluster' in getCL:
            raise ValueError("[E] Cluster Not found (%s) PLEASE check / fix and try again" % (target))
        return getCL

    def ecs_cluster_describe(self, client, target):
        print("******CLUSTER*******")
        getCL = client.describe_clusters(clusters=[target])
        print(getCL)
        return getCL

    def ecs_taskfam_describe(self, client, target):
        print("******FAM*******")
        task_families = []
        task_fams = client.list_task_definition_families()
        for tf in task_fams['families']:
            print(tf)
        return task_families

    def ecs_task_describe(self, client, target):    
        print("******TASK DescribE *******")       
        tlist = client.list_tasks(cluster=target)
        task_in = client.describe_tasks(cluster=target, tasks=tlist['taskArns'])
        ecr_imgs = []
        tdef_arn=[]
        task_defs = []
        print("******TASK IN *******")
        for tsk in task_in['tasks']:
            uri = tsk['containers'][0]['image'].split(':')[0]
            ecr_imgs.append(uri)
            tdef_arn.append({
                "clusterArn": tsk['clusterArn'],
                "desiredStatus": tsk['desiredStatus'],
                "launchType": tsk['launchType'],
                "memory": tsk['memory'],
                "overrides": tsk['overrides'],
                "platformVersion": tsk['platformVersion'],
                "taskArn": tsk['taskArn'],
                "taskDefinitionArn": tsk['taskDefinitionArn'],
                "group": tsk['group'],
                "version": tsk['version'],
            })
        print("******DefiNition *******")
        temp_arns=[]
        for tdef in tdef_arn:
            tdd = client.describe_task_definition(taskDefinition=tdef['taskDefinitionArn'])['taskDefinition']
            print("_____00000@@ *******")
            if tdd['taskDefinitionArn'] in temp_arns:
                continue
            temp_arns.append(tdd['taskDefinitionArn'])
            task_defs.append({
                "taskDefinitionArn": tdd['taskDefinitionArn'],
                "family": tdd['family'],
                "executionRoleArn": tdd['executionRoleArn'],
                "networkMode": tdd['networkMode'],
                "containerDefinitions": tdd['containerDefinitions'],
                "volumes": tdd['volumes'],
                "placementConstraints": tdd['placementConstraints'],
                "requiresCompatibilities": tdd['requiresCompatibilities'],
                "cpu": tdd['cpu'],
                "memory": tdd['memory'],
                "volumes": tdd['volumes']
            })
        return tdef_arn, ecr_imgs, task_defs

    def ecr_describe(self, client, target, ecr_imgs):
        print("******ECR*******")
        print(ecr_imgs)
        repos = client.describe_repositories()
        for r in repos['repositories']:
            if r['repositoryUri'] not in ecr_imgs:
                continue
            print("********-----*[R]*----********")
            print(r)
            ecr_imgs = client.describe_images(repositoryName=r['repositoryName'])
            print(".....******IMAGES*******")
            for i in ecr_imgs['imageDetails']: 
                print(i)
        return repos

    def elb_describe(self, client, target):
        print("******ELB*******")
        elbs = client.describe_load_balancers()
        for elb in elbs['LoadBalancerDescriptions']:
            print(elb)
        return elbs


    def behavior_describe(self, target, aconnect):
        #client = boto3.client('lambda')
        ec2 = aconnect.__get_client__('ec2')
        if 'eks' in self.svc_type:  # EKS type here
            client = aconnect.__get_client__('eks')
            getCL = self.eks_cluster_describe(client, target)
            lcf = getCL['cluster']
            node_groups, autoscale_group = self.eks_nodegroup_describe(client, target)
            launch_templates = self.eks_launchTemplates_describe(ec2, target)        
            return {
                    'name': target,
                    'endpoint': lcf['endpoint'],
                    'target': target,
                    'version': lcf['version'],
                    'roleArn': lcf['roleArn'],
                    'resourcesVpcConfig': lcf['resourcesVpcConfig'],
                    'kubernetesNetworkConfig': lcf['kubernetesNetworkConfig'],
                    'logging': lcf['logging'],
                }, node_groups, autoscale_group, launch_templates
        elif 'ecs' in self.svc_type: #ECS type here
            client = aconnect.__get_client__('ecs')
            getCL = self.ecs_cluster_describe(client, target)
            tdef_arn, ecr_imgs, task_defs = self.ecs_task_describe(client, target)
            # fam = self.ecs_taskfam_describe(client, target)
            
    
            ecr = aconnect.__get_client__('ecr')
            containers = self.ecr_describe(ecr, target, ecr_imgs)
                
            elb = aconnect.__get_client__('elb')
            elbs = self.elb_describe(elb, target)
            return {
                    'name': target,
                    'target': target,
                    'roleArn': getCL['clusters'][0]['roleArn'],
                    'elbs': elbs,
                }, tdef_arn, containers, task_defs




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

        NETWORK_MAP = loadServicesMap(accountOrigin['services_map'], 'RDS', self.bucket_path)
        DOMAIN_MAP = loadServicesMap(accountOrigin['services_map'], 'domains', self.bucket_path)
        if self.svc_type == 'eks':
            containerObj, node_groups, autoscale_group, launch_templates = self.behavior_describe(target, aconnect)
        elif self.svc_type == 'ecs':
            containerObj, tdef_arn, ecr_imgs, task_defs = self.behavior_describe(target, aconnect)

        roles, resourceRole = describe_role(containerObj['roleArn'], aconnect, self.origin['account'], False)
        target_file = '%s_%s' % (acctID, target)
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
            {"import_tasks": "../aws/cr_dynamodb.yml", # add ECR, EKS, ECS, ELB, Taskdef, TaskFam
                "vars": {"project": '{{ project }}'}}
        ]
        taskRaw = taskMain[0]
        taskMain = [taskRaw] + taskWithFiles
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
            
            cobj_copy = copy.deepcopy(containerObj)
            t_name = containerObj['name']
            if suffix:
                t_name = "%s%s" % (t_name, suffix)
                cobj_copy.update({"name": t_name})

            defaultVar[targetLabel].update({"clusters": [cobj_copy]})
            if self.svc_type == 'eks':
                defaultVar[targetLabel].update({"node_groups": node_groups})
                defaultVar[targetLabel].update({"autoscale_group": autoscale_group})
                defaultVar[targetLabel].update({"launch_templates": launch_templates})
            elif self.svc_type == 'ecs':
                defaultVar[targetLabel].update({"task_defs": task_defs})
                defaultVar[targetLabel].update({"tdef_arn": tdef_arn})
                defaultVar[targetLabel].update({"ecr_imgs": ecr_imgs})

            option = "main_%s" % account['all']
            mainIn = "%s/%s/%s" % (rootFolder, 'defaults', option)
            writeYaml(defaultVar, mainIn)
            yaml_main = "%s.yaml" % mainIn
            account_replace(yaml_main, str(targetLabel), "<environment_placeholder>")
            account_replace(yaml_main, str(acctID), str(simple_id))
            account_replace(yaml_main, "<environment_placeholder>", str(targetLabel))


            # add Policies
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
                #print (role)
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

            defaultVar[targetLabel].update({"policies": role_policies})
            defaultVar[targetLabel].update({"roles": role_list})

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
            rootYML = [{"name": "micro modler for lambda-%s" % target,
                        "hosts": "dev",
                        "remote_user": "root",
                        "roles": targets}]
            # ansibleRoot
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
