
import os
import time  # , random


import boto3
from botocore.exceptions import ClientError


import copy
import datetime

from tools.gentools.main_Deployer import TemporalDeployer
from tools.gentools.microUtils import roleCleaner, s3_put, writeYaml
##
##
# pip install ansible -t ansible_in

class Orchestrater():
    __dir = '/tmp'
    output = "data/ansible"
    bucket = None
    sendto = None

    def __init__(self, bucket):
        self.bucket = bucket
        self.sendto = "%s/ansible/roles" % (self.__dir)

    def define_and_deploy(self, event):
        tm = TemporalDeployer(self.__dir)
        self.define(event, tm)
        result = self.deploy(event, tm)
        return result

    def define(self, event, tm=None):
        output = None
        origin = event['origin']
        acctID = origin['account']
        role = svc_in = event['role']
        roleString = roleCleaner(role)
        roleString = "%s_%s" % (acctID, roleString)
        if not tm:
            tm = TemporalDeployer(self.__dir)
        if 'output' in event:
            output = event['output']
        if output:
            if not output.startswith('data/ansible'):
                print("[E] output [%s] did not start with 'data/ansible' prefix....using default" % (output))
                output = "data/ansible/%s" % (roleString)
        else:
            output = "data/ansible/%s" % (roleString)
        fullUpdate = event['fullUpdate']
        targetAPI = event['targetAPI']
        type_in = event['type_in']
        svc_in = event['svc_in']
        global_accts = event['global_accts']
        config = event['config']
        triggers = origin['triggers']
        if triggers is None:
            raise ValueError("[E] config file [ %s ] did not load correctly.. PLEASE check / fix and try again" % (fullpath))
        # targetAPI = "Secberus"
        # type_in = "-L"
        # svc_in = role = "SB-UserManage"
        # origin = {}
        # global_accts = []
        # config = {}
        # triggers = []
        # original account is base = origin['account']

        sendto = "%s/%s" % (self.sendto, roleString)
        acctID, target, acctTitle, ready = tm.Define(type_in, svc_in, origin, global_accts, sendto, config, triggers, targetAPI, fullUpdate)
        self.output_files(output)
        return acctID, target, acctTitle, ready

    def output_files(self, targetKey, roleString):
        s3_put(self.bucket, targetKey, localfile, resource=None)

    def deploy(self, event, tm=None):
        if not tm:
            tm = TemporalDeployer(self.__dir)
        role = event['role']
        origin = event['origin']
        acctID = origin['account']
        global_accts = event['global_accts']
        roleString = roleCleaner(role)
        roleString = "%s_%s" % (acctID, roleString)
        sendto = "%s/%s" % (self.sendto, roleString)
        if 'from_s3' in event:
            remoteDirectoryName = event['s3_defined']
            s3_resource = boto3.resource('s3')
            rbucket = s3_resource.Bucket(self.bucket)
            for object in bucket.objects.filter(Prefix=remoteDirectoryName):  # loop through directories and pull files locally
                dir_name = os.path.dirname(object.key).split("/")[-1]
                if roleString not in object.key:
                    print("[W] key doesn't not match:%s... found:%s" % (roleString, object.key))
                file_name = os.path.basename(object.key)
                tmp_path = f"{self.__dir}/ansible/roles/{roleString}/{dir_name}/{file_name}"
                if not os.path.exists(os.path.dirname(tmp_path)):
                    os.makedirs(os.path.dirname(tmp_path))
                rbucket.download_file(object.key, tmp_path)
            # self.base_playbook_file(role, roleString, sendto)
            
            # place files in /tmp/ansible/roles/<yourrole>/defaults
            # and in /tmp/ansible
        target_environments = event['target_environments']
        results = tm.deployStart(global_accts, target_environments, roleString)
        return results

    def base_playbook_file(self, role, roleString, sendto):
        ansibleRoot = sendto.split('roles/')[0]
        rootYML = [{"name": "CEDAR s3 DEFINER for ALL gateways resource -%s" % role,
                    "hosts": "dev",
                    "remote_user": "root",
                    "roles": [roleString]}]
        # ansibleRoot
        writeYaml(rootYML, ansibleRoot, roleString)


    def check_files():
        for root, dirs, files in os.walk('/tmp'):
            print("[__] %s" % (root))
            print("-----[%s]                       - - - - -[%s]" % (dirs, files[0]))


    def lambda_handler(event, context):
        action = event['action']
        print(event)

        bucket = os.environp['bucket']
        otr = Orchestrater(bucket)

        if 'define' in action and 'deploy' in action:
            response = otr.define_and_deploy(event)

        elif 'define' in action:
            response = otr.define(event)

        elif 'deploy' in action:
            response = otr.deploy(event)
        else:
            print("[E] action has yet to be defined")
        check_files()


        return response



#############
# Local run #
#############
if __name__ == '__main__':
    bucket = "sb-portal-dev"
    otr = Orchestrater(bucket)
