
import json
# import yaml
import copy
from collections import abc

# https://github.com/astro44/py2hcl/blob/main/py2hcl.py
# import hcl
# Author: rcolvin
# use at own risk.
from py2hcl import py2hcl
from microUtils import loadYaml
from microUtils import writeTXT



if __name__ == '__main__':
    pcl = py2hcl()
    # fullTest = False
    fullTest = True
    file ="/Users/astro_sk/Documents/TFS/cedar/tools/gentools/ansible/693485195958_PP-Configs/defaults/main_pp-prod.yaml"

    dd = loadYaml(file)

    # dd = {'sb_permissions': {'dynamodbs': [{'arn': 'dddddddd', 'streamspec': {'StreamEnabled': True, 'StreamViewType': 'NEW_AND_OLD_IMAGES'}, 'write_capacity': 1}], 'eid': '///Ro9'}}
    hcl = pcl.dumps(dd)
    target_path = "_hcl_out.tfvars"
    writeTXT(hcl, target_path)

    # print(hcl)