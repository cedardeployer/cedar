# This code is used to create Ansible files for deploying Lambda's
# all that is needed is a target Lambda, tests, and it will do the rest.
# finds associate roles and policies
# creates Ansible modules based on those policies and roles
# defines the Lambdas and creates them with tests
# finds api-gateways or other events
# if api found defines the security needed. creates modules for deployment with templates
import re
#import ValueError
import os
import time
import random
from time import sleep
from datetime import datetime, date
import json
import shutil
import boto3
from botocore.exceptions import ClientError
import sys
from shutil import copyfile
import fileinput
import logging
import urllib

import distutils
from distutils import dir_util

import awsconnect

from awsconnect import awsConnect


from microUtils import writeYaml, writeJSON, account_replace, loadServicesMap, loadConfig, ansibleSetup
from microUtils import describe_role

# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(os.path.realpath(__file__))


class ApiGatewayMolder():
    origin = None

    temp = None

    def Cooker(self, target):
        lambda_describe(target)

    def __init__(self, directory, islambda=False):
        global dir_path
        if not islambda:
            temp = "%s/%s" % (dir_path, directory)
        else:
            temp = '/tmp'
        self.temp = temp
        if not os.path.exists(temp):
            os.makedirs(temp)
        else:
            print (" directory %s already exists... remove or change name." % temp)

#############################################
######   [ USAGE PLAN KEYs ]#################
#############################################
#############################################
    def describe_apiKey(self, client, apiKey, position=None):
        rlist = []  # client.get_api_key(apiKey='9j5xhi7ene')
        if position is None:
            response = client.get_api_key(apiKey=apiKey, limit=500)
        else:
            response = client.get_api_key(apiKey=apiKey, position=position, limit=500)
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
            response = client.get_usage_plan_keys(usagePlanId=usagePlanID, limit=500)
        else:
            response = client.get_usage_plan_keys(usagePlanId=usagePlanID, position=position, limit=500)
        temp = response['items']
        baseList = self.keysMapAPI(client, temp)
        if "position" in response:
            rlist = self.describe_planKey(client, usagePlanID, response['position'])
        keys = baseList + rlist
        return keys

    def describe_apiUsage(self, client, restApiId, position=None):
        rlist = []
        if position is None:
            response = client.get_usage_plans(keyId=restApiId, limit=500)
        else:
            response = client.get_usage_plans(keyId=restApiId, position=position, limit=500)
        baseList = response['items']
        if "position" in response:
            rlist = self.describe_apiUsage(client, restApiId, response['position'])
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
            response = client.get_authorizers(restApiId=restApiId, position=position, limit=500)
        baseList = response['items']
        if "position" in response:
            rlist = self.describe_Allmodels(client, restApiId, response['position'])
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
            response = client.get_models(restApiId=restApiId, position=position, limit=500)
        baseList = response['items']
        if "position" in response:
            rlist = self.describe_Allmodels(client, restApiId, response['position'])
        models = baseList + rlist
        return models

    def get_attrModel(self, client, target, restApiId, init=False):
        rawSchema = client.get_model(restApiId=restApiId, modelName=target, flatten=True)['schema']

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
                    return{'type': mType, 'items': value['items']}
            elif len(v) > 1 and type(v) is dict:
                print(v)  # 'type': 'object', 'additionalProperties': {'$ref': '#/definitions/address'}}
                oType = v['type']
                # if 'items' in v:
                for oK, oV in v.items():
                    if 'type' in oK:
                        continue
                    #itemKey = oK
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
            #response = client.get_model( restApiId='8qabpn6aa4', modelName='claim', flatten=True )['schema']
        # print("--------COMPLETED----------")
        # print("   ----------------------")
        # print("      ----------------")
        # print(mapped)
        return mapped

    def describe_models(self, client, restApiId, name, models):
        model_list = self.describe_Allmodels(client, restApiId)
        print("START")
        print(restApiId)
        basic = []
        advanced = []
        advTemp = []

        models.update({'basic': basic, 'dependant': advanced})
        basicNames = []
        for model in model_list:
            rawSchema = model['schema'].replace(restApiId, "%s_id" % (name))  # gets converted in real time
            #model['schema']=model['schema'].replace("\n", "" ).replace( "\\", "" )
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
        print(advanced)
        print("-------000b-----~~~----~~~----~~~")
        # print(models)
        # print("--------001----~~~----~~~----~~~")
        #raise ValueError('A very specific bad thing happened.')
        return models

    def describeRefs(self, key, value):
        refs = []
        if 'type' in key:
            return None
        if isinstance(value, (list, tuple, dict)):
            # print("%s:%s"%(key, value))
            if '$ref' in value:
                refs.append(value['$ref'])
            else:
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
                            print(" --: continue %s" % (rName))
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
                                        array.insert(i, atemp)  # Item now just before reference
                                        if 'client' in mname and 'clients' in IName:
                                            print(i)
                                            print(num)
                                            print(model)
                                            print("### client &*&*&*&****&&&&&")
                                            # raise
        if additionali > 0:
            print("    Additions found... rerunning")
            self.relocRefsOnDependencies(array, basicNames)
        return array

