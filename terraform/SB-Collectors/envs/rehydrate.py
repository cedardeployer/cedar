import os
import sys

import awsconnect
from awsconnect import awsConnect

dir_path = os.path.dirname(os.path.realpath(__file__))


class TerraHydrate():
    origin = None

    def __init__(self, directory):
        pass

    def Define(self, type_in, svc_in, origin, global_accts, sendto, config, triggers=None, targetAPI=None, fullUpdate=None):
        accID = origin['account']
        region = origin['region']
        accountRole = global_accts[accID]['role']
        print(" ## USING ## %s--> %s, role %s, account originDefinition %s, config %s, copyAnsible to %s" %
              (type_in, svc_in, accountRole, accID, config, sendto))
        print(" !!! !! to assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVR.yaml' to True or False as needed")
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        print(" ________________-")
        print("         %s" % (accID))
        print(" ________________-")
        aconnect = awsConnect(accID, origin['eID'], origin['role_definer'], sts_client, region)
        aconnect.connect()

        # #.  IMPORT will happen after a write for each environment
        # IMPORT should occur before deploying in each environment....
        # REMOVE ALL ASSETS NOT RELEVANT... OTHERWISE DELETION OCCURS


        # provider "aws" {
        #   assume_role {
        #     role_arn     = "arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME"
        #     session_name = "SESSION_NAME"
        #     external_id  = "EXTERNAL_ID"
        #   }
        # }

        # TODO: build out a list of resources that need to be refreshed based
        # on the default vars/locals file
        # LOOP ALL and create the import commands for each with correct targets
        # #  terraform import module._s3.aws_s3_bucket.d delete-me-again002
        # #  #####.
        # PULL FILES FOR the correct environment replacing existing when needed.
        # from './env' to '.'

    def refresh(self):
        pass

    def refreshInvoke(self, command, newPath='../'):
        prevPath = dir_path
        os.chdir(newPath)
        roleFile = command
        print(roleFile)
        print(" ----- STARTING --------[%s][%s]" % (roleFile, newPath))

        # args = ['ansible-playbook', '-i', 'windows-servers', quotedRole, '-vvvv']
        args = [command]
        msg = ""
        commandIn = " ".join(args)
        try:
            print(commandIn)
            rawOut = check_output(commandIn, stderr=PIPE, shell=True).decode()
            # rawOut = check_output(args, stderr=PIPE).decode()
            # rawOut = check_output(args, stderr=PIPE, shell=True).decode()
            if isinstance(rawOut, str):
                output = rawOut
            else:
                output = rawOut.decode("utf-8")
            msg = output
        except Exception as e:
            msg = "[E] error occured target:%s  file:%s error:%s" % (newPath, roleFile, e)
            print(msg)
        print(" ----- COMPLETED --------[%s][%s]" % (roleFile, newPath))

        os.chdir(prevPath)




if __name__ == "__main__":
    th = TerraHydrate()
    th.refresh()


if old:
    # if __name__ == "__main__":

    found = None
    length = 0
    tot = len(sys.argv) - 1
    SkipDefinition = False
    type_in = str(sys.argv[1]).strip()
    if 'help' in type_in:
        print(" ************************************************************")
        print("      Try using the following PSUEDO after *CONFIG.yaml is correct :")
        print('           python rehydrate.py -L dev "test" * ENVR.yaml API_Name true')
        print(
            "         -[NOTE]-->  the above will describe 'dev' and then deploy ALL * to 'test,stage' ")
        print(
            "         -[NOTE]-->  the above will describe 'dev' and then deploy to 'test,stage' ")
        print(
            "         -[NOTE]-->  the above can also deploy API only using -G , CloudFront using -CF, DynamoDB using -DY  ")
        print(
            '           python rehydrate.py -G dev "test,stage" activities[*] ENVR.yaml API_Name true')
        print(
            "         -[NOTE]-->  the above will describe activities api with all methods * ")
        print(
            '           python rehydrate.py -G dev "test,stage" *[*] ENVR.yaml API_Name true')
        print('           python rehydrate.py -G dev "test,stage" API_Name ENVR.yaml API_Name true')
        print(
            "         -[NOTE]-->  the above will deploy all API under API_Name... both rolename(API_Name) and targetAPI MUST be SAME  ")
        print("         OR to deploy without Defining ")
        print("         -[NOTE]-->  the above will deploy to stage,test ")
        print(" ************************************************************")
        exit()

    targetAPI = fullUpdate = target_environments = None
    if tot < 6:
        missing = 6 - tot
        totTypeIn = len(type_in)
        msg = "[E] %s arguments missing... found:%s needs 6+ arguments" % (
            missing, tot)
        if "-" in type_in and totTypeIn < 4:
            example = "... for example: \n   python rehydrate.py -L dev 'test,stage' Quickboks_temp ENVR.yaml"
            msg = "%s %s" % (msg, example)
            raise Exception(msg)
        elif totTypeIn > 4:
            SkipDefinition = True
    if not SkipDefinition:
        source_environment = str(sys.argv[2]).strip()
        target_environments = str(sys.argv[3]).strip().split(",")
        role = str(sys.argv[4]).strip()
        config = str(sys.argv[5]).strip()  # ENVR.yaml
        if '/' in str(sys.argv[6]):
            sendto = str(sys.argv[6]).strip()  # 'some path'
        else:
            sendto = os.path.join('../../ansible/roles')
            sys.argv.append(sys.argv[7])
            sys.argv[7] = sys.argv[6]
        roleString = roleCleaner(role)
        if not "roles/" in sendto:
            sendto = "%s/%s" % (sendto, roleString)
        # targetAPI = str(sys.argv[7]).strip()   ### API_Name
        if len(sys.argv) > 7:
            targetAPI = str(sys.argv[7]).strip()
            print(sys.argv[7])
            if targetAPI.lower() == "none" or targetAPI.lower() == "null" or targetAPI == "*":
                targetAPI = None
        # fullUpdate = str(sys.argv[8]).strip()   ### true
        if tot > 8:
            fullUpdate = str(sys.argv[8]).strip().lower()  # true
            if fullUpdate == "none" or fullUpdate == "null" or fullUpdate == "false":
                fullUpdate = False
            else:
                fullUpdate = True
    else:
        target_environments = type_in.split(",")
        role = str(sys.argv[2]).strip()
        config = str(sys.argv[3]).strip()

    start_time = time.time()

    fullpath = "%s/%s" % (dir_path, config)
    origin, global_accts = loadConfig(fullpath, source_environment)

    origin = config_updateRestricted(dir_path, origin)  # going to previous dir
    global_accts = config_updateRestricted(dir_path, global_accts)  # going to previous dir

    triggers = origin['triggers']
    if triggers is None:
        raise ValueError(
            "[E] config file [ %s ] did not load correctly.. PLEASE check / fix and try again" % (fullpath))
    th = TerraHydrate()
    ready = None

    if not SkipDefinition:
        acctID, target, acctTitle, ready = th.Define(type_in, role, origin, global_accts, sendto, config, triggers, targetAPI, fullUpdate)
        print("-[DEFINED]-- %s seconds ---" % (time.time() - start_time))
        # BELOW to skip deployment

    # print(global_accts)

    #print (target_environments)
    # //logger.info("Finished")

    print("--[FIN]- %s seconds ---" % (time.time() - start_time))
