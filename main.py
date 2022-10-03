#!/usr/bin/env python
# coding: utf-8


import concurrent.futures as cf
import logging
import re
import csv
from getpass import getpass


from netmiko import ConnectHandler
from netmiko import NetMikoAuthenticationException, NetMikoTimeoutException

# In[252]:


logging.basicConfig(filename="test.log", level=logging.DEBUG)
logger = logging.getLogger("netmiko")

# In[190]:

#just some mock output strings for testing:
mock_dir = '''  Idx  Attr     Size(Byte)  Date        Time       FileName                     
    6  -rw-        309,740  Aug 28 2017 23:13:02   CE5855EI-V200R001SPH009.PAT  
    7  -rw-    123,663,708  Oct 13 2017 23:14:00   CE5855EI-V200R002C50SPC800.cc
    8  -rw-        626,594  Nov 15 2017 20:35:42   CE5855EI-V200R002SPH006.PAT  
    9  -rw-      1,200,034  Jul 17 2018 15:47:32   CE5855EI-V200R002SPH015.PAT  
   10  -rw-      1,404,763  Nov 22 2018 09:00:15   CE5855EI-V200R002SPH017.PAT  
   11  -rw-      2,682,715  May 30 2019 03:20:04   CE5855EI-V200R002SPH020.PAT  
   12  -rw-      3,256,155  Jan 19 2020 23:39:45   CE5855EI-V200R002SPH026.PAT  
   13  -rw-    132,847,324  Nov 01 2021 00:29:46   CE5855EI-V200R019C10SPC800.cc
   14  -rw-      1,810,389  Nov 01 2021 00:29:53   CE5855EI-V200R019SPH010.PAT  
   15  -rw-      3,268,565  Nov 17 2021 00:18:41   CE5855EI-V200R019SPH015.PAT  
'''
mock_patch = '''Patch Package Name    :sd1:/CE5855EI-V200R019SPH015.PAT
Patch Package Version :V200R019SPH015
Patch Package State   :Running   
Patch Package Run Time:2021-11-17 00:19:17+03:00
'''
mock_startup = ''' MainBoard:
  Configured startup system software:        flash:/CE5855EI-V200R019C10SPC800.cc
  Startup system software:                   flash:/CE5856EI-V200R019C10SPC800.cc
  Next startup system software:              flash:/CE5857EI-V200R019C10SPC800.cc
  Startup saved-configuration file:          flash:/vrpcfg.zip
  Next startup saved-configuration file:     flash:/vrpcfg.zip
  Startup paf file:                          default
  Next startup paf file:                     default
  Startup patch package:                     flash:/CE5858EI-V200R019SPH015.PAT
  Next startup patch package:                flash:/CE5859EI-V200R019SPH015.PAT
  '''
mock_startup2 = ''' MainBoard:
  Configured startup system software:        flash:/CE5855EI-V200R019C10SPC800.cc
  Startup system software:                   flash:/CE5856EI-V200R019C10SPC800.cc
  Next startup system software:              flash:/CE5857EI-V200R019C10SPC800.cc
  Startup saved-configuration file:          flash:/vrpcfg.zip
  Next startup saved-configuration file:     flash:/vrpcfg.zip
  Startup paf file:                          default
  Next startup paf file:                     default
  Startup patch package:                     NULL
  Next startup patch package:                NONE
  '''

# In[242]:


def getStartupSoftware(vtyraw_disstartup):
    '''
    Takes raw input of "display startup" command as a string.
    Returns dictionary of corresponding filenames as:
    sss - Startup system software filename;
    nsss - Next startup system software filename;
    spp - Startup patch package filename;
    nspp - Next startup patch package filename.

    '''

    # regexp for catching the "startup system software,..." string with capturing group of a filename, excluding path:
    sss_regexp = "Startup system software:\s+(?:flash|sd1?|sdcard):/((?:CE|AR|S|NE)\w*-V[0-9]{3}R[0-9]{3}(?:C\d\d?)?SPC[0-9]{3}\.cc)"
    nsss_regexp = "Next startup system software:\s+(?:flash|sd1?|sdcard):/((?:CE|AR|S|NE)\w*-V[0-9]{3}R[0-9]{3}(?:C\d\d?)?SPC[0-9]{3}\.cc)"
    spp_regexp = "Startup patch package:\s+(?:(?:flash|sd1?|sdcard):/((?:CE|AR|S|NE)\w*-V[0-9]{3}R[0-9]{3}SPH[0-9]{3}\.PAT)|NONE|NULL)"
    nspp_regexp = "Next startup patch package:\s+(?:(?:flash|sd1?|sdcard):/((?:CE|AR|S|NE)\w*-V[0-9]{3}R[0-9]{3}SPH[0-9]{3}\.PAT)|NONE|NULL)"
