
import json
import yaml
import copy
from collections import abc

import hcl

dd = {"name": "joe", "info": {"age": [5, 12, 42], "gender": {"type": "male"}, "accidents": [{"name": "Thursday"}, {"height": "six 2"}, {"color": "blue", "eyes": "brown"}]}, 'status': 'ACTIVE', 'streamspec': {'StreamEnabled': True, 'StreamViewType': 'NEW_AND_OLD_IMAGES'}, 'write_capacity': 1}
# dd = {'sb_permissions': {'dynamodbs': [{'arn': 'arn:aws:dynamodb:us-east-1:814235745176:table/sb_permissions', 'indexes': [{'hash_key_name': 'PK', 'hash_key_type': 'STRING'}, {'type': 'global_all'}, {'hash_key_name': 'PK', 'hash_key_type': 'STRING'}, {'hash_key_name': 'PK'}], 'streamspec': {'StreamEnabled': True,
                                                                                                                                                                                                                                                                                                    # 'StreamViewType': 'NEW_AND_OLD_IMAGES'}, 'write_capacity': 1}], 'eid': '/91NZ0U', 'env': 'xx-PRODUCTION', 'error_path': '~/Ansible_Deployer', 'region': 'us-east-1', 'role_duration': 3600, 'skipping': {'methods': False, 'models': False, 'options': False, 'resources': False, 'stage': False}}}
dd = {'sb_permissions': {'dynamodbs': [{'arn': 'dddddddd', 'streamspec': {'StreamEnabled': True, 'StreamViewType': 'NEW_AND_OLD_IMAGES'}, 'write_capacity': 1}], 'eid': '///Ro9'}}


