#!/usr/bin/env python3

from moduls.elog import logme
import configparser
import re
import time
import sys
import os
import ipaddress
from requests import get
import socket
import random
import string


def countme(Section, Item, Count, ECFG):

    z = configparser.RawConfigParser()
    z.read(ECFG["homedir"] + os.sep + "ews.idx")

    if z.has_section(Section) is not True:
        z.add_section(Section)

    if z.has_option(Section, Item) is not True:
        z.set(Section, Item, 0)

    if Count >= 0:
        z.set(Section, Item, Count)
    elif Count == -2:
        z.set(Section, Item, str(int(z.get(Section, Item)) + 1))
    elif Count == -3:
        z.set(Section, Item, 0)

    with open(ECFG["homedir"] + os.sep + "ews.idx", 'w') as countfile:
        z.write(countfile)
        countfile.close

    if Count == -1:
        return(z.get(Section, Item))

    return


def calcminmax(MODUL, imin, imax, ECFG):

    if (imax - imin) > int(ECFG["sendlimit"]):
        logme(MODUL, "Need to send : " + str(imax - imin) + " limit is : " + str(ECFG["sendlimit"]) + ". Adapting to limit!", ("P1"), ECFG)
        imax = imin + int(ECFG["sendlimit"])

    return(imin, imax)


def timestamp():
    now = time.time()
    localtime = time.localtime(now)
    milliseconds = '%03d' % int((now - int(now)) * 1000)
    return time.strftime('%Y%m%dT%H%M%ST', localtime) + milliseconds


def ip4or6(ip):

    if re.match("^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", ip):
        return("4")
    else:
        return("6")


def readcfg(MODUL, ITEMS, FILE):

    RC = {}

    config = configparser.SafeConfigParser(os.environ)
    config.read(FILE)

    for items in ITEMS:
        if config.has_option(MODUL, items) is True and len(config.get(MODUL, items)) > 0:
            RC[items] = config.get(MODUL, items)
        else:
            print((" => [ERROR] Config parameter [%s] '%s=' didn't find or empty in %s config file. Abort !" % (MODUL, items, FILE)))
            sys.exit()

    if "ip" in RC:
        RC["ipv"] = ip4or6(RC["ip"])

    return RC


def readonecfg(MODUL, item, FILE):

    config = configparser.SafeConfigParser(os.environ)
    config.read(FILE)

    if config.has_option(MODUL, item) is True and len(config.get(MODUL, item)) > 0:
        return config.get(MODUL, item)
    elif config.has_option(MODUL, item) is True and len(config.get(MODUL, item)) == 0:
        return "NULL"
    elif config.has_option(MODUL, item) is False:
        return "FALSE"
    else:
        return "UNKNOW"


def checkForPublicIP(ip):
    return ipaddress.ip_address(ip).is_global


def getOwnExternalIP(MODUL, ECFG):
    """  try from env variable """
    try:
        if os.environ.get('MY_EXTIP') is not None:
            if ipaddress.ip_address(str(os.environ.get('MY_EXTIP'))).is_global:
                return os.environ.get('MY_EXTIP')
            else:
                logme(MODUL, "[ERROR] Environment variable MY_EXTIP is not a public IP", ("P1", "LOG"), ECFG)
        else:
            logme(MODUL, "[INFO] Environment variable MY_EXTIP not set", ("P1", "LOG"), ECFG)
    except:
        logme(MODUL, "[ERROR] Environment variable MY_EXTIP contains no IP address", ("P1", "LOG"), ECFG)

    """ try ews.ip file """
    ewsip = ECFG["path"] + os.sep + "ews.ip"

    if os.path.isfile(ewsip):
        pubipfile = readonecfg("MAIN", "ip", ewsip)
        if pubipfile.lower() == "null" or pubipfile.lower() == "false" or pubipfile.lower() == "unknown":
            logme(MODUL, "[ERROR] ews.ip contained no ip section or empty value for ip. ", ("P1","LOG"), ECFG)
        else:
            try:
                if ipaddress.ip_address(str(pubipfile)).is_global:
                    return pubipfile
                else:
                    logme(MODUL, "[ERROR] IP address in ews.ip is not a public IP", ("P1", "LOG"), ECFG)
            except:
                logme(MODUL, "[ERROR] ews.ip contains no IP address", ("P1", "LOG"), ECFG)

    """ try the IP from ews.cfg """
    configip = readonecfg(MODUL, "ip", ECFG["cfgfile"])
    try:
        if ipaddress.ip_address(str(configip)).is_global:
            return(configip)
        else:
            logme(MODUL, "[ERROR] IP address in ews.cfg is not a public IP", ("P1", "LOG"), ECFG)
    except:
        logme(MODUL, "[ERROR]] ews.cfg contains no IP address", ("P1", "LOG"), ECFG)

    """ try from public service """
    try:
        extip = get('https://api.ipify.org', timeout=5).text
        if ipaddress.ip_address(str(extip)).is_global:
            return extip
        else:
            logme(MODUL, "[ERROR] IP address returned from external service is not a public IP, this should never happen...", ("P1", "LOG"), ECFG)
    except:
        logme(MODUL, "[ERROR] Could not determine a valid public IP using external service", ("P1", "LOG"), ECFG)

    return(False)


def getHostname(MODUL, ECFG):
    """ get Hostname from ENV/SOCKET/RANDOM """
    if os.environ.get('MY_HOSTNAME') is not None:
        return(os.environ.get('MY_HOSTNAME'))
    elif socket.gethostname() is not None:
        return(socket.gethostname())
    else:
        return("host-".join(random.choice(string.ascii_lowercase) for i in range(16)))


def getOwnInternalIP(MODUL, ECFG):
    """ try MY_INTIP from ENV """
    try:
        if os.environ.get('MY_INTIP') is not None:
            if ipaddress.ip_address(str(os.environ.get('MY_INTIP'))).is_private:
                return(os.environ.get('MY_INTIP'))
            else:
                logme(MODUL, "[ERROR] Could not determine a valid private IP using 0.0.0.0", ("P1", "LOG"), ECFG)
                return("0.0.0.0")
    except:
        logme(MODUL, "[ERROR] Could not determine a valid private IP using 0.0.0.0", ("P1", "LOG"), ECFG)
        return("0.0.0.0")


def resolveHost(host):
    """ resolve an IP, either from IP or hostname """
    try:
        return(ipaddress.IPv4Address(host))
    except:
        if ipaddress.IPv4Address(socket.gethostbyname(host)):
            return(socket.gethostbyname(host))
        else:
            return(False)


if __name__ == "__main__":
    pass
