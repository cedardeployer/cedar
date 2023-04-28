# This code is used to create Ansible files for deploying Lambda's
# all that is needed is a target Lambda, tests, and it will do the rest.
# finds associate roles and policies
# creates Ansible modules based on those policies and roles
# defines the Lambdas and creates them with tests
# finds api-gateways or other events
# if api found defines the security needed. creates modules for deployment with templates
import configparser
import re
from time import sleep
import os
import time
import random
import shutil
from datetime import datetime, date
import boto3
from botocore.exceptions import ClientError
import json
import sys
from shutil import copyfile
from shutil import copytree, copy2
import fileinput
import logging
import urllib
from pathlib import Path
import distutils
from distutils import dir_util

from tools.gentools import awsconnect

from tools.gentools.awsconnect import awsConnect

#from context import FormatContext
#import pyaml
# pip install pyyaml
import yaml
import decimal
# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
# dir_path = os.path.dirname(__file__)
dir_path = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)
user_home = str(Path.home())


class FormatSafeDumper(yaml.SafeDumper):
    def represent_decimal(self, data):
        return self.represent_scalar('tag:yaml.org,2002:str', str(data))

    def represent_set(self, data):
        return self.represent_sequence('tag:yaml.org,2002:seq', list(data))


FormatSafeDumper.add_representer(
    decimal.Decimal, FormatSafeDumper.represent_decimal)
FormatSafeDumper.add_representer(set, FormatSafeDumper.represent_set)
FormatSafeDumper.add_representer(tuple, FormatSafeDumper.represent_set)


class CommonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (tuple, set)):
            return list(o)
        if isinstance(o, Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)

        if isinstance(o, datetime):
            serial = o.isoformat()
            return serial
        return super(CommonEncoder, self).default(o)


def ansibleSetup(temp, target, isFullUpdate, skipFiles=False):
    ansible_folders = ["defaults", "files", "handlers", "tasks", "templates"]
    rootFolder = temp
    if not skipFiles:
        rootFolder = "%s/%s" % (temp, target)
        if os.path.exists(rootFolder) and isFullUpdate:
            oldDIR = "%s_old" % rootFolder
            if os.path.exists(oldDIR):
                shutil.rmtree(oldDIR)
                logger.info(f'{oldDIR}: DELETED')
            os.rename(rootFolder, oldDIR)
            logger.debug(f'ROOT-FOLDER: {rootFolder}')
        # folders needed

        if not os.path.exists(rootFolder):
            os.makedirs(rootFolder)
        for folder in ansible_folders:
            newFolder = "%s/%s" % (rootFolder, folder)
            if not os.path.exists(newFolder):
                os.makedirs(newFolder)

        # CREATE Template TASkS
    targetLabel = target.replace("-", "_")
    targetLabel = targetLabel.replace("*", "_")
    targetLabel = "A" + targetLabel
    taskMain = [{"name": "INITIAL PROJECT SETUP  project VAR", "set_fact": {"project": "{{ %s }}" % targetLabel}}
                ]
    if not skipFiles:
        taskWithFiles = [
            {"import_tasks": "../aws/sts.yml", "vars": {"project": '{{ project }}'}},
            {"import_tasks": "../aws/IAM.yml", "vars": {"project": '{{ project }}'}},
            {"import_tasks": "../aws/lambda.yml",
                "vars": {"project": '{{ project }}'}}
            # {"include": "dynamo_fixtures.yml project={{ project }}"},
        ]
        taskMain = taskMain + taskWithFiles

    return taskMain, rootFolder, targetLabel


def describe_regions(ec2_client=None):
    if ec2_client is None:
        ec2_client = boto3.client('ec2')
    response = ec2_client.describe_regions()['Regions']
    return [rg['RegionName'] for rg in response]


