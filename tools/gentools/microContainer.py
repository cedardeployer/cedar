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
from tools.gentools.microUtils import ansibleSetup, file_replace_obj_found
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
        # print("******CLUSTER*******")
        getCL = client.describe_clusters(clusters=[target])
        # print(getCL)
        return getCL

    def ecs_taskfam_describe(self, client, target):
        # print("******FAM*******")
        task_families = []
        task_fams = client.list_task_definition_families()
        # for tf in task_fams['families']:
        #     print(tf)
        return task_families

    def ecs_service_describe(self, client, target, svc_target=None):    
        # print("******TASK DescribE *******")       
        tlist = client.list_tasks(cluster=target)
        task_in = client.describe_tasks(cluster=target, tasks=tlist['taskArns'])
        services_in = client.list_services(cluster=target)
        ecr_imgs = []
        tdef_arn=[]
        task_defs = []
        svc_set=[]
        roles = []
        elbs = []
        # print("******TASK IN *******")
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


        # print("******TASK SERVICES *******")
        for svc in services_in['serviceArns']:
            svc_info = client.describe_services(cluster=target, services=[svc])
            for ss in svc_info['services']:
                cp_strategy = ss['capacityProviderStrategy'][0]['capacityProvider']
                loadbcrs = [ lbs['containerName'] for lbs in ss['loadBalancers'] ]
                elbs = elbs + loadbcrs
                if 'deploymentConfiguration' in ss:
                    if 'maximumPercent' in ss['deploymentConfiguration']:
                        ss['maximum_percent'] = ss['deploymentConfiguration']['maximumPercent']
                    if 'minimumHealthyPercent' in ss['deploymentConfiguration']:
                        ss['minimum_healthy_percent'] = ss['deploymentConfiguration']['minimumHealthyPercent']
                    del ss['deploymentConfiguration']['deploymentCircuitBreaker']
                    del ss['deploymentConfiguration']['maximumPercent']
                    del ss['deploymentConfiguration']['minimumHealthyPercent']
                
                network = ss['networkConfiguration']
                if 'networkConfiguration' in ss:
                    if 'awsvpcConfiguration' in ss['networkConfiguration']:
                        ss['assign_public_ip'] = ss['networkConfiguration']['awsvpcConfiguration']['assignPublicIp']
                        if 'securityGroups' in ss['networkConfiguration']['awsvpcConfiguration']:
                            ss['security_groups'] = ss['networkConfiguration']['awsvpcConfiguration']['securityGroups']
                        if 'subnets' in ss['networkConfiguration']['awsvpcConfiguration']:
                            ss['subnets'] = ss['networkConfiguration']['awsvpcConfiguration']['subnets']
                        del ss['networkConfiguration']['awsvpcConfiguration']['securityGroups']
                        del ss['networkConfiguration']['awsvpcConfiguration']['subnets']
                        del ss['networkConfiguration']['awsvpcConfiguration']['assignPublicIp']
                        network = ss['networkConfiguration']['awsvpcConfiguration']

                sobj = {
                    "name": ss['serviceName'],
                    "state": "present",
                    "cluster": ss['clusterArn'].split('/')[-1],
                    "taskDefinition": ss['taskDefinition'],
                    "loadBalancers": loadbcrs,
                    "serviceRegistries": ss['serviceRegistries'],
                    "desiredCount": ss['desiredCount'],
                    "launchType": cp_strategy if 'FARGATE' in cp_strategy else 'EC2',
                    "capacityProviderStrategy": ss['capacityProviderStrategy'],
                    # "platformVersion": ss['platformVersion'],
                    # "propagateTags": ss['propagateTags'],
                    "role": ss['roleArn'],
                    "placementConstraints": ss['placementConstraints'],
                    "placementStrategy": ss['placementStrategy'],
                    "networkConfiguration": network,
                    "healthCheckGracePeriodSeconds": ss['healthCheckGracePeriodSeconds'],
                    "schedulingStrategy": ss['schedulingStrategy'],
                    "deploymentConfiguration": ss['deploymentConfiguration'],
                    "enableECSManagedTags": ss['enableECSManagedTags'],
                }
                if 'deploymentController' in ss:
                    if 'type' in ss['deploymentController']:
                        sobj['deploymentController'] = ss['deploymentController']
                if sobj['role'] not in roles and 'aws-service-role' not in sobj['role']:
                    roles.append(sobj['role'])
                if not svc_target:
                    svc_set.append(sobj)
                else:
                    if svc_target in ss['serviceName']:
                        svc_set.append(sobj)
                        break
        # print("******DefiNition *******")
        temp_arns=[]
        for tdef in tdef_arn:
            tdd = client.describe_task_definition(taskDefinition=tdef['taskDefinitionArn'])['taskDefinition']
            # print("_____00000@@ *******")
            if tdd['taskDefinitionArn'] in temp_arns:
                continue
            temp_arns.append(tdd['taskDefinitionArn'])
            if tdd['executionRoleArn'] not in roles:
                roles.append(tdd['executionRoleArn'])
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
        return tdef_arn, ecr_imgs, task_defs, svc_set, roles, elbs

    def ecr_describe(self, client, ecr_imgs, targets=None):
        # print("******ECR*******")
        # print(ecr_imgs)
        repos = []
        rr_in = client.describe_repositories()
        for r in rr_in['repositories']:
            if r['repositoryUri'] in ecr_imgs:
                repos.append({"name": r['repositoryName'], "uri": r['repositoryUri']})
        return repos

    def elb_describe(self, client, targets):
        # print("******ELB*******")
        elbs_in = []
        elbs = client.describe_load_balancers()
        target_groups = []
        target_gs = client.describe_target_groups()
        for tg in target_gs['TargetGroups']:
            if tg['TargetGroupName'] in targets:
                tg_in = {
                    "name": tg['TargetGroupName'],
                    "state": "present",
                    "protocol": tg['Protocol'],
                    "port": tg['Port'],
                    "vpcId": tg['VpcId'],
                    "modify_targets": True,
                    "health_check_protocol": tg['HealthCheckProtocol'],
                    "health_check_port": tg['HealthCheckPort'],
                    "health_check_path": tg['HealthCheckPath'],
                    "health_check_interval": tg['HealthCheckIntervalSeconds'],
                    "health_check_timeout": tg['HealthCheckTimeoutSeconds'],
                    "healthyThresholdCount": tg['HealthyThresholdCount'],
                    "healthy_threshold_count": tg['UnhealthyThresholdCount'],
                    "unhealthy_threshold_count": tg['UnhealthyThresholdCount'],
                    "target_type": tg['TargetType'],
                    # "protocolVersion": tg['ProtocolVersion'],
                    # "healthCheckEnabled": tg['HealthCheckEnabled'],
                    # "targets": tg['Targets'],
                    # "LoadBalancerArns": tg['LoadBalancerArns'],
                }
                target_groups.append(tg_in)
        # print("******ELB IN*******")
        for elb in elbs['LoadBalancers']:
            subnets = [ee['SubnetId'] for ee in elb['AvailabilityZones']]
            listeners = []
            dlistens = client.describe_listeners(LoadBalancerArn=elb['LoadBalancerArn'])
            for dl in dlistens['Listeners']:
                drules = client.describe_rules(ListenerArn=dl['ListenerArn'])['Rules']
                # drules = [dr['RuleArn'] for dr in drules
                dl['Rules'] = drules
                listeners.append(dl)
            if elb['LoadBalancerName'] in targets:
                eObj={
                    "name": elb['LoadBalancerName'],
                    "state": "present",
                    "security_groups": elb['SecurityGroups'],
                    "scheme": elb['Scheme'],
                    "type": elb['Type'],
                    "ipAddressType": elb['IpAddressType'],
                    "listeners": dlistens['Listeners']
                }
                if subnets:
                    eObj['subnets'] = subnets
                # elif 'customerOwnedIpv4Pool' in elb:
                #     eObj['customerOwnedIpv4Pool'] = elb['customerOwnedIpv4Pool']
                # if 'SubnetMappings' in elb:
                #     eObj['subnetMapping'] = elb['SubnetMappings']
                elbs_in.append(eObj)
        
        return elbs_in, target_groups


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
            tdef_arn, ecr_imgs, task_defs, svc_in, roles, elb_tmps = self.ecs_service_describe(client, target)
            # fam = self.ecs_taskfam_describe(client, target)
        
            ecr = aconnect.__get_client__('ecr')
            ecr_imgs = self.ecr_describe(ecr, ecr_imgs)
            
            # elb = aconnect.__get_client__('elb')
            elb = aconnect.__get_client__('elbv2')
            elbs, target_groups = self.elb_describe(elb, elb_tmps)
            elb_main={
                "elbs": elbs,
                "target_groups": target_groups
            }
            ## convert svc_in into a dictionary by name
            # svc_dict = {}
            # for svc in svc_in:
            #     svc_dict[svc['name']] = svc
            ecs_main={
                "task_list": tdef_arn,
                "task_definitions": task_defs,
                "services": svc_in,

            }
            return {
                    'name': target,
                    'target': target,
                    'roles': roles,
                    "state": "present", # "has_instances",
                    "delay": 10,
                    "repeat": 10
                    # 'roleArn': getCL['clusters'][0]['roleArn'],
                    # 'elb_apps': elbs,
                }, elb_main, ecs_main, ecr_imgs

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
            containerObj, elb_main, ecs_main, ecr_imgs = self.behavior_describe(target, aconnect)
        roles = []
        for rrls in containerObj['roles']:
            rle, resourceRole = describe_role(rrls, aconnect, self.origin['account'], False)
            roles= roles + rle


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
            {"import_tasks": "../aws/IAM.yml", "vars": {"project": '{{ project }}'}},
            # {"import_tasks": "../aws/cr_dynamodb.yml", # add ECR, EKS, ECS, ELB, Taskdef, TaskFam
            #     "vars": {"project": '{{ project }}'}}
        ]


        taskRaw = taskMain[0]
        taskMain = [taskRaw] + taskWithFiles


        taskMain.append({"import_tasks": "../aws/_elb.yml",
                         "vars": {"project": '{{ project }}'}})
        # taskMain.append({"import_tasks": "../aws/_ecr.yml",
        #                  "vars": {"project": '{{ project }}'}})
        # taskMain.append({"import_tasks": "../aws/_ecs.yml",
        #                  "vars": {"project": '{{ project }}'}})
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
                defaultVar[targetLabel].update({"elb_apps": elb_main})
                defaultVar[targetLabel].update({"ecs_clusters": ecs_main})
                defaultVar[targetLabel].update({"ecr_imgs": ecr_imgs})



            # add Policies
            role_list = []
            role_policies = []
            # print("---role in")
            for role in roles:
                # print("role: %s" % role['name'])
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
                    "aws_path": rData['Path'],
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
            option = "main_%s" % account['all']
            mainIn = "%s/%s/%s" % (rootFolder, 'defaults', option)
            writeYaml(defaultVar, mainIn)
            yaml_main = "%s.yaml" % mainIn
            account_replace(yaml_main, str(targetLabel), "<environment_placeholder>")
            account_replace(yaml_main, str(acctID), str(simple_id))
            account_replace(yaml_main, "<environment_placeholder>", str(targetLabel))
            ALL_MAPS = [DOMAIN_MAP, NETWORK_MAP]
            ########################################################
            ########################################################
            # STRING REPLACE ON ALL MAPS --BEGINS--- here #####
            file_replace_obj_found(yaml_main, akey, acctPlus, ALL_MAPS)
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
            rootYML = [{"name": "micro modler for Container-%s" % target,
                        "hosts": "dev",
                        "remote_user": "root",
                        "roles": targets}]
            # ansibleRoot
            print(ansibleRoot)
            print(target_file)
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