##################################################
#######  ABOVE REPOSITION ########################
######   BASED ON DEPENDENCIES  ##################
##################################################

    def put_models(self, client, models):
        modelsAdded = []
        for model in models:
            #current= client.get_model(restApiId=restApiId,modelName=modelName)
            # if model.name == current.modelName:
                # delete model first
            modelName = model.name
            try:
                response = client.delete_model(restApiId=model.restApiId, modelName=modelName)
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
            #current= client.get_model(restApiId=restApiId,modelName=modelName)
            # if model.name == current.modelName:
                # delete model first
            modelName = model.name
            try:
                response = client.delete_model(restApiId=model.restApiId, modelName=modelName)
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
        #client = aconnect.__get_client__('apigateway')
        #client = boto3.client('apigateway')
        usage = client.get_usage_plans()['items']
        for use in usage:
            for stage in use['apiStages']:
                if apiID in stage['apiId']:
                    stageLabel = stage['stage']
                    apiStage = "%s_%s" % (apiName, stageLabel)
                    if apiStage in stages:
                        continue
                    stages.update({apiStage: {'stage': stageLabel, 'api': apiName, 'state': 'present'}})
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

        # get api, resource, method, integration and responses, models
    def describe_gateway(self, resourceNname, resourceType, aconnect, resourceRole=None, targetAPI=None):

        client = aconnect.__get_client__('apigateway')
        #client = boto3.client('apigateway')
        # apis=client.get_rest_apis()
        apis = self.getAll_rest_apis(client)
        integratedAPIs = []
        stages = {}
        models = {}
        auths = []
        addedResource = {}
        possibleOptions = {}
        print ("*********************************************************************")

        print ("                  API GATEWAY                                              ")
        print ("*********************************************************************")
        print (apis)

        print ("*********************************************************************")
        print (targetAPI)

        # for api in apis['items']:
        for api in apis:
            id = api['id']
            name = api['name']
            if targetAPI is not None:
                if name.lower() != targetAPI.lower():
                    continue

            #resources = client.get_resources( restApiId=id,limit=500)
            resources = self.getAllResources(client, id)

            # api id, stage id.
            stages = self.describe_stages(client, id, name, stages)
            models = self.describe_models(client, id, name, models)
            auths = self.describe_authorizers(client, id, name, auths)

            print ("                            API GATEWAY       resources                                       ")
            print ("     resources    %s     " % resources)
            # for rest in resources['items']:
            methodCallMax = 4
            methodCalls = 0
            for rest in resources:
                path = rest['path']
                mId = rest['id']
                parentId = None
                if 'parentId' in rest:
                    parentId = rest['parentId']
                if not 'resourceMethods' in rest:
                    parent = rest
                    continue
                for key, value in rest['resourceMethods'].items():
                    tempResourceRole = resourceRole

            # ONLY FOR TESTINNG
                    # if not 'GET' in key:
                    #     continue
            # DELETE ABOVE !!!!!!!!!

                    print ("      *API*     ")
                    print ("   @#@#. 002. #@#@ %s %s  client.get_method(restApiId=%s,resourceId=%s,httpMethod=%s)" % (name, path, id, mId, key))
                    integrated = None
                    mInfo = value
                    print (value)
                    # try:
                    #     integrated = client.get_integration(restApiId=id, resourceId=mId, httpMethod=key)
                    #     del integrated['ResponseMetadata']
                    # except ClientError as e:
                    #     print(e.response['Error']['Message'])

                    # print integrated
                    method = client.get_method(restApiId=id, resourceId=mId, httpMethod=key)
                    del method['ResponseMetadata']
                    authType = method['authorizationType']
                    keyRequired = method['apiKeyRequired']
                    integratedType = None
                    if not 'methodIntegration' in method:
                        continue
                    methodCalls = methodCalls + 1
                    if methodCalls > 16:
                        sleep(1)
                        methodCalls = 0
                    methodIntegration = method['methodIntegration']
                    print (" method:")
                    # print (method)
                    print("----====-----====----====----")
                    #method = client.get_method( restApiId='20iv84vxh9',resourceId='i8b9of',httpMethod='GET')
                    # if not 'uri' in methodIntegration:
                    #     # print(".    - -- - 002-- -   ?")
                    #     # print ( methodIntegration )
                    #     continue
                    operationName = rModels = sModels = authName = requestParameters = requestValidator = authScope = None
                    methodResponse = None
                    if 'methodResponses' in method:
                        methodResponse = method['methodResponses']
                        # print("~~~~~1")
                        # print (methodResponse)
                        # print("~~~~~1bb")
                        if '200' in methodResponse:
                            if 'responseModels' in methodResponse['200']:
                                mm = methodResponse['200']['responseModels']
                                sModels = {}
                                for mkey, mvalue in mm.items():
                                    sModels.update({mkey: mvalue})

                    if 'requestModels' in method:
                        sm = method['requestModels']
                        rModels = {}
                        # print("~~~~~2")
                        # print(sm)
                        # print("~~~~~2bb")
                        for rkey, rvalue in sm.items():
                            rModels.update({rkey: rvalue})
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
                        requestValidator = client.get_request_validator(restApiId=id, requestValidatorId=method['requestValidatorId'])
                        del requestValidator['ResponseMetadata']
                    if 'requestParameters' in method:
                        requestParameters = method['requestParameters']
                    if 'authorizerId' in method:
                        auth = client.get_authorizer(restApiId=id, authorizerId=method['authorizerId'])
                        authName = auth['name']
                    if 'authorizationScopes' in method:
                        authScope = method['authorizationScopes']
                    add = False
                    if (resourceType in integration and resourceNname in integration) or resourceNname == "*":
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
                                                       'httpMethod': method['httpMethod'],
                                                       'methodIn': methodIntegration,
                                                       'methodResponse': methodResponse}})
                        # if 'COGNITO' in authType:
                        # print ("  . . .1 . .  ")
                        # print (method)
                        # print ("  . . .2 . .  ")
                    if add:
                        addedResource.update({path: mId})
                        if not 'credentials' in methodIntegration:
                            methodIntegration.update({'credentials': tempResourceRole})
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
                             'httpMethod': method['httpMethod'],
                             'methodIn': methodIntegration,
                             'methodResponse': methodResponse})

        for rK, rV in addedResource.items():  # Ensure OPTIONS picked up for Methods gathered
            if rK in possibleOptions:
                integratedAPIs.append(possibleOptions[rK])
        print ("=====>>>  !!")
        print ("completed!!")
        print ("completed!!")
        print (integratedAPIs)
        #raise ValueError(" stopping now for check...")
        if len(integratedAPIs) == 0:
            return None
        return integratedAPIs, stages, models, auths

    def summary_gateway(self, client, targetAPI):
        apis = self.getAll_rest_apis(client)
        id = None
        for api in apis:
            if targetAPI in api['name']:
                id = api['id']
                break
        if id is None:
            print("[E]  no api tree found with name: %s" % (targetAPI))
            raise
        resources = self.getAllResources(client, id)
        integratedAPIs = {}

        print ("                            API GATEWAY       resources                                       ")
        print ("     resources    %s     " % resources)
        # for rest in resources['items']:
        for rest in resources:
            path = rest['path']
            mId = rest['id']
            if not 'resourceMethods' in rest:
                parent = rest
                continue
            for key, value in rest['resourceMethods'].items():

                # print integrated
                method = client.get_method(restApiId=id, resourceId=mId, httpMethod=key)
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

    def describe_GatewayALL(self, target, aconnect, accountOrigin, accounts=[], types=[], sendto=None, targetAPI=None, isFullUpdate=False):
        print ("describe_GatewayALL")
        # describe_gateway(self, resourceNname, resourceType, aconnect , resourceRole=None,targetAPI=None):
        isFullUpdate = False
        directorysNeeded = False
        skipFiles = True
        # tmp="/tmp"

        self.origin = accountOrigin
        acctID = accountOrigin['account']
        assumeRole = accountOrigin['assume_role']
        # self.origin['account']

        roles, resourceRole = describe_role("CR-Lambda-VPC", aconnect, acctID, True if 'api' in types else False)
        # (target,'lambda', aconnect, resourceRole, targetAPI)
        apis, stages, models, auths = self.describe_gateway('*', '*', aconnect, resourceRole, targetAPI)

        taskMain, rootFolder, targetLabel = ansibleSetup(self.temp, target, isFullUpdate, skipFiles)

        taskMain.append({"import_tasks": "../aws/agw_model.yml project={{ project }}"})
        taskMain.append({"import_tasks": "../aws/_agw.yml project={{ project }}"})

        # ONLY needs two files default definition and tasks
        #############################################
        #############################################
        ######## write YAML to file in tasks  #######
        #############################################
        #############################################
        # rootFolder=tmp
        option = "tasks_main"
        #mainIn = "%s/%s/%s"%(rootFolder,'tasks',option)
        mainIn = "%s/%s" % (rootFolder, option)
        writeYaml(taskMain, mainIn)
        file_tasks = "%s.yaml" % mainIn
        file_defaults = None

        for akey, account in accounts.items():
            # if not account in acctID:
            if not acctID in akey:
                continue
            accDetail = {
                "account_id": akey,
                "env": account['title'],
                "role_duration": 3600,
                "region": "us-east-1",
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
            #print (" A P I. see below. ......===---->>>")
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
                #defaultVar[targetLabel].update({ "api_domains": stage_list })
                #defaultVar[targetLabel].update({ "api_usage": stage_list })

            #option = "defaults_main%s"%account['all']
            option = "defaults_main"
            mainIn = "%s/%s" % (rootFolder, option)
            #mainIn = "%s/%s/%s"%(rootFolder,'defaults',option)
            file_defaults = "%s.yaml" % mainIn
            # CREATE default with all vars
            writeYaml(defaultVar, mainIn)
            account_replace(file_defaults, str(acctID), str(akey))

        if directorysNeeded:
            if not sendto is None:
                print (" .... creating a main.yaml for ansible using dev")
                opt = "main_%s.yaml" % accountOrigin['all']
                src = "%s/%s/%s" % (rootFolder, 'defaults', opt)
                opt2 = "main.yaml"
                dst = "%s/%s/%s" % (rootFolder, 'defaults', opt2)
                copyfile(src, dst)
                print (" -------==------===---- COPY START....")
                print (" sending to %s. from %s" % (sendto, rootFolder))
                distutils.dir_util.copy_tree(rootFolder, sendto)
                print (" -------==------===---- FINAL YAML file....")
                ansibleRoot = sendto.split('roles/')[0]
                targets = ['%s' % target]
                rootYML = [{"name": "micro modler for lambda-%s" % target,
                            "hosts": "dev",
                            "remote_user": "root",
                            "roles": targets}]
                # ansibleRoot
                writeYaml(rootYML, ansibleRoot, target)
        print(file_tasks)
        return file_tasks, file_defaults
