# This code is used to create Ansible files for deploying Lambda's
# all that is needed is a target Lambda, tests, and it will do the rest.
# finds associate roles and policies
# creates Ansible modules based on those policies and roles
# defines the Lambdas and creates them with tests
# finds api-gateways or other events
# if api found defines the security needed. creates modules for deployment with templates
import logging
import re
import os
# import ValueError
# import time
# import random
# from time import sleep
# from datetime import datetime, date
import json
# import shutil
# import boto3
import sys

from botocore.exceptions import ClientError
# import sys
from shutil import copyfile
# import fileinput
# import logging
# import urllib

import distutils
# from distutils import dir_util

# import awsconnect

# from awsconnect import awsConnect

from tools.gentools.microGatewayHttp import HttpGatewayMolder
from tools.gentools.microUtils import writeYaml, account_replace, loadServicesMap, ansibleSetup, loadConfig
from tools.gentools.microUtils import describe_role, roleCleaner, account_inject_between
from tools.gentools.microUtils import describe_regions, account_replace_inline, file_replace_obj_found

# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
# dir_path = os.path.dirname(__file__)
dir_path = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)

class ApiGatewayMolder():
    origin = None
    httpGateway = None
    temp = None

    def Cooker(self, target):
        lambda_describe(target)

        
    def __init__(self, directory, root=None):
        global dir_path
        self.directory = directory
        if root:
            temp = "%s/%s" % (root, directory)
        else:
            temp = "%s/%s" % (dir_path, directory)
        self.temp = temp
        if not os.path.exists(temp):
            os.makedirs(temp)
        else:
            logger.warning(f'{temp} already exists--remove or rename.')

    def api_http(self):
        if self.httpGateway:
            return self.httpGateway
        self.httpGateway = HttpGatewayMolder()
        return self.httpGateway

    #############################################
    # #####   [ USAGE PLAN KEYs ]#################
    #############################################
    #############################################
    def describe_apiKey(self, client, apiKey, position=None):
        rlist = []  # client.get_api_key(apiKey='9j5xhi7ene')
        if position is None:
            response = client.get_api_key(apiKey=apiKey, limit=500)
        else:
            response = client.get_api_key(
                apiKey=apiKey, position=position, limit=500)
        baseList = response['items']
        if "position" in response:
            rlist = self.describe_apiKey(client, apiKey, response['position'])
        keys = baseList + rlist
        return keys

    def keysMapAPI(self, client, baseList):
        pass
        # for base in baseList:

    def describe_planKey(self, client, usagePlanID, position=None):
        rlist = []
        if position is None:
            response = client.get_usage_plan_keys(
                usagePlanId=usagePlanID, limit=500)
        else:
            response = client.get_usage_plan_keys(
                usagePlanId=usagePlanID, position=position, limit=500)
        temp = response['items']
        baseList = self.keysMapAPI(client, temp)
        if "position" in response:
            rlist = self.describe_planKey(
                client, usagePlanID, response['position'])
        keys = baseList + rlist
        return keys

    def describe_apiUsage(self, client, restApiId, position=None):
        rlist = []
        if position is None:
            response = client.get_usage_plans(keyId=restApiId, limit=500)
        else:
            response = client.get_usage_plans(
                keyId=restApiId, position=position, limit=500)
        baseList = response['items']
        if "position" in response:
            rlist = self.describe_apiUsage(
                client, restApiId, response['position'])
        usagePlans = baseList + rlist
        return usagePlans

    def put_UsagePlan(self, client, usagePlans):
        for plans in usagePlans:
            # delete first if exists... or ignore....
            # response = client.delete_usage_plan(
            #                 usagePlanId='string'
            #             )
            client.create_usage_plan(name=plans['name'], description=plans['description'],
                                     apiStages=plans['apiStages'],
                                     throttle=plans['throttle'],
                                     quota=plans['quota']
                                     )

    def put_PlanKeys(self, client, keys, usagePlanId):
        for key in keys:
            # delete first if exists... or ignore....
            # response = client.delete_usage_plan(
            #                 usagePlanId='string'
            #             )
            response = client.create_usage_plan_key(usagePlanId=usagePlanId, keyId=key['id'],
                                                    keyType=key['type']
                                                    )

    def put_APIKeys(self, client, keys, usagePlanId):
        for key in keys:
            response = client.create_api_key(name=key['name'],
                                             description=key['description'],
                                             enabled=key['enabled'],
                                             generateDistinctId=key['generateDistinctId'],
                                             value=key['value'],
                                             # customerId=key['customerId']
                                             )

    #############################################
    ######   [ USAGE PLAN KEYs ]#################
    #############################################
    #############################################

    #############################################
    ######   [ API AUTHORIZERS ]#################
    #############################################
    #############################################
    def describe_authorizers(self, client, restApiId, name, auths):
        auth_list = self.describe_Allauths(client, restApiId)
        aList = []
        for auth in auth_list:
            auth.update({'state': 'present', 'apiName': name})
            auths.append(auth)

        # auths.update({apiStage:{'stage':stageLabel,'api':apiName, 'state':'present'}})
        return auths

    def describe_Allauths(self, client, restApiId, position=None):
        rlist = []
        if position is None:
            response = client.get_authorizers(restApiId=restApiId, limit=500)
        else:
            response = client.get_authorizers(
                restApiId=restApiId, position=position, limit=500)
        baseList = response['items']
        if "position" in response:
            rlist = self.describe_Allmodels(
                client, restApiId, response['position'])
        models = baseList + rlist
        return models

    #############################################
    #### E N D  [ API AUTHORIZERS ]##############
    #############################################
    #############################################

    #############################################
    ######   [ API MODELS ]#################
    #############################################
    #############################################
    def describe_Allmodels(self, client, restApiId, position=None):
        rlist = []
        if position is None:
            response = client.get_models(restApiId=restApiId, limit=500)
        else:
            response = client.get_models(
                restApiId=restApiId, position=position, limit=500)
        baseList = response['items']
        if "position" in response:
            rlist = self.describe_Allmodels(
                client, restApiId, response['position'])
        models = baseList + rlist
        return models

    def get_attrModel(self, client, target, restApiId, init=False):
        rawSchema = client.get_model(
            restApiId=restApiId, modelName=target, flatten=True)['schema']

        rr = json.loads(rawSchema)
        mType = rr['type']
        # print(" - - - - START attrModel - - - - -")
        # print(rr)
        if 'properties' in rr:
            response = rr['properties']
        else:
            response = rr['items']

        definitions = rr['definitions']
        oFinal = {}
        for k, v in response.items():
            value = v
            name = k
            print(" key: %s, value: %s" % (k, v))
            if "$ref" in k:
                vmodel = os.path.basename(v)
                oValue = {'items': None}
                value = self.get_attrModel(client, vmodel, restApiId)
                name = target
                oValue['items'] = value
                # print(" - - - - START attrModel - - - -%s -"%target)
                # print(response)
                # print(oValue)
                # raise
                if init:
                    return {'type': mType, 'items': value['items']}
            elif len(v) > 1 and type(v) is dict:
                # 'type': 'object', 'additionalProperties': {'$ref': '#/definitions/address'}}
                print(v)
                oType = v['type']
                # if 'items' in v:
                for oK, oV in v.items():
                    if 'type' in oK:
                        continue
                    # itemKey = oK
                    # oValue=v['items']
                    if "$ref" in oV:
                        vmodel = os.path.basename(oV['$ref'])
                        value = self.get_attrModel(client, vmodel, restApiId)
                        # oValue['items']=value
                    oFinal.update({name: {'type': oType, 'items': oV}})
            oFinal.update({name: value})
        return {'type': mType, 'items': oFinal}

    def describe_modelInTarget(self, client, apiName, target, svcType='dynamodb'):
        apis = self.getAll_rest_apis(client)
        restApiId = None
        for api in apis:
            name = api['name']
            if name in apiName:
                restApiId = api['id']
                break
        if restApiId is None:
            return None

        mapped = None
        if svcType in 'dynamodb':
            obj = {}
            begin = ""
            mapped = self.get_attrModel(client, target, restApiId, True)

        # print("--------COMPLETED----------")
        # print("   ----------------------")
        # print("      ----------------")
        # print(mapped)
        return mapped
    # def models_filter(self,models):

    #     return models
    def describe_models(self, client, restApiId, name, models):
        model_list = self.describe_Allmodels(client, restApiId)
        basic = []
        advanced = []
        advTemp = []

        models.update({'basic': basic, 'dependant': advanced})
        basicNames = []
        for model in model_list:
            rawSchema = model['schema'].replace(
                restApiId, "%s_id" % (name))  # gets converted in real time
            # model['schema']=model['schema'].replace("\n", "" ).replace( "\\", "" )
            # model['schema'] =model['schema'].replace('{', "{'$schema':'http://json-schema.org/draft-04/schema#', 'title': '%s' ,"%(model['name']), 1)

            model['schema'] = json.loads(rawSchema)

            model.update({'api': name, 'state': 'present'})
            apiModel = "%s_%s" % (name, model['name'])
            if '$ref' in rawSchema:
                advTemp.append(model)
            else:
                basic.append(model)
                basicNames.append(model['name'])
            # models.update({apiModel:model})

        # print(advTemp)
        # raise ValueError('A very specific bad thing happened.')

        # print("-------000-----~~~----~~~----~~~")
        # print(advTemp)
        # print("-------000b-----~~~----~~~----~~~")
        advTemp = self.relocRefsOnDependencies(advTemp, basicNames)
        advanced.extend(advTemp)
        # raise
        # advanced=advTemp
        logger.debug(f'Advanced: {advanced}')
        # print(models)
        # print("--------001----~~~----~~~----~~~")
        # raise ValueError('A very specific bad thing happened.')
        return models

    def checkstr_type(self, obj):
        return bool(obj) and all(isinstance(elem, str) for elem in obj)

    def describeRefs(self, key, value):
        refs = []
        if 'type' in key:
            return None
        if isinstance(value, (list, tuple, dict)):
            # print("%s:%s"%(key, value))
            if '$ref' in value:
                refs.append(value['$ref'])
            else:
                # print("*****")
                # print(value)
                if not self.checkstr_type(value):
                    for k, v in value.items():
                        dd = self.describeRefs(k, v)
                        if dd:
                            refs = refs + dd
        else:
            return None
        return refs

    ##################################################
    #######  BELOW REPOSITION ########################
    ######   BASED ON DEPENDENCIES  ##################
    ##################################################
    def modelRefs(self, schema):
        refs = []
        if 'properties' in schema:
            for k, v in schema['properties'].items():
                tempRefs = self.describeRefs(k, v)
                if tempRefs is None:
                    continue
                for ref in tempRefs:
                    refs.append(os.path.basename(ref))
        elif 'items' in schema:
            for k, v in schema['items'].items():
                if "$ref" in k:
                    refs.append(os.path.basename(v))
        if refs:
            refs = list(set(refs))
        return refs

    #
    def relocRefsOnDependencies(self, array, basicNames):
        additionali = 0
        for i, adv in enumerate(array):
            if additionali > 0:
                i = additionali + i
                if i >= len(array):
                    break
            # print("--=     %s"%( array[i] )   )
            sSchema = array[i]['schema']
            if 'properties' in sSchema or 'items' in sSchema:
                refsIn = []
                model = array[i]
                IName = model['name']
                if 'items' in sSchema:
                    refsIn.append(os.path.basename(sSchema['items']['$ref']))
                else:
                    props = sSchema['properties']
                    # print(props)
                    for k, v in props.items():
                        refs = self.describeRefs(k, v)
                        if refs is None:
                            continue
                        for ref in refs:
                            refM = os.path.basename(ref)
                            refsIn.append(refM)
                if refsIn:
                    for rName in refsIn:
                        if rName in basicNames:
                            #print(" --: continue %s" % (rName))
                            continue
                        else:
                            for num, atemp in enumerate(array):
                                # aprops = atemp['schema']#['properties']
                                mname = atemp['name']
                                # print(mname)

                                if mname == rName:  # found match for reference
                                    if num > i:  # reference is AFTER i and MUST be before
                                        additionali = additionali + 1
                                        del array[num]
                                        # Item now just before reference
                                        array.insert(i, atemp)
                                        if 'client' in mname and 'clients' in IName:
                                            print(i)
                                            print(num)
                                            print(model)
                                            print("### client &*&*&*&****&&&&&")
                                            # raise
        if additionali > 0:
            print("additional found ... rerun")
            self.relocRefsOnDependencies(array, basicNames)
        return array

    ##################################################
    #######  ABOVE REPOSITION ########################
    ######   BASED ON DEPENDENCIES  ##################
    ##################################################

    def put_models(self, client, models):
        modelsAdded = []
        for model in models:
            # current= client.get_model(restApiId=restApiId,modelName=modelName)
            # if model.name == current.modelName:
            # delete model first
            modelName = model.name
            try:
                response = client.delete_model(
                    restApiId=model.restApiId, modelName=modelName)
                print("[W] found MODEL %s and deleted..." % modelName)
            except ClientError as e:
                print(" -[W]- NOT found MODEL %s .." % modelName)
                print(e.response['Error']['Message'])
            try:
                response = client.create_model(restApiId=model.restApiId, name=modelName, description=model.description,
                                               schema=model.schema, contentType=model.contentType)
                modelsAdded.append()
            except ClientError as e:
                print(e.response['Error']['Message'])
        return modelsAdded

    #############################################
    #####   [ API MODELS ]####  ABOVE  ##########
    #############################################
    #############################################

    def put_resources(self, client, resources):
        modelsAdded = []
        for model in models:
            # current= client.get_model(restApiId=restApiId,modelName=modelName)
            # if model.name == current.modelName:
            # delete model first
            modelName = model.name
            try:
                response = client.delete_model(
                    restApiId=model.restApiId, modelName=modelName)
                print("[W] found MODEL %s and deleted..." % modelName)
            except ClientError as e:
                print(" -[W]- NOT found MODEL %s .." % modelName)
                print(e.response['Error']['Message'])
            try:
                response = client.create_model(restApiId=model.restApiId, name=modelName, description=model.description,
                                               schema=model.schema, contentType=model.contentType)
                modelsAdded.append()
            except ClientError as e:
                print(e.response['Error']['Message'])
        return modelsAdded

    def describe_stages(self, client, apiID, apiName, stages):
        # client = aconnect.__get_client__('apigateway')
        # client = boto3.client('apigateway')
        usage = client.get_usage_plans()['items']
        for use in usage:
            for stage in use['apiStages']:
                if apiID in stage['apiId']:
                    stageLabel = stage['stage']
                    apiStage = "%s_%s" % (apiName, stageLabel)
                    if apiStage in stages:
                        continue
                    stages.update(
                        {apiStage: {'stage': stageLabel, 'api': apiName, 'state': 'present'}})
        return stages

    def getAllResources(self, client, restApiId, position=None):
        rlist = []
        if position is None:
            response = client.get_resources(restApiId=restApiId, limit=500)
        else:
            response = client.get_resources(restApiId=restApiId, position=position, limit=500)
        baseList = response['items']
        if "position" in response:
            rlist = self.getAllResources(client, restApiId, response['position'])
        final = baseList + rlist
        return final

    def getAll_rest_apis(self, client, position=None):
        rlist = []
        if position is None:
            response = client.get_rest_apis(limit=500)
        else:
            response = client.get_rest_apis(position=position, limit=500)
        baseList = response['items']
        if "position" in response:
            rlist = self.getAll_rest_apis(client, response['position'])
        final = baseList + rlist
        return final

    def getALL_v2_apis(self, client, position=None):
        gw = self.api_http()
        return gw.getALL_http_apis(client)
        

        # get api, resource, method, integration and responses, models

    def describe_gateway(self, resourceNname, resourceType, aconnect, resourceRole=None, targetAPI=None):
        client = aconnect.__get_client__('apigateway')
        client2 = aconnect.__get_client__('apigatewayv2') 
        # client = boto3.client('apigateway')
        # apis=client.get_rest_apis()
        apis = self.getAll_rest_apis(client)
        apis = apis + self.getALL_v2_apis(client2)
        integratedAPIs = []
        stages = {}
        models = {}
        auths = []
        addedResource = {}
        possibleOptions = {}

        print(f"    [DEFINE] API GATEWAY - {targetAPI}")
        logger.debug(f'APIs: {apis}')
        # print(targetAPI)

        GREEDY = False
        if '*' == resourceNname:
            GREEDY = True
        # for api in apis['items']:
        for api in apis:
            if 'id' in api:
                id = api['id']
            elif 'ApiId' in api:
                id = api['ApiId']
            if 'name' in api:
                name = api['name']
            elif 'Name' in api:
                name = api['Name']
            if targetAPI is not None:
                if name.lower() != targetAPI.lower():
                    continue
            protocol = "REST"
            if 'ProtocolType' in api:
                protocol = api['ProtocolType']
            #print(protocol)
            if protocol == "HTTP" or protocol == "WEBSOCKET":  # 'ProtocolType': 'WEBSOCKET'|'HTTP',
                print("********* WARNING  !!!!!!!")
                print("[W] HTTP/WSocket testing needed... continue")
                continue
            # resources = client.get_resources( restApiId=id,limit=500)
            resources = self.getAllResources(client, id)

            final_MODELS = {'basic': [], 'dependant': []}
            final_AUTHS = []
            # api id, stage id, model id
            stages = self.describe_stages(client, id, name, stages)
            models = self.describe_models(client, id, name, models)
            auths = self.describe_authorizers(client, id, name, auths)
            if GREEDY:
                final_MODELS = models
                final_AUTHS = auths

            logger.debug("                            API GATEWAY       resources")
            logger.debug(f'Resources: {resources}')

            # for rest in resources['items']:
            for rest in resources:
                path = rest['path']
                mId = rest['id']
                parentId = None
                if 'parentId' in rest:
                    parentId = rest['parentId']
                if 'resourceMethods' not in rest:
                    parent = rest
                    continue

                pathString = path
                resourceString = resourceNname
                pathString = roleCleaner(pathString)
                if '_*' not in resourceNname:
                    resourceString = roleCleaner(resourceString)
                    if (resourceString != pathString and resourceType != 'lambda' and not GREEDY):
                        continue
                else:
                    tempString = resourceString[:-2]
                    resourceString = roleCleaner(tempString)
                    if (resourceString not in pathString) and resourceType != 'lambda' and not GREEDY:
                        continue

                logger.debug('METHODS: ', rest['resourceMethods'])
                for key, value in rest['resourceMethods'].items():
                    tempResourceRole = resourceRole
                    # ONLY FOR TESTINNG
                    # if not 'GET' in key:
                    #     continue
                    # DELETE ABOVE !!!!!!!!!

                    logger.debug(f'{name}, {path}  client.get_method(restApiId={id},resourceId={mId},httpMethod={key})')
                    # integrated = None
                    # mInfo = value
                    # logger.info(value)

                    # if (resourceString != pathString and resourceType != 'lambda' and not GREEDY):

                    logger.debug(f'   *API*     [{resourceNname}][{pathString}]')

                    # try:
                    #     integrated = client.get_integration(restApiId=id, resourceId=mId, httpMethod=key)
                    #     del integrated['ResponseMetadata']
                    # except ClientError as e:
                    #     print(e.response['Error']['Message'])

                    # print integrated
                    method = client.get_method(
                        restApiId=id, resourceId=mId, httpMethod=key)
                    del method['ResponseMetadata']
                    authType = method['authorizationType']
                    keyRequired = method['apiKeyRequired']
                    function = method['httpMethod']
                    logger.debug(f'Function: {function}; Resource Type: {resourceType}')
                    if function.lower() not in resourceType.lower() and resourceType != 'lambda' and resourceType != '*':
                        if 'options' not in function.lower():
                            continue
                    integratedType = None
                    if 'methodIntegration' not in method:
                        continue
                    methodIntegration = method['methodIntegration']
                    logger.debug(f'Method: {method}')

                    operationName = rModels = sModels = authName = requestParameters = requestValidator = authScope = None
                    methodResponse = None
                    if 'methodResponses' in method:
                        methodResponse = method['methodResponses']

                        if '200' in methodResponse:
                            if 'responseModels' in methodResponse['200']:
                                mm = methodResponse['200']['responseModels']
                                sModels = {}
                                for mkey, mvalue in mm.items():
                                    sModels.update({mkey: mvalue})

                    # if 'GET' in key:
                    #     raise
                    if 'requestModels' in method:
                        sm = method['requestModels']
                        rModels = {}

                        # FIND MODELS AND ADD ONLY WHATS NEEDED IF NOT GREEDY
                        for rkey, rvalue in sm.items():
                            if 'empty' in rvalue.lower():
                                continue
                            rModels.update({rkey: rvalue})
                            if not GREEDY:  # ONLY ADD MODELS NEEDED FOR API
                                found = False
                                heritage = []
                                for md in models['dependant']:
                                    if md['name'] == rvalue:
                                        if md not in final_MODELS['dependant']:
                                            final_MODELS['dependant'].append(
                                                md)
                                            heritage = self.modelRefs(
                                                md['schema'])
                                        found = True
                                        break
                                if not found or heritage:
                                    for md in models['basic']:
                                        if md['name'] == rvalue:
                                            if md not in final_MODELS['basic']:
                                                final_MODELS['basic'].append(
                                                    md)
                                            break
                                    if heritage:   # IF MODEL HAS REFS GRAB THEM HERE
                                        for md in models['basic']:
                                            if md['name'] in heritage:
                                                if md not in final_MODELS['basic']:
                                                    final_MODELS['basic'].append(
                                                        md)
                                logger.debug(f'Final models: {final_MODELS}')
                        # raise
                    integration = None
                    if 'uri' in methodIntegration:
                        integration = methodIntegration['uri']
                    if 'credentials' in methodIntegration:
                        tempResourceRole = methodIntegration['credentials']
                    if rModels is None:
                        rModels = {}
                    if sModels is None:
                        sModels = {}
                    if requestParameters is None:
                        requestParameters = {}
                    if requestValidator is None:
                        requestValidator = {}
                    if methodResponse is None:
                        methodResponse = {}
                    if integration is None:
                        integration = {}

                    if 'requestValidatorId' in method:
                        requestValidator = client.get_request_validator(restApiId=id,
                                                                        requestValidatorId=method['requestValidatorId'])
                        del requestValidator['ResponseMetadata']
                    if 'requestParameters' in method:
                        requestParameters = method['requestParameters']
                    if 'authorizerId' in method:
                        auth = client.get_authorizer(
                            restApiId=id, authorizerId=method['authorizerId'])
                        authName = auth['name']
                    if 'authorizationScopes' in method:
                        authScope = method['authorizationScopes']
                    add = False
                    logger.debug(f'{integration}[{function}], type: {resourceType}, name: {resourceNname}')

                    logger.debug(f'if ({resourceType} in {integration} and {resourceNname} in {integration}) or {resourceNname} == "*"')
                    logger.debug(f'{resourceString} == {pathString}')

                        # raise
                    if (resourceType in integration and resourceNname in integration) or resourceNname == "*":
                        add = True
                    elif '_*' in resourceNname and resourceType == '*' and pathString.startswith(resourceString):
                        # print('if (%s in %s and %s in %s) or %s == "*"' % (resourceType, integration, resourceNname, integration, resourceNname))
                        # print("-------------------")
                        # print(". %s == %s" % (resourceString , pathString))
                        # raise
                        add = True
                    elif '_*' in resourceNname and resourceType.lower() == function.lower() and pathString.startswith(resourceString):
                        # print('if (%s in %s and %s in %s) or %s == "*"' % (resourceType, integration, resourceNname, integration, resourceNname))
                        # print("-------------------")
                        # print(". %s == %s" % (resourceString , pathString))
                        raise
                        add = True
                    elif resourceType == '*' and resourceString == pathString:
                        add = True
                    elif resourceType.lower() == function.lower() and resourceString == pathString:
                        add = True
                    elif key == "OPTIONS":
                        possibleOptions.update({path: {'name': name,
                                                       'parentid': parentId,
                                                       'credentials': None,
                                                       'state': 'present',
                                                       'id': mId,
                                                       'operationlabel': operationName,
                                                       'requestparameters': requestParameters,
                                                       'requestvalidator': requestValidator,
                                                       'authscope': authScope,
                                                       'requestmodels': rModels,
                                                       'responsemodels': sModels,
                                                       'authorizationType': authType,
                                                       'authName': authName,
                                                       'apiKeyRequired': keyRequired,
                                                       'type': integratedType,
                                                       'path': path,
                                                       'httpMethod': function,
                                                       'methodIn': methodIntegration,
                                                       'methodResponse': methodResponse}})

                    if add:
                        addedResource.update({path: mId})
                        if not 'credentials' in methodIntegration:
                            methodIntegration.update(
                                {'credentials': tempResourceRole})
                        integratedAPIs.append(
                            {'name': name,
                             'parentid': parentId,
                             'credentials': tempResourceRole,
                             'state': 'present',
                             'id': mId,
                             'operationlabel': operationName,
                             'requestparameters': requestParameters,
                             'requestvalidator': requestValidator,
                             'authscope': authScope,
                             'requestmodels': rModels,
                             'responsemodels': sModels,
                             'authorizationType': authType,
                             'authName': authName,
                             'apiKeyRequired': keyRequired,
                             'type': integratedType,
                             'path': path,
                             'httpMethod': function,
                             'methodIn': methodIntegration,
                             'methodResponse': methodResponse})

        for rK, rV in addedResource.items():  # Ensure OPTIONS picked up for Methods gathered
            if rK in possibleOptions:
                integratedAPIs.append(possibleOptions[rK])
        logger.info("Read completed")
        logger.debug('Integrated APIs: ', integratedAPIs)

        if len(integratedAPIs) == 0:
            return None, None, None, None
        return integratedAPIs, stages, final_MODELS, final_AUTHS

    def summary_gateway(self, client, targetAPI):
        apis = self.getAll_rest_apis(client)
        id = None
        for api in apis:
            if targetAPI in api['name']:
                id = api['id']
                break
        if id is None:
            logger.error(f'[E] API tree {targetAPI} not found')
            raise
        resources = self.getAllResources(client, id)
        integratedAPIs = {}

        logger.debug("                            API GATEWAY       resources")
        logger.debug(f'Resources: {resources}')
        # for rest in resources['items']:
        for rest in resources:
            path = rest['path']
            mId = rest['id']
            if not 'resourceMethods' in rest:
                parent = rest
                continue
            for key, value in rest['resourceMethods'].items():

                method = client.get_method(
                    restApiId=id, resourceId=mId, httpMethod=key)
                del method['ResponseMetadata']
                authType = method['authorizationType']
                keyRequired = method['apiKeyRequired']
                integratedType = None
                if not 'methodIntegration' in method:
                    continue

                if 'requestParameters' in method:
                    requestParameters = method['requestParameters']
                if 'authorizationScopes' in method:
                    authScope = method['authorizationScopes']
                add = False
                if (resourceType in integration and resourceNname in integration) or resourceNname == "*":
                    add = True
                # elif key == "OPTIONS":
                #     continue
                if add:
                    integratedAPIs.update({path:
                                           {
                                               'id': mId,
                                               'requestparameters': requestParameters,
                                               'authscope': authScope,
                                               'authorizationType': authType,
                                               'apiKeyRequired': keyRequired,
                                               'path': path,
                                               'httpMethod': method['httpMethod']}})
        return integratedAPIs

    def describe_GatewayALL(self, target, aconnect, accountOrigin, accounts=[], types=[], sendto=None, targetAPI=None, isFullUpdate=False, needDirs=False):
        # describe_gateway(self, resourceNname, resourceType, aconnect , resourceRole=None,targetAPI=None):
        allAccounts = True
        directorysNeeded = needDirs
        skipFiles = True
        acctTitle = None
        if directorysNeeded:
            skipFiles = False
        # tmp="/tmp"
        #

        self.origin = accountOrigin
        acctID = acctPlus = accountOrigin['account']
        if 'sharedas' in accountOrigin:
            acctPlus = acctID + accountOrigin['sharedas']
        assumeRole = accountOrigin['assume_role']

        NETWORK_MAP = loadServicesMap(accountOrigin['services_map'], 'RDS')
        COGNITO_MAP = loadServicesMap(accountOrigin['services_map'], 'cognito')
        BUCKET_MAP = loadServicesMap(accountOrigin['services_map'], 'S3')
        REGIONS = describe_regions()

        iamRole = accountOrigin['triggeredRole']
        logger.info(f'API-lambda trigger role: {iamRole}')

        targetString = roleCleaner(target)
        roles, resourceRole = describe_role(iamRole, aconnect, acctID, True if 'api' in types else False)
        # (target,'lambda', aconnect, resourceRole, targetAPI)
        apis, stages, models, auths = self.describe_gateway('*', '*', aconnect, resourceRole, targetAPI)

        taskMain, rootFolder, targetLabel = ansibleSetup(self.temp, target, isFullUpdate, skipFiles)
        taskMain = taskMain[0:2]
        taskMain.append({"import_tasks": "../aws/agw_authorizer.yml",
                         "vars": {"project": '{{ project }}'}})
        taskMain.append({"import_tasks": "../aws/agw_model.yml",
                         "vars": {"project": '{{ project }}'}})
        taskMain.append({"import_tasks": "../aws/_agw.yml",
                         "vars": {"project": '{{ project }}'}})

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
        # ONLY needs two files default definition and tasks
        #############################################
        #############################################
        ######## write YAML to file in tasks  #######
        #############################################
        #############################################
        # rootFolder=tmp
        option = "main"
        if directorysNeeded:
            mainIn = "%s/%s/%s" % (rootFolder, 'tasks', option)
        else:
            option = "tasks_main"
            mainIn = "%s/%s" % (rootFolder, option)
        # mainIn = "%s/%s" % (rootFolder, option)
        writeYaml(taskMain, mainIn)
        file_tasks = "%s.yaml" % mainIn
        file_defaults = None
        # if 'services_map' in accountOrigin:
        #     mapfile = accountOrigin['services_map']
        #     serviceMap = loadServicesMap(mapfile, None)
        for akey, account in accounts.items():
            default_region = "us-east-1"
            # if not account in acctID:
            if acctID == akey:
                acctTitle = account['title']
            if not allAccounts:
                if acctID not in akey:
                    continue
            prefix = suffix = ''
            if 'suffix' in account or 'prefix' in account or 'contains' in account:
                if 'suffix' in account:
                    suffix = account['suffix']
            if 'region_deploy' in account:
                default_region = account['region_deploy']
            simple_id = akey
            if "_" in simple_id:
                simple_id = simple_id.split("_")[0]
            eID = account['eID']
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

            ########################################################
            #############  API GATEWAY METHODS   ###################
            ########################################################
            api_list = []
            stage_list = []  #
            model_list = models  # []  #
            # stages.update({apiStage:{'stage':stageLabel,'api':apiName}})
            if apis:
                # for mk,mv in models.items():
                #    model_list.append(mv)
                for sk, sv in stages.items():
                    api_name = sv['api']
                    if suffix not in api_name and suffix:
                        api_name = "%s%s" % (api_name, suffix)
                        sv.update({'api': api_name})
                    stage_list.append(sv)
                for api in apis:
                    api_name = api['name']
                    if suffix not in api_name and suffix:
                        api_name = "%s%s" % (api_name, suffix)
                    oApi = {
                        'name': api_name,
                        'id': api['id'],
                        'credentials': "%s" % api['credentials'],
                        'authorizationType': api['authorizationType'],
                        'apiKeyRequired': api['apiKeyRequired'],
                        'type': api['type'],
                        'path': api['path'],
                        'operational_name': api['operationlabel'],
                        'request_valid': api['requestvalidator'],
                        'request_params': api['requestparameters'],
                        'auth_scope': api['authscope'],
                        'authName': api['authName'],
                        'request_models': api['requestmodels'],
                        'response_models': api['responsemodels'],
                        'httpMethod': api['httpMethod'],
                        'parentid': api['parentid'],
                        'method_response': api['methodResponse'],
                        'method_integration': api['methodIn'],
                        'state': api['state']
                    }

                    api_list.append(oApi)
                defaultVar[targetLabel].update({"api_gw": api_list})
                defaultVar[targetLabel].update({"api_stages": stage_list})
                defaultVar[targetLabel].update({"api_models": model_list})
                defaultVar[targetLabel].update({"api_authorizers": auths})
                # defaultVar[targetLabel].update({ "api_domains": stage_list })
                # defaultVar[targetLabel].update({ "api_usage": stage_list })

            # option = "defaults_main%s"%account['all']
            # option = "defaults_main"
            # mainIn = "%s/%s" % (rootFolder, option)
            # mainIn = "%s/%s/%s"%(rootFolder,'defaults',option)
            # # mainIn = "%s/%s/%s"%(rootFolder,'defaults',option)
            # file_defaults = "%s.yaml" % mainIn
            # # CREATE default with all vars
            # writeYaml(defaultVar, mainIn)
            # account_replace(file_defaults, str(acctID), str(akey))
                #
            if directorysNeeded:
                option = "main_%s" % account['all']
                mainIn = "%s/%s/%s" % (rootFolder, 'defaults', option)
                writeYaml(defaultVar, mainIn)
                #print("----> file: %s" % (mainIn))
                yaml_main = "%s.yaml" % mainIn
                account_replace(yaml_main, str(targetLabel), "<environment_placeholder>")
                account_replace(yaml_main, str(acctID), str(simple_id))
                account_replace(yaml_main, "<environment_placeholder>", str(targetLabel))

                ALL_MAPS = [BUCKET_MAP, NETWORK_MAP, COGNITO_MAP]
                ########################################################
                ########################################################
                # STRING REPLACE ON ALL MAPS --BEGINS--- here #####
                file_replace_obj_found(yaml_main, akey, acctPlus, ALL_MAPS)
                # STRING REPLACE ON ALL MAPS ---ENDS-- here #####
                ########################################################
                ########################################################
                if "_" in akey:  # KEY found _ account with many ENVs in single account
                    for m_region in REGIONS:  # default_region
                        match = "arn:aws:apigateway:%s" % (m_region)
                        account_replace_inline(yaml_main, match, m_region, default_region)

                verify = True
                if suffix not in target and suffix:
                    pass
                    # account_inject_between("%s.yaml" % mainIn, ":function:", "/invocations", suffix, 'suffix', verify)
                    # account_inject_between("%s.yaml" % mainIn, 'TableName\\": \\"', '\\"\\', suffix, 'suffix', verify)
                    #inject_recursive(dd,'TableName\\": \\"', '\\"\\', "-doodo-")
                if prefix not in target and prefix:
                    account_inject_between("%s.yaml" % mainIn, ":function:", "/invocations", prefix, 'prefix', verify)
                    account_inject_between("%s.yaml" % mainIn, 'TableName\\": \\"', '\\"\\', prefix, 'prefix', verify)

        if directorysNeeded:
            if sendto:
                logger.info('Creating a main.yaml for ansible using dev')
                opt = "main_%s.yaml" % accountOrigin['all']
                src = "%s/%s/%s" % (rootFolder, 'defaults', opt)
                opt2 = "main.yaml"
                dst = "%s/%s/%s" % (rootFolder, 'defaults', opt2)
                logger.info("src: %s" % (src))
                logger.info("dst: %s" % (dst))
                copyfile(src, dst)

                logger.info(f'{rootFolder} --> {sendto}')
                distutils.dir_util.copy_tree(rootFolder, sendto)
                ansibleRoot = sendto.split('roles/')[0]
                # targets = ['%s' % targetString]

                target_file = '%s_%s' % (acctID, targetString)
                targets = [target_file]
                rootYML = [{"name": "micro modler for ALL gateways resource -%s" % target,
                            "hosts": "dev",
                            "remote_user": "root",
                            "roles": targets}]
                # ansibleRoot
                writeYaml(rootYML, ansibleRoot, target_file)
        else:
            option = "defaults_main"
            mainIn = "%s/%s" % (rootFolder, option)
            # mainIn = "%s/%s/%s"%(rootFolder,'defaults',option)
            file_defaults = "%s.yaml" % mainIn
            # CREATE default with all vars
            writeYaml(defaultVar, mainIn)
            account_replace(file_defaults, str(acctID), str(akey))

        logger.info('Final YAML: {file_tasks}')
        # return file_tasks, file_defaults
        return acctID, target, acctTitle, True

    def describe_GwResource(self, target, aconnect, accountOrigin, accounts=[], types=[], sendto=None, targetAPI=None, isFullUpdate=False, needDirs=False):
        logger.info('Start description for target deployments...')
        # describe_gateway(self, resourceNname, resourceType, aconnect , resourceRole=None,targetAPI=None):
        # isFullUpdate = False
        directorysNeeded = needDirs
        skipFiles = True
        if directorysNeeded:
            skipFiles = False
        acctTitle = None
        # tmp="/tmp"

        self.origin = accountOrigin
        acctID = acctPlus = accountOrigin['account']
        if 'sharedas' in accountOrigin:
            acctPlus = acctID + accountOrigin['sharedas']
        assumeRole = accountOrigin['assume_role']

        NETWORK_MAP = loadServicesMap(accountOrigin['services_map'], 'RDS')
        COGNITO_MAP = loadServicesMap(accountOrigin['services_map'], 'cognito')
        BUCKET_MAP = loadServicesMap(accountOrigin['services_map'], 'S3')
        REGIONS = describe_regions()
        # self.origin['account']

        iamRole = accountOrigin['triggeredRole']
        logger.info(f'API-lambda trigger role: {iamRole}')

        roles, resourceRole = describe_role(iamRole, aconnect, acctID, True if 'api' in types else False)
        targetString = roleCleaner(target)
        if "[" not in target:
            logger.error(f'[E] arguments given do not contain methods for resource: {target}')
            raise Exception(f'[E] arguments given do not contain methods for resource: {target}')
        method = re.search(r'\[(.*?)\]', target).group(1)

        # (target,'lambda', aconnect, resourceRole, targetAPI)
        if '/*[' in target:  # this means we must recursively find all lower paths
            apis, stages, models, auths = self.describe_gateway(
                targetString, method, aconnect, resourceRole, targetAPI)
        else:
            apis, stages, models, auths = self.describe_gateway(
                targetString, method, aconnect, resourceRole, targetAPI)
        if apis is None:
            logger.error(f'No matching apis found! {target} in {targetAPI}')
            sys.exit('[E] Stopped')

        print(f'    Total API endpoints: {len(apis)}')

        target_file = '%s_%s' % (acctID, targetString)
        # taskMain, rootFolder, targetLabel = ansibleSetup(self.temp, targetString, isFullUpdate, skipFiles)
        taskMain, rootFolder, targetLabel = ansibleSetup(self.temp, target_file, isFullUpdate, skipFiles)
        taskMain = taskMain[0:2]
        taskMain.append({"import_tasks": "../aws/agw_model.yml",
                         "vars": {"project": '{{ project }}'}})
        taskMain.append({"import_tasks": "../aws/_agw.yml",
                         "vars": {"project": '{{ project }}'}})
        skipping = error_path = None
        if 'error_path' in accountOrigin:
            error_path = accountOrigin['error_path']
        if 'skipping' in accountOrigin:
            skipping = accountOrigin['skipping']
        # error_path: /Users/astro_sk/Documents/TFS/Ansible_Deployer
        if skipping:
            skipping = {
                "methods": False,
                "options": False,
                "models": False,
                "stage": False,
                "resources": False
            }
        if not apis:
            msg = "[E] missing apis please fix "
            print(msg)
            raise
        # ONLY needs two files default definition and tasks
        #############################################
        #############################################
        ######## write YAML to file in tasks  #######
        #############################################
        #############################################
        # rootFolder=tmp
        option = "main"
        # mainIn = "%s/%s/%s"%(rootFolder,'tasks',option)
        if directorysNeeded:
            mainIn = "%s/%s/%s" % (rootFolder, 'tasks', option)
        else:
            option = "tasks_main"
            mainIn = "%s/%s" % (rootFolder, option)
        writeYaml(taskMain, mainIn)
        file_tasks = "%s.yaml" % mainIn
        file_defaults = None

        for akey, account in accounts.items():
            default_region = 'us-east-1'
            # if not account in acctID:
            if acctID == akey:
                acctTitle = account['title']
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
                "eid": account['eID'],
                "roles": [],
                "policies": []
            }

            if assumeRole:
                accDetail.update({"cross_acct_role": account['role']})
            defaultVar = {targetLabel: accDetail}

            ########################################################
            #############  API GATEWAY METHODS   ###################
            ########################################################
            # print (" A P I. see below. ......===---->>>")
            api_list = []
            stage_list = []  #
            model_list = models  # []  #
            # stages.update({apiStage:{'stage':stageLabel,'api':apiName}})
            if not apis is None:
                # for mk,mv in models.items():
                #    model_list.append(mv)
                for sk, sv in stages.items():
                    stage_list.append(sv)
                for api in apis:
                    oApi = {
                        'name': api['name'],
                        'id': api['id'],
                        'credentials': "%s" % api['credentials'],
                        'authorizationType': api['authorizationType'],
                        'apiKeyRequired': api['apiKeyRequired'],
                        'type': api['type'],
                        'path': api['path'],
                        'operational_name': api['operationlabel'],
                        'request_valid': api['requestvalidator'],
                        'request_params': api['requestparameters'],
                        'auth_scope': api['authscope'],
                        'authName': api['authName'],
                        'request_models': api['requestmodels'],
                        'response_models': api['responsemodels'],
                        'httpMethod': api['httpMethod'],
                        'parentid': api['parentid'],
                        'method_response': api['methodResponse'],
                        'method_integration': api['methodIn'],
                        'state': api['state']
                    }

                    api_list.append(oApi)
                defaultVar[targetLabel].update({"api_gw": api_list})
                defaultVar[targetLabel].update({"api_stages": stage_list})
                defaultVar[targetLabel].update({"api_models": model_list})
                defaultVar[targetLabel].update({"api_authorizers": auths})
                # defaultVar[targetLabel].update({ "api_domains": stage_list })
                # defaultVar[targetLabel].update({ "api_usage": stage_list })
                #
            if directorysNeeded:
                option = "main_%s" % account['all']
                mainIn = "%s/%s/%s" % (rootFolder, 'defaults', option)
                writeYaml(defaultVar, mainIn)
                yaml_main = "%s.yaml" % mainIn
                account_replace(yaml_main, str(targetLabel), "<environment_placeholder>")
                account_replace(yaml_main, str(acctID), str(simple_id))
                account_replace(yaml_main, "<environment_placeholder>", str(targetLabel))
                ALL_MAPS = [BUCKET_MAP, NETWORK_MAP, COGNITO_MAP]
                ########################################################
                ########################################################
                # STRING REPLACE ON ALL MAPS --BEGINS--- here #####
                file_replace_obj_found(yaml_main, akey, acctPlus, ALL_MAPS)
                # STRING REPLACE ON ALL MAPS ---ENDS-- here #####
                ########################################################
                ########################################################

                if "_" in akey:  # KEY found _ account with many ENVs in single account
                    for m_region in REGIONS:  # default_region
                        match = "arn:aws:apigateway:%s" % (m_region)
                        account_replace_inline(yaml_main, match, m_region, default_region)


            # option = "defaults_main%s"%account['all']

        if directorysNeeded:
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
                logger.info(f"Writing final YAML: {file_tasks}")
                ansibleRoot = sendto.split('roles/')[0]
                # targets = ['%s' % targetString]
                targets = [target_file]
                rootYML = [{"name": "micro modler for gateways resource -%s" % target,
                            "hosts": "dev",
                            "remote_user": "root",
                            "roles": targets}]
                # ansibleRoot
                writeYaml(rootYML, ansibleRoot, target_file)
        else:
            option = "defaults_main"
            mainIn = "%s/%s" % (rootFolder, option)
            # mainIn = "%s/%s/%s"%(rootFolder,'defaults',option)
            file_defaults = "%s.yaml" % mainIn
            # CREATE default with all vars
            writeYaml(defaultVar, mainIn)
            account_replace(file_defaults, str(acctID), str(akey))

        #print(file_tasks)
        # return file_tasks, file_defaults
        return acctID, targetString, acctTitle, True