def describe_role(name, aconnect, acct, apiTRigger=False):
    client = aconnect.__get_client__('iam')
    #client = boto3.client('iam')
    if "/" in name:
        name = name.split("/")[-1]
    roleData = client.get_role(RoleName=name)['Role']
    del roleData['CreateDate']
    arn = roleData['Arn']
    roles = []
    aplcy = client.list_attached_role_policies(RoleName=name)
    policies = []
    givenPolicies = aplcy['AttachedPolicies']
    if apiTRigger:
        logger.info(f'Using API trigger policy: {name}')
        logger.debug(f'Policies...: {givenPolicies}')

        pname = name
        p_arn = "arn:aws:iam::%s:policy/%s" % (acct, pname)
        try:
            pDefinition = describe_policy(p_arn, pname, aconnect)
            policies.append(pDefinition)
        except ClientError as e:
            logger.info(f'[E] no policy named:{p_arn} found.. using only Policies...: {givenPolicies}')
    if len(givenPolicies) != 0:
        for plcy in givenPolicies:
            polName = plcy['PolicyName']
            polARN = plcy['PolicyArn']
            pDefinition = describe_policy(polARN, polName, aconnect)
            policies.append(pDefinition)
    roles.append({'name': name, 'data': roleData, 'policies': policies})
    return roles, arn


def describe_policy(arn, name, aconnect):
    client = aconnect.__get_client__('iam')
    #client = boto3.client('iam')
    polMeta = client.get_policy(PolicyArn=arn)['Policy']
    polDefined = client.get_policy_version(PolicyArn=arn, VersionId=polMeta['DefaultVersionId'])
    #polDefined = client.get_role_policy(RoleName=name,PolicyName=polName)

    logger.debug(polDefined)
    doc = polDefined['PolicyVersion']['Document']
    description = 'CR-Default no description found'
    if 'Description' in polMeta:
        description = polMeta['Description']
    path = polMeta['Path']
    print(f'    [ENSURE] policy exists: {name}')
    return {'PolicyName': name,
            'Path': path,
            'PolicyDocument': doc,
            'Description': description}


def s3_copy_key(fromBucket, toBucket, fromKey, toKey, resource=None):
    if resource is None:
        resource = boto3.resource('s3')
    if toKey[0] == "/":
        toKey = toKey[1:]
    copy_source = {
        'Bucket': fromBucket,
        'Key': fromKey
    }
    client = resource.meta.client
    extn = os.path.splitext(toKey)[1]
    extension = extn[1:]
    #extra_args={'ContentType': mime}
    # k = client.head_object(Bucket = fromBucket, Key = fromKey)
    # m = k["Metadata"]
    # m["new_metadata"] = "value"

    mimeType = getMimeType(extension)
    # client.copy_object(Bucket = toBucket, Key = toKey, CopySource = fromBucket + '/' + fromKey, Metadata = m, MetadataDirective='REPLACE')
    client.copy_object(Bucket=toBucket, Key=toKey, CopySource=fromBucket + '/' + fromKey, ContentType=mimeType, MetadataDirective='REPLACE')


def getMimeType(extension):
    if '.' in extension:
        extension = extension[1:]
    extn = '.%s' % (extension)
    if extn in images:
        meta = 'image'
    elif extn in texts:
        meta = 'text'
    elif extn in videos:
        meta = 'video'
    elif extn in audios:
        meta = 'audio'
    else:
        meta = 'application'
    # ### EXTENSIONS ####
    if 'xlsx' in extn:
        extension = 'vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif 'doc' in extn:
        extension = 'msword'
    elif 'docx' in extn:
        extension = 'vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif 'pptx' in extn:
        extension = 'vnd.openxmlformats-officedocument.presentationml.presentation'
    elif 'jpg' in extn:
        extension = 'jpeg'

    return '%s/%s' % (meta, extension)


def s3_put_stream(bucket, targetKey, some_binary_data, resource=None):
    if resource is None:
        resource = boto3.resource('s3')
    object = resource.Object(bucket, targetKey)
    object.put(Body=some_binary_data)


def s3_put(bucket, targetKey, localfile, resource=None):
    if resource is None:
        resource = boto3.resource('s3')
    print(" S3 --> @%s/%s" % (bucket, targetKey))
    if targetKey[0] == "/":
        targetKey = targetKey[1:]
    try:
        extn = os.path.splitext(localfile)[1]
        extension = extn[1:]
        mimeType = getMimeType(extension)
        resource.meta.client.upload_file(localfile, bucket, targetKey, ExtraArgs={'ContentType': mimeType})  # , 'ACL': "public-read"} )#, Metadata={'foo': 'bar'}
        return True
    except ClientError as ex:
        msg = "[E] during s3 push of report. file:%s target:%s/%s error:%s" % (localfile, bucket, targetKey, ex)
        #self.slackSend(self.channelName,msg,self.current.slack_name, ":bomb:")
        if ex.response['Error']['Code'] == "404":
            # sqs_logger.warning(" the file  %s does not exist." % localfile)
            print(" the file %s does not exist." % localfile)
        else:
            raise
    return False