class json2hcl:
    def __init__(self):
        pass

    def loads(self, value):
        return hcl.loads(value)

    def dumps(self, nested):
        nn = copy.deepcopy(nested)
        txt = ""
        prevKey = ""
        spaces = "    "
        braces = []
        insideBrace = []
        # wasInsideBrace = False
        # insideCount = 0
        prevObj = None
        prevInsideSetKey = None
        for parentKeyString, key, value, parentObj in self.nested_dict_iter(nn):
            ppKey = parentKeyString
            mkey = key
            mspc = ""
            braceEND = ""
            if isinstance(parentObj, list):
                print("....list END")

            bname, btype = self.brace_last_isArray(braces)
            isArray = False
            if bname and btype in 'array' and bname in parentKeyString.rsplit(",", 1)[0]:
                print (f"~~~~~~~~ is Array  {bname}   {key}    pkey:{parentKeyString}   pObj:{parentObj}")
                isArray = True
            insideSet = False
            if len(parentObj.keys()) > 1 and isArray and len(parentKeyString.split(",")) > 1:
                insideSet = True
                print("~~== INSIDE    SEt %s" % (insideSet))

            insidesetKEY = None
            if prevObj:
                if isArray:
                    if insideSet:
                        insidesetKEY = parentKeyString.rsplit(",", 1)[0] + "_insideset"
                        if insidesetKEY not in insideBrace:
                            print(f" MMMM>>>>{insidesetKEY}")
                            insideBrace.append(insidesetKEY)
                            mkey = " r{ " + key
                    elif prevInsideSetKey in insideBrace and insidesetKEY not in insideBrace:
                        insideBrace.remove(prevInsideSetKey)
                        txt = txt + "}r,"
                elif prevInsideSetKey and not insidesetKEY:
                    if prevInsideSetKey in insideBrace:
                        insideBrace.remove(prevInsideSetKey)
                        txt = txt + "}m"
                print(f" BBBM>>{prevInsideSetKey}>>>{insidesetKEY}>>> {key}  prevKey: {prevKey}  pKey: {parentKeyString}  insideBrc:{insideBrace}")

            simpleObj = False
            if isinstance(parentObj, abc.Mapping) and (isinstance(value, (int, float)) or isinstance(value, (str))):
                simpleObj = True

            if "," in ppKey:
                appKey = ppKey.split(",")
                mspc = "".join([spaces for spc in appKey])
                ppKey = appKey[0]

            penKey = prevKey.rsplit(",", 1)[0]
            isBrace, brace = self.brace_nearest(penKey, braces)
            if (parentKeyString.rsplit(",", 1)[0] not in prevKey.rsplit(",", 1)[0]) and (prevKey.rsplit(",", 1)[0] not in parentKeyString.rsplit(",", 1)[0]):
                print(f"*   ****** {parentKeyString}   prevKey: {prevKey}  brace:{braces}  {penKey}")
            elif isBrace:
                if brace['name'] not in parentKeyString:
                    print("______c______")
                else:
                    isBrace = None
                print(f".      NOT  {prevKey}       {parentKeyString}  {brace}")

            if isBrace:
                if txt.strip()[-1] == ',':  # CLEANUP EXTRA COMMAS befor Brace
                    txt = txt[:-1]
                btype = "}z" if isBrace in 'dict' else "]z"
                if isBrace in ('dict', 'array'):
                    txt = txt + f"\n{mspc}" + f" {btype}"
                print(f" D  U  D  E ... found  {btype}")
                braces.remove(brace)

            if simpleObj and isArray and not insideSet:
                mkey = "q{" + key
                braceEND = "}q,"
            if ppKey in prevKey:
                txt = txt + f"\n{mspc}{mkey} = "
            else:
                if txt:
                    txt = txt + f"\n{mspc}{mkey}="
                else:
                    txt = txt + f"{mspc}{mkey}="
            if isinstance(value, list):
                if not self.list_isSimple(value):
                    print("list")
                    txt = txt + "p["
                    braces.append({"name": parentKeyString, "type": "array"})
                    print(f"--a->{parentKeyString}")
                    print(" __            ADD A")
            elif isinstance(value, abc.Mapping):
                print("map")
                txt = txt + "z{"
                braces.append({"name": parentKeyString, "type": "dict"})
                print(f"--b->{parentKeyString}")
                print(" __            ADD B")
            txt_value = self.resolve_valueInType(value)
            if txt_value:
                txt = txt + txt_value + f' {braceEND}'

            # if isArray and not insideSet:
            #     txt = txt + "},"

            print(f"--::[{isBrace}]-- -- - -- -- -- -- --{key}--BEGIN")
            print(f"--[{parentKeyString}] -==>>>>{value}     {parentObj}")
            print(f"---------------------- -- -- ----END")
            prevKey = parentKeyString
            prevObj = parentObj
            prevInsideSetKey = insidesetKEY

        if braces:
            txt = txt + "\n"
            braces.reverse()
        for brace in braces:
            if brace['type'] == "array":
                txt = txt + "]"
            elif brace['type'] == "dict":
                txt = txt + "}"
        return txt

    # this guarntees tree is read from the TOP -->DOWN

    def nested_dict_iter(self, nested, parentKey=None):
        pObj = nested
        lastKey = None
        for key, value in nested.items():
            ppkey = "%s,%s" % (parentKey, key)
            if parentKey is None:
                ppkey = key
            # print("    iter.... now---> %s" % (key))
            yield ppkey, key, value, pObj
            if isinstance(value, abc.Mapping):
                yield from self.nested_dict_iter(value, ppkey)
            if isinstance(value, list):
                if isinstance(value[0], abc.Mapping):
                    for vv in value:
                        yield from self.nested_dict_iter(vv, ppkey)

    def brace_nearest(self, key, braces):
        for brace in braces:
            if key in brace['name']:
                return brace['type'], brace
        return None, None

    def brace_last_isArray(self, braces):
        if braces:
            last = braces[-1]
            return last['name'], last['type']
        return None, None

    def resolve_valueInType(self, value):
        txt = ""
        if isinstance(value, str):
            txt = txt + f'"{value}"'
        elif isinstance(value, bool):
            vbool = 'true' if value else 'false'
            txt = txt + f'{vbool}'
        elif isinstance(value, (int, float)):
            txt = txt + f'{value}'
        elif isinstance(value, list):
            isSimple = True
            items = []
            for iv in value:
                if not isinstance(iv, (str, bool, int, float)):
                    isSimple = False
                    break
                items.append(self.resolve_valueInType(iv))
            if isSimple:
                txt = "[" + ",".join(items) + "]"

        return txt

    def list_isSimple(self, value):
        isSimple = True
        for iv in value:
            if not isinstance(iv, (str, bool, int, float)):
                isSimple = False
                break
        return isSimple

    def cleanResult(self, value):
        dy = value
        dy = dy.replace("z{", "{")
        dy = dy.replace("p[", "[")
        dy = dy.replace("z[", "[")
        dy = dy.replace("q{", "{")
        dy = dy.replace("r{", "{")
        dy = dy.replace("}z", "}")
        dy = dy.replace("]z", "]")
        dy = dy.replace("}m", "}")
        dy = dy.replace("}q", "}")
        dy = dy.replace("}r", "}")
        return dy


if __name__ == '__main__':
    jcl = json2hcl()


    # dy = jcl.dumps(dd)
    test = True

    print("____________________________________________")
    print("____________________________________________")
    print("_____________HCL ORIGINAL____________")
    print("____________________________________________")
    print("____________________________________________")
    isFile = False
    filename = "main.yaml"
    if isFile:
        with open(filename, 'r') as stream:
            dd = yaml.load(stream, Loader=yaml.FullLoader)

    # print(dd)
    # raise
    dy = jcl.dumps(dd)

    final_hcl = jcl.cleanResult(dy)
    if test:
        # final_hcl = dy
        print(dy)
        print(" ====================== CLEAN")
        print(final_hcl)
        # exit()
        jsonAgain = jcl.loads(final_hcl)
        print("____________________________________________")
        print("____________________________________________")
        print("_____________back to JSON____________")
        print("____________________________________________")
        print("____________________________________________")
        print(jsonAgain)