#TODO: modify regexp for patch to match devices with no active patch
    ss_dict = dict(zip(["sss", "nsss", "spp", "nspp"], [re.findall(sss_regexp, vtyraw_disstartup)[0],
                                                        re.findall(nsss_regexp, vtyraw_disstartup)[0],
                                                        re.findall(spp_regexp, vtyraw_disstartup)[0],
                                                        re.findall(nspp_regexp, vtyraw_disstartup)[0]]))
    return (ss_dict)


def getFsDir(vtyraw_dir):
    '''
    Parameters:
    raw output of "dir flash:/" command as a string.
    Returns:
    List of corresponding filenames *.PAT|*.cc:

    '''

    regexpr = "(CE|AR|S|NE)\w*-V[0-9]{3}R[0-9]{3}(C\d\d?)?SP[CH][0-9]{3}\.(PAT|cc)"
    dir_list = [x.group() for x in re.finditer(regexpr, vtyraw_dir, flags=re.IGNORECASE)]
    return (dir_list)


# In[267]:






def peerConnectWorker(host):
    device_dict = {
        "host": host,
        "username": "e.volodin@dc",
        "password": gpwd,
        "device_type": "huawei",
        "conn_timeout": 15,
        'global_delay_factor': 0.1
    }
    try:
        with ConnectHandler(**device_dict) as net_connect:
            banner = net_connect.find_prompt()
            print("connected to device with <banner>: ", banner)
            output_dir = net_connect.send_command("dir | i PAT|cc")
            output_disstartup = net_connect.send_command("dis startup")

            del_result = net_connect.send_command("del /unreserved /quiet flash:/logfile/*")
            print(del_result)
            #output_aaa = net_connect.send_command("aaa")
            #print(output_aaa)
            #output_laupp = net_connect.send_command("local-aaa-user password policy administrator")
            #print(output_laupp)
            #output_upao = net_connect.send_command("undo password alert original")
            #print(output_upao)



            # init SW lists:
            junk_list = []
            proper_list = []
            for item in getFsDir(output_dir):  # iterate via actual dir list:
                if item not in getStartupSoftware(
                        output_disstartup).values():  # if list item is not currently used cc.PAT - move to trash list
                    junk_list.append(item)
                    print(f'software file {item} on {banner} is unused!')
                else:
                    proper_list.append(item)  # if not - put it in the "nice"  list
                    print(f'software file {item} on {banner} is being used as startup or next startup')

            # delete all files in junk list:
            for item in range(len(junk_list)):
             print(f'attempting to delete file from {banner}:')
             result = net_connect.send_command("delete /unreserved /quiet "+junk_list[item])
             print (result)
    except NetMikoTimeoutException:
        print(f'\nConn to {host} timed out!')
        return(None,None)
    except NetMikoAuthenticationException:
        print(f'\nAuthentication failed for {host}')
        return (None,None)
    return (junk_list,proper_list)

def getHostsCsv(fn):
    with open(fn) as fh:
        csv_reader = csv.DictReader(fh)
def getHostsNewlines(fn):
    with open(fn) as fh:
        ip_addrs = fh.read().splitlines()
    return(ip_addrs)



if __name__ == '__main__':
    gpwd = print(getpass('type your pass:'))
    hosts = getHostsNewlines('ips.txt') #you can either use CSV parser or just iterate through a regular test file. Just comment out depending on what u need
    #hosts = ["10.9.33.166", "10.6.33.161"]
    with cf.ThreadPoolExecutor() as exe:
        results = exe.map(peerConnectWorker, hosts)
    print(results)