def s3_get(bucket,targetKey, localfile, resource=None):
    if resource is None:
        resource = boto3.resource('s3')
    try:
        #s3_client.download_file(self.bucket, targetKey, localfile)
        print(" GET from bucket %s   file:%s  to:%s"%(bucket,targetKey, localfile))
        resource.Bucket(bucket).download_file(targetKey, localfile )
        return True
    except ClientError as ex:
        msg="[E] during s3 get. file:%s target:%s/%s error:%s"%(localfile, bucket, targetKey, ex)
        print(msg)
            #self.slackSend(self.channelName,msg,self.current.slack_name, ":bomb:")
        if ex.response['Error']['Code'] == "404":
            logger.warning("5 the file  %s does not exist."%localfile)
            print(" the file %s does not exist."%localfile)
        else:
            raise
    return False

def s3_get_stream(bucket, targetKey, encoding='utf-8', resource=None):
    if resource is None:
        resource = boto3.resource('s3')
    targetKey = targetKey[1:] if targetKey.startswith('/') else targetKey
    if targetKey == 'data/lambdas/XX-CEDAR/../RESTRICTED.yaml':
        targetKey = 'data/lambdas/RESTRICTED.yaml'
    obj = resource.Object(bucket, targetKey)
    if encoding is None:
        return obj.get()['Body'].read()
    else:
        return obj.get()['Body'].read().decode(encoding)

def copy_tree(src, dst, symlinks=False, ignore=None):
    # distutils.dir_util.copy_tree(src, dst, symlinks, ignore)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            # shutil.copytree(s, d, symlinks, ignore)
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)

def cleanAcct_num(acct_num):
    acct_num = acct_num.replace(' ', '')
    acct_num = acct_num.split('-')[0]
    acct_num = acct_num.split('_')[0]
    return str(acct_num)

def file_replace_obj_found(yaml_main, akey, acctPlus, ALL_MAPS , entire_file=False):
    if entire_file:
        account_replace(yaml_main, cleanAcct_num(acctPlus), cleanAcct_num(akey))
    for SVC_MAP in ALL_MAPS:
        typeObj = SVC_MAP[akey]
        for key, value in SVC_MAP[acctPlus].items():
            # if len(str(value)) < 5 or len(str(typeObj[key])) < 5:
            #     logger.warning(f'Dangerous replace found: {key} - skipping {value} for {typeObj[key]}')
            #     continue
            if len(str(value)) < 5 or len(str(typeObj[key])) < 5:
                logger.warning(f'Dangerous replace found: {key} - executing replace {value} for {typeObj[key]}')
            account_replace(yaml_main, str(value), str(typeObj[key]))


def writeYaml(data, filepath, option=''):
    dd = {"---": data}
    fullpath = '%s%s.%s' % (filepath, option, 'yaml')
    with open(fullpath, 'wb') as outfile:
        yaml.dump(dd, outfile, default_flow_style=False,
                  encoding='utf-8', allow_unicode=True, Dumper=FormatSafeDumper)
    for line in fileinput.input([fullpath], inplace=True):
        if line.strip().startswith("'---"):
            line = '---\n'
        sys.stdout.write(line)
    return fullpath.rsplit("/", 1)[1]


def writeJSON(data, filepath, option=''):
    fullpath = '%s%s.%s' % (filepath, option, 'js')
    with open(fullpath, 'w') as outfile:
        json.dump(data, outfile, cls=CommonEncoder, indent=4)
    return fullpath.rsplit("/", 1)[1]


def account_replace(filein, num2Search, newNumber, verify=False):
    # Read in the file
    if ".pdf" in filein:
        return
    with open(filein, 'r') as file:
        filedata = file.read()

    index = 0
    if verify:
        index = filedata.find(newNumber)
    if index <= 0:
        # Replace the target string
        filedata = filedata.replace(num2Search, newNumber)

    # Write the file out again
    with open(filein, 'w') as file:
        file.write(filedata)


def account_replace_inline(filein, match, target_value, new_value):
    # Read in the file
    filedata = ""
    with open(filein, 'r') as file:
        for line in file:
            filedata = filedata + replace_inline_matched(line, match, target_value, new_value)
    # Write the file out again
    with open(filein, 'w') as file:
        file.write(filedata)


def replace_inline_matched(line, match, target_value, new_value):
    if match in line:
        return line.replace(target_value, new_value)
    return line


def account_inject_between(filein, num2Search, numB4, newNumber, appendType='suffix', verify=False):
    # Read in the file
    with open(filein, 'r') as file:
        filedata = file.read()

    filedata = inject_recursive(filedata, num2Search, numB4, newNumber, appendType, verify)

    # Write the file out again
    with open(filein, 'w') as file:
        file.write(filedata)


def inject_recursive(str_base, strFrom, strTo, strNew, appendType='suffix', verify=False):
    index_from = str_base.find(strFrom)
    if index_from == -1:
        return str_base
    index_from = index_from + len(strFrom)
    index_to = str_base.find(strTo, index_from)
    last = str_base[index_from:index_to]
    print("*****[%s]** from:%s, to:%s, new:%s" % (str_base.find(strFrom), strFrom, strTo, strNew))
    print(" strL: %s from:%s to:%s  last:%s" % (len(strFrom), index_from, index_to, last))
    # raise
    slippage = len(strNew) + index_to
    if 'suffix' in appendType:
        formatString = "%s%s" % (last, strNew)
    elif 'prefix' in appendType:
        formatString = "%s%s" % (strNew, last)
    found = False
    if verify:
        if strNew in str_base[:index_to]:
            found = True
    logger.debug(f'verify: {verify}, look: {str_base[:index_to]}, found: {found}')
    if not found:
        aBlock = injector(str_base[:index_to], formatString, index_from, True)[:slippage]
    else:
        aBlock = str_base[:index_to]
    strBlock = str_base[index_to:]
    indexNew = strBlock.find(strFrom)
    if indexNew >= 0:
        strBlock = aBlock + inject_recursive(strBlock, strFrom, strTo, strNew, verify)
    else:
        strBlock = aBlock + strBlock
    return strBlock


def injector(s, newstring, index, nofail=False):
    if not nofail and index not in range(len(s)):
        raise ValueError("index outside given string")
    if index < 0:  # add it to the beginning
        return newstring + s
    if index > len(s):  # add it to the end
        return s + newstring
    return s[:index] + newstring + s[index:]


def roleCleaner(roleString):
    if "/" in roleString or "}" in roleString:
        roleString = "_".join(roleString.split("/"))
        if "_" in roleString[0]:
            roleString = roleString[1:]
        roleString = roleString.replace("}", "")
        roleString = roleString.replace("{", "")
    if "[" in roleString:
        method = re.search(r'\[(.*?)\]', roleString).group(1)
        roleString = roleString.split("[")[0]
        if method == '*':
            method = 'all'
        roleSting = "%s_%s" % (roleString, method)
    return roleString


def loadServicesMap(fullpath, domain='RDS', base_path=None):
    # Start internal config load
    # spliter = "/gentools"
    # print(" LOADING ServiceMap: %s" % fullpath)
    if not os.path.isfile(fullpath):
        # try a directory behind
        if not fullpath.startswith("/") or '/' not in fullpath:
            #print(" LOADING 2 ServiceMap: %s .. behind:%s" % (fullpath, dir_path))
            if not os.path.isfile(fullpath):
                basename = os.path.basename(fullpath)
                fullpath = "../%s" % (basename)
    if os.path.isfile(fullpath):
        logger.info(f'Loading {fullpath}')
        with open(fullpath, newline='') as stream:
            exp = yaml.load(stream, Loader=yaml.FullLoader)
        if domain:
            targets = exp['services'][domain]
        else:
            targets = exp['services']
        return targets

    # End internal config load

    if 'bucket' in os.environ:
        path = "%s/%s" % (base_path, fullpath)
        exp = loadYamlStream(os.environ['bucket'], path)
    else:
        exp = loadYaml(fullpath)
    if domain:
        targets = exp['services'][domain]
    else:
        targets = exp['services']
    return targets


def loadYamlStream(bucket, key, resource=None):
    stream = s3_get_stream(bucket, key, 'utf-8', resource)
    exp = yaml.load(stream, Loader=yaml.FullLoader)
    return exp


def loadYaml(fullpath):
    # Start internal config load
    # Look locally before loading from ~/.config/cedar
    finalpath = fullpath
    if not os.path.isfile(finalpath):
        basename = os.path.basename(fullpath)
        finalpath = os.path.join(finalpath.rsplit('/', 2)[0], basename)
    if not os.path.isfile(finalpath):
        basename = os.path.basename(fullpath)
        finalpath = os.path.join(finalpath.rsplit('/', 2)[0], basename)

    if os.path.isfile(finalpath):
        logger.info(f'Loading Yaml: {finalpath}')
        with open(finalpath, newline='') as stream:
            exp = yaml.load(stream, Loader=yaml.FullLoader)
        return exp

    # End internal config load

    config_parser = configparser.RawConfigParser()
    config_file_path = f'{user_home}/.config/cedar/config'
    config_parser.read(config_file_path)

    config_choice = 'default'

    try:
        restricted = config_parser.get(config_choice, 'restricted')
    except configparser.NoSectionError as e:
        logger.error(e.message)
        return None, None

    logger.info(f'Loading Yaml: {user_home}/.config/cedar/{restricted}.yaml')

    try:
        with open(f'{user_home}/.config/cedar/{restricted}.yaml', newline='') as stream:
            exp = yaml.load(stream, Loader=yaml.FullLoader)
    except FileNotFoundError as e:
        logger.error(e)
        return None, None, None
    return exp

def writeTXT(data,filepath, ext=''):
    fullpath="%s.%s"%(filepath,ext)
    f = open(fullpath,'w')
    f.write(data.strip())
    f.close()
    return fullpath


def loadConfig(fullpath, env):
    # Start internal config load
    finalpath = fullpath
    if not os.path.isfile(fullpath):
        basename = os.path.basename(fullpath)
        finalpath = os.path.join(finalpath.rsplit('/', 2)[0], basename)
    if not os.path.isfile(finalpath):
        basename = os.path.basename(fullpath)
        finalpath = os.path.join(finalpath.rsplit('/', 2)[0], basename)
    if os.path.isfile(finalpath):
        logger.info(f'Config loading from {finalpath}')

        # with open(finalpath, newline='') as stream:
        with open(finalpath, 'r') as stream:
            exp = yaml.load(stream, Loader=yaml.FullLoader)

        env = 'target2Define' + env.capitalize()
        target = exp[env]
        global_accts = exp['accounts']
        return target, global_accts

    # End internal config load

    config_parser = configparser.RawConfigParser()
    config_file_path = f'{user_home}/.config/cedar/config'
    config_parser.read(config_file_path)

    config_choice = 'default'
    try:
        envr = config_parser.get(config_choice, 'envr')
    except configparser.NoSectionError as e:
        logger.error(e.message)
        return None, None

    logger.info(f'Config loading from {user_home}/.config/cedar/{envr}.yaml')
    try:
        with open(f'{user_home}/.config/cedar/{envr}.yaml', 'r') as stream:
            exp = yaml.load(stream, Loader=yaml.FullLoader)
    except FileNotFoundError as e:
        logger.error(e)
        return None, None

    env = 'target2Define' + env.capitalize()
    target = exp[env]
    global_accts = exp['accounts']
    return target, global_accts


def config_updateRestricted(path, config, restrict_override=None):
    spliter = "/gentools"
    parts = [path]
    if spliter in path:
        parts = path.split(spliter)
        path = parts[0]

    if restrict_override:
        path = "%s/%s" % (parts[0], restrict_override)
    else:
        path = "%s/RESTRICTED.yaml" % (parts[0])
    logger.info(f'Looking for config...')
    if 'bucket' in os.environ:
        path = path[1:] if path.startswith('/') else path
        secrets = loadYamlStream(os.environ['bucket'], path)['services']['eID']
    else:
        secrets = loadYaml(path)['services']['eID']
    suffix = ""
    if 'sharedas' in config:
        suffix = config['sharedas']
    if 'account' in config:
        account = config['account'] + suffix
        config.update({'eID': secrets[account]['value']})
    else:
        for k, v in config.items():
            v.update({'eID': secrets[k]['value']})
    logger.debug(f'CONFIG: {config}')
    return config
