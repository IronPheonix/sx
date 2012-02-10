#!/usr/bin/env python
"""
This class will evalatuate a cluster and create a report that will
link in known issues with links to resolution.

@author    :  Shane Bradley
@contact   :  sbradley@redhat.com
@version   :  2.08
@copyright :  GPLv2
"""
import re
import os.path
import logging
import textwrap

import sx
from sx.tools import StringUtil
from sx.logwriter import LogWriter
from sx.plugins.lib.clusterha.clusterhaconfanalyzer import ClusterHAConfAnalyzer
from sx.plugins.lib.clusterha.clusternode import ClusterNode
from sx.plugins.lib.clusterha.clusternode import ClusterNodeNetworkMap
from sx.plugins.lib.clusterha.clusternode import ClusterStorageFilesystem


class ClusterEvaluator():
    def __init__(self, cnc):
        self.__cnc = cnc
        # Seperator between sections:
        self.__seperator = "------------------------------------------------------------------"

    def getClusterNodes(self):
        return self.__cnc

    # #######################################################################
    # Evaluate function
    # #######################################################################
    def __evaluateClusterGlobalConfiguration(self, cca):
        rString = ""
        if (cca.isCleanStartEnabled()):
            description =  "The clean_start option in the /etc/cluster/cluster.conf was enabled and is not supported "
            description += "for production clusters. The option is for testing and debugging only."
            urls = ["https://access.redhat.com/kb/docs/DOC-61417"]
            rString += StringUtil.formatBulletString(description, urls)

        # Disable the post_join_delay check for now
        #if (not int(cca.getPostJoinDelay()) > 3):
        #    description =  "The post_join_delay option was 3 (which is the default value) in the /etc/cluster/cluster.conf file. "
        #    description += "In some cluster environments a value of 3 for post_join_delayis to too low."
        #    urls = ["https://access.redhat.com/kb/docs/DOC-52756", "https://access.redhat.com/kb/docs/DOC-3642"]
        #    rString += StringUtil.formatBulletString(description, urls)
        if (not (int(cca.getPostFailDelay()) == 0)):
            description =  "The post_fail_delay option in the /etc/cluster/cluster.conf file was not zero(default). "
            description += "Most clusters should not modifiy the default value of zero."
            urls = ["https://access.redhat.com/kb/docs/DOC-3642", "https://access.redhat.com/kb/docs/DOC-5931"]
            rString += StringUtil.formatBulletString(description, urls)
        # Check for single node configurations and clusters that are larger than 16 nodes.
        clusterNodeCount = len(cca.getClusterNodeNames())
        if (clusterNodeCount == 1):
            description =  "This is a single node cluster and does not meet the minimum number of cluster nodes required for "
            description += "high-availibility. Red Hat recommends that clusters always have a minimum of two nodes to protect "
            description += "against hardware failures."
            urls = ["https://access.redhat.com/kb/docs/DOC-5893"]
            rString += StringUtil.formatBulletString(description, urls)
        elif (clusterNodeCount > 16):
            descriptioin = "The maximum number of cluster nodes supported by the High Availability Add-On is 16, and the same "
            description += "is true for the Resilient Storage Add-On that includes GFS2 and CLVM. This cluster currently has "
            description += "%d number of cluster nodes which exceeds the supported 16 number of cluster nodes." %(clusterNodeCount)
            urls = ["https://access.redhat.com/kb/docs/DOC-40821"]
            rString += StringUtil.formatBulletString(description, urls)
        return rString

    def __evaluateClusterNodeHeartbeatNetwork(self, hbNetworkMap):
        rString = ""
        # ###################################################################
        # Check if bonding is being used on the heartbeat network
        # ###################################################################
        if ((hbNetworkMap.isBondedMasterInterface()) and (not hbNetworkMap.getBondedModeNumber() == "1")):
            # The currently only supported mode for RHEL
            # clustering heartbeat network is mode
            # 1(Active-backup)
            description =  "The only supported bonding mode on the heartbeat network is mode 1(active-backup)."
            description += "The heartbeat network(%s) is currently using bonding mode %s(%s).\n" %(hbNetworkMap.getInterface(),
                                                                                                   hbNetworkMap.getBondedModeNumber(),
                                                                                                   hbNetworkMap.getBondedModeName())
            urls = ["https://access.redhat.com/kb/docs/DOC-59572"]
            rString += StringUtil.formatBulletString(description, urls)
        # ###################################################################
        # Check if heartbeat network interface is netxen or bnx2 network module
        # ###################################################################
        if (hbNetworkMap.getNetworkInterfaceModule().strip() == "bnx2"):
            description =  "The network interface %s that the cluster communication is using is on a network device that " %(hbNetworkMap.getInterface())
            description += "is using the module: %s. This module has had known issues with network communication." %(hbNetworkMap.getNetworkInterfaceModule())
            urls = []
            rString += StringUtil.formatBulletString(description, urls)
        elif ((hbNetworkMap.getNetworkInterfaceModule().strip() == "netxen") or
              (hbNetworkMap.getNetworkInterfaceModule().strip() == "nx_nic")):
            description =  "The network interface %s that the cluster is using for communication is using the module: %s. " %(hbNetworkMap.getInterface(),
                                                                                                                                  hbNetworkMap.getNetworkInterfaceModule())
            description += "This module has had known issues with network communication."
            urls = ["https://access.redhat.com/kb/docs/DOC-57187",
                    "https://access.redhat.com/kb/docs/DOC-44972",
                    "https://access.redhat.com/kb/docs/DOC-54254",
                    "https://access.redhat.com/kb/docs/DOC-44972"]
            rString += StringUtil.formatBulletString(description, urls)
        elif (hbNetworkMap.isBondedMasterInterface()):
            # Loop over the bonded interfaces
            for bondedSlaveInterface in hbNetworkMap.getBondedSlaveInterfaces():
                description =  "The network interface that the cluster is using for communication is using the module: %s." %(bondedSlaveInterface.getNetworkInterfaceModule())
                description += "This network interface is a slave interface(%s) that is part of the bond: %s." %(bondedSlaveInterface.getInterface(),
                                                                                                                 hbNetworkMap.getInterface())
                description += "This module has had known issues with network communication. Here are a couple articles that may or may not be related:"

                if (bondedSlaveInterface.getNetworkInterfaceModule().strip() == "bnx2"):
                    urls = []
                    rString += StringUtil.formatBulletString(description, urls)
                elif ((bondedSlaveInterface.getNetworkInterfaceModule().strip() == "netxen") or
                      (bondedSlaveInterface.getNetworkInterfaceModule().strip() == "nx_nic")):
                    urls = ["https://access.redhat.com/kb/docs/DOC-57187",
                            "https://access.redhat.com/kb/docs/DOC-44972",
                            "https://access.redhat.com/kb/docs/DOC-54254",
                            "https://access.redhat.com/kb/docs/DOC-44972"]
                    rString += StringUtil.formatBulletString(description, urls)
        return rString

    def __evaluateClusterNodeFencing(self, cca, clusternode):
        rString = ""
        cnp = clusternode.getClusterNodeProperties()
        fenceDevicesList = cnp.getFenceDevicesList()
        if (len(fenceDevicesList) > 0):
            # Check if acpi is disabled if sys mgmt card is fence device
            smFenceDevicesList = ["fence_bladecenter", "fence_drac", "fence_drac5", "fence_ilo",
                                  "fence_ilo_mp", "fence_ipmi", "fence_ipmilan", "fence_rsa"]

            cnFenceDeviceList = cca.getClusterNodeFenceDevicesList(clusternode.getClusterNodeName())
            for fd in cnFenceDeviceList:
                if ((fd.getAgent() in smFenceDevicesList) and (not clusternode.isAcpiDisabledinRunlevel())):
                    description = "The service \"acpid\" is not disabled on all runlevels(0 - 6). " + \
                        "This service should be disabled since a system management fence device(%s) "%(fd.getAgent()) + \
                        "was detected. If acpid is enabled the fencing operation may not work as intended."
                    urls = ["https://access.redhat.com/kb/docs/DOC-5415"]
                    rString += StringUtil.formatBulletString(description, urls)
                    break;
            # Check if fence_manual is enabled on a node
            if (cca.isFenceDeviceAgentEnabledOnClusterNode(clusternode.getClusterNodeName(), "fence_manual")):
                description = "The fence device \"fence_manual\" is defined as a fence agent for this node which is an unsupported fencing method."
                urls = ["https://access.redhat.com/kb/docs/DOC-43212"]
                rString += StringUtil.formatBulletString(description, urls)
        else:
            description = "There was no fence device defined for the clusternode. A fence device is required for each clusternode."
            urls = ["https://access.redhat.com/kb/docs/DOC-62219"]
            rString += StringUtil.formatBulletString(description, urls)
        return rString

    def __evaluateServiceIsEnabled(self, clusternode, serviceName):
        rString = ""
        for chkConfigItem in clusternode.getChkConfigList():
            if (chkConfigItem.getName() == serviceName):
                if(chkConfigItem.isEnabledRunlevel3()):
                    rString += "3 "
                if(chkConfigItem.isEnabledRunlevel4()):
                    rString += "4 "
                if(chkConfigItem.isEnabledRunlevel5()):
                    rString += "5 "
        return rString

    def __isNFSChildOfClusterStorageResource(self, cca, csFilesystem):
        # Just need to find 1 match. If clusterstorage fs has 1 nfs child then
        # requires localflocks to be enabled.
        clusteredServices = cca.getClusteredServices()
        for clusteredService in clusteredServices:
            resourcesInFlatList = clusteredService.getFlatListOfClusterResources()
            clusterfsResource = None
            for resource in resourcesInFlatList:
                if ((resource.getType() == "clusterfs") and (len(resource.getAttribute("device")) > 0)):
                    if (csFilesystem.getDeviceName() == resource.getAttribute("device")):
                        # Found Match for the filesystem
                        clusterfsResource = resource
                elif (not clusterfsResource == None):
                    # Since the clusterfsResource is not None then next resource
                    # should be nfs export. If not then either no nfs export or
                    # not configured correctly cause nfsexport uses inhertiance
                    # to get fs to use. Break out of loop after this condition
                    # is checked.
                    if ((resource.getLevel() == (clusterfsResource.getLevel() + 1)) and (resource.getType() == "nfsexport")):
                        return True
        return False

    def __evaluateClusterStorage(self, cca):
        # Is active/active nfs supported? Sorta
        # urls = ["https://access.redhat.com/kb/docs/DOC-60255"]
        rString = ""
        for clusternode in self.__cnc.getClusterNodes():
            clusterNodeEvalString = ""
            if (not clusternode.isClusterNode()):
                continue
            # ###################################################################
            # Distro Specific evaluations
            # ###################################################################
            # The distro release of this node
            distroRelease = clusternode.getDistroRelease()
            if ((distroRelease.getDistroName() == "RHEL") and (distroRelease.getMajorVersion() == 5)):
                # Check if GFS2 module should be removed on RH5 nodes
                if (self.__cnc.doesGFS2ModuleNeedRemoval(clusternode.getUnameA(), clusternode.getClusterModulePackagesVersion())) :
                    description = "The kmod-gfs2 is installed on a running kernel >= 2.6.18-128. This module should be removed since the module is included in the kernel."
                    urls = ["https://access.redhat.com/kb/docs/DOC-54965"]
                    clusterNodeEvalString += StringUtil.formatBulletString(description, urls)

            # ###################################################################
            # Analyze the Clustered Storage
            # ###################################################################
            listOfClusterStorageFilesystems = clusternode.getClusterStorageFilesystemList()

            stringUtil = StringUtil()
            # Check to see if the GFS/GFS2 fs has certain mount options enabled.
            fsTable = []
            for csFilesystem in listOfClusterStorageFilesystems:
                csFilesystemOptions = csFilesystem.getMountOptions()
                if(not (csFilesystemOptions.find("noatime") >= 0) or
                   (not csFilesystemOptions.find("nodiratime") >= 0)):
                    fsTable.append([csFilesystem.getDeviceName(), csFilesystem.getMountPoint()])
            if (len(fsTable) > 0):
                tableHeader = ["device_name", "mount_point"]
                description =  "The following GFS/GFS2 file-systems did not have the mount option noatime or nodiratime set. "
                description += "Unless atime support is essential, Red Hat recommends setting the mount option \"noatime\" and "
                description += "\"nodiratime\" on every GFS/GFS2 mount point. This will significantly improve performance since "
                description += "it prevents reads from turning into writes."
                tableOfStrings = stringUtil.toTableStringsList(fsTable, tableHeader)
                urls = ["https://access.redhat.com/kb/docs/DOC-41485"]
                clusterNodeEvalString += StringUtil.formatBulletString(description, urls, tableOfStrings)

            # Check to see if they are exporting a gfs/gfs2 fs via samba and nfs.
            tableHeader = ["device_name", "mount_point", "nfs_mp", "smb_mp"]
            fsTable = []
            for csFilesystem in listOfClusterStorageFilesystems:
                # There are 4 ways of mounting gfs via nfs/smb at same time that
                # needs to be checked:

                # 1) nfs mount via /etc/exports  and smb mount via /etc/samba/smb.conf
                # 2) nfs mount via /etc/cluster/cluster.conf and smb mount via /etc/cluster/cluster.conf
                # 3) nfs mount via /etc/cluster/cluster.conf and smb mount via /etc/samba/smb.conf.
                # 4) nfs mount via /etc/exports and smb mount via /etc/cluster/cluster.conf
                if (csFilesystem.isEtcExportMount() and csFilesystem.isSMBSectionMount()):
                    # 1) nfs mount via /etc/exports  and smb mount via /etc/samba/smb.conf
                    #print "1: %s" %(csFilesystem.getMountPoint())
                    nfsMP = csFilesystem.getEtcExportMount().getMountPoint()
                    smbSectionList = csFilesystem.getSMBSectionMountList()
                    if (len(smbSectionList) > 0):
                        smbMP = smbSectionList.pop().getOptionValue("path").strip()
                        fsTable.append([csFilesystem.getDeviceName(), csFilesystem.getMountPoint(), "%s(EN)" %(nfsMP), "%s(ES)" %(smbMP)])
                        for smbSection in smbSectionList:
                            smbMP = smbSection.getOptionValue("path").strip()
                            fsTable.append(["", "", "", "%s(ES)" %(smbMP)])
                elif ((not csFilesystem.isEtcExportMount()) and (not csFilesystem.isSMBSectionMount())):
                    # 2) nfs mount via /etc/cluster/cluster.conf and smb mount via /etc/cluster/cluster.conf
                    #print "2: %s" %(csFilesystem.getMountPoint())
                    if((self.__isNFSChildOfClusterStorageResource(cca, csFilesystem)) and
                       (len(csFilesystem.getClusteredSMBNames()) > 0)):
                        nfsMP = csFilesystem.getMountPoint()
                        smbPaths = []
                        for name in csFilesystem.getClusteredSMBNames():
                            for smbSection in csFilesystem.getClusteredSMBSectionList(name):
                                currentPath = smbSection.getOptionValue("path").strip()
                                if (len(currentPath) > 0):
                                    smbPaths.append(currentPath)
                        if ((len(nfsMP) > 0) and (len(smbPaths) > 0)):
                            # Pop the first one off the list.
                            smbMP = smbPaths.pop()
                            fsTable.append([csFilesystem.getDeviceName(), csFilesystem.getMountPoint(), "%s(CN)" %(nfsMP), "%s(CS)" %(smbMP)])
                            # IF there any left add those with some blanks.
                            for smbMP in smbPaths:
                                fsTable.append(["", "", "", "%s(CS)" %(smbMP)])
                elif ((csFilesystem.isSMBSectionMount()) and (self.__isNFSChildOfClusterStorageResource(cca, csFilesystem))):
                    # 3) nfs mount via /etc/cluster/cluster.conf and smb mount via /etc/samba/smb.conf.
                    #print "3: %s" %(csFilesystem.getMountPoint())
                    nfsMP = csFilesystem.getMountPoint()
                    smbSectionList = csFilesystem.getSMBSectionMountList()
                    if (len(smbSectionList) > 0):
                        smbMP = smbSectionList.pop().getOptionValue("path").strip()
                        fsTable.append([csFilesystem.getDeviceName(), csFilesystem.getMountPoint(), "%s(CN)" %(nfsMP), "%s(ES)" %(smbMP)])
                        for smbSection in smbSectionList:
                            smbMP = smbSection.getOptionValue("path").strip()
                            fsTable.append(["", "", "", "%s(ES)" %(smbMP)])
                elif ((csFilesystem.isEtcExportMount()) and (len(csFilesystem.getClusteredSMBNames()) > 0)):
                    # 4) nfs mount via /etc/exports and smb mount via /etc/cluster/cluster.conf
                    # print "4: %s" %(csFilesystem.getMountPoint())
                    smbSectionList = []
                    for name in csFilesystem.getClusteredSMBNames():
                        smbSectionList += csFilesystem.getClusteredSMBSectionList(name)
                    if (len(smbSectionList) > 0):
                        smbMP = smbSectionList.pop().getOptionValue("path").strip()
                        fsTable.append([csFilesystem.getDeviceName(), csFilesystem.getMountPoint(), "%s(EN)" %(nfsMP), "%s(CS)" %(smbMP)])
                        for smbSection in smbSectionList:
                            smbMP = smbSection.getOptionValue("path").strip()
                            fsTable.append(["", "", "", "%s(CS)" %(smbMP)])
            # Write the table if it is not empty.
            if (len(fsTable) > 0):
                description =  "The following GFS/GFS2 filesystem(s) are being exported by NFS and SMB(samba) which is unsupported. "
                description += "Where the mount point was found will be noted:                                                      "
                description += "nfs export via /etc/exports (EN)                                       "
                description += "nfs export via /etc/cluster/cluster.conf (CN)                          "
                description += "samba export via /etc/exports for samba (ES)                           "
                description += "samba export via /etc/cluster/cluster.conf for samba (CS)"
                tableOfStrings = stringUtil.toTableStringsList(fsTable, tableHeader)
                urls = ["https://access.redhat.com/kb/docs/DOC-60253"]
                clusterNodeEvalString += StringUtil.formatBulletString(description, urls, tableOfStrings)

            # Check for localflocks if they are exporting nfs.
            fsTable = []
            for csFilesystem in listOfClusterStorageFilesystems:
                if (csFilesystem.isEtcExportMount()):
                    csFilesystemOptions = csFilesystem.getMountOptions()
                    if (csFilesystem.isFilesysMount()):
                        csFilesystemOptions = "%s %s" %(csFilesystemOptions, csFilesystem.getFilesysMount().getMountOptions())
                    if (csFilesystem.isEtcFstabMount()):
                        csFilesystemOptions = "%s %s" %(csFilesystemOptions, csFilesystem.getEtcFstabMount().getMountOptions())
                    if (csFilesystem.isClusterConfMount()):
                        csFilesystemOptions = "%s %s" %(csFilesystemOptions, csFilesystem.getClusterConfMount().getMountOptions())
                    # Check if localflock is enabled.
                    if (not csFilesystemOptions.find("localflocks") >=0):
                        fsTable.append([csFilesystem.getDeviceName(), csFilesystem.getMountPoint()])
                elif(csFilesystem.isClusterConfMount()):
                    # Since we know it is not in /etc/exports but is in
                    # cluster.conf then we need to see if there is a service
                    # where it has child resource of nfsexports.
                    if(self.__isNFSChildOfClusterStorageResource(cca, csFilesystem)):
                        csFilesystemOptions = csFilesystem.getClusterConfMount().getMountOptions()
                        if (not csFilesystemOptions.find("localflocks") >=0):
                            fsTable.append([csFilesystem.getDeviceName(), csFilesystem.getMountPoint()])

            if (len(fsTable) > 0):
                tableHeader = ["device_name", "mount_point"]
                description = "Any GFS/GFS2 filesystem that is exported with nfs should have the option \"localflocks\" set."
                description += "The following GFS/GFS2 filesystem do not have the option set."
                tableOfStrings = stringUtil.toTableStringsList(fsTable, tableHeader)
                urls = ["https://access.redhat.com/kb/docs/DOC-59118", "http://docs.redhat.com/docs/en-US/Red_Hat_Enterprise_Linux/5/html-single/Configuration_Example_-_NFS_Over_GFS/index.html#locking_considerations"]
                clusterNodeEvalString += StringUtil.formatBulletString(description, urls, tableOfStrings)
            # ###################################################################
            # Add to string with the hostname and header if needed.
            # ###################################################################
            if (len(clusterNodeEvalString) > 0):
                if (not len(rString) > 0):
                    sectionHeader = "%s\nCluster Storage Configuration Known Issues\n%s" %(self.__seperator, self.__seperator)
                    rString += "%s\n%s(Cluster Node ID: %s):\n%s\n\n" %(sectionHeader, clusternode.getClusterNodeName(), clusternode.getClusterNodeID(), clusterNodeEvalString.rstrip())
                    sectionHeaderAdded = True
                else:
                    rString += "%s(Cluster Node ID: %s):\n%s\n\n" %(clusternode.getClusterNodeName(), clusternode.getClusterNodeID(), clusterNodeEvalString.rstrip())
        # Return the string
        return rString

    def evaluate(self):
        """
         * If two node cluster, check if hb and fence on same network. warn qdisk required if not or fence delay.
         """
        # Return string for evaluation.
        rstring = ""
        # Nodes that are in cluster.conf, so should have report of all these
        baseClusterNode = self.__cnc.getBaseClusterNode()
        if (baseClusterNode == None):
            # Should never occur since node count should be checked first.
            return ""
        cca = ClusterHAConfAnalyzer(baseClusterNode.getPathToClusterConf())
        # ###################################################################
        # Check global configuration issues:
        # ###################################################################
        clusterConfigString = ""
        if (not cca.isClusterConfFilesIdentical(self.__cnc.getPathToClusterConfFiles())):
            description = "The /etc/cluster/cluster.conf file was not identical on all the cluster nodes."
            urls = ["https://access.redhat.com/kb/docs/DOC-65315"]
            clusterConfigString += StringUtil.formatBulletString(description, urls)
        clusterConfigString += self.__evaluateClusterGlobalConfiguration(cca)
        if (len(clusterConfigString) > 0):
            sectionHeader = "%s\nCluster Global Configuration Known Issues\n%s" %(self.__seperator, self.__seperator)
            rstring += "%s\n%s:\n%s\n" %(sectionHeader, cca.getClusterName(), clusterConfigString)

        # ###################################################################
        # Check cluster nodes configuration
        # ###################################################################
        # Will be set to true if a node has a string was added to evaluation string.
        sectionHeaderAdded = False
        for clusternode in self.__cnc.getClusterNodes():
            clusterNodeEvalString = ""
            if (not clusternode.isClusterNode()):
                continue

            # Check if this is using Open Shared root
            if (clusternode.isOpenSharedRootClusterNode()):
                description = "This is an openshared-root cluster node. This is a special cluster using 3rd party rpms that is only supported on RHEL4."
                urls = ["http://www.open-sharedroot.org/"]
                clusterNodeEvalString += StringUtil.formatBulletString(description, urls)

            # Checking all clusternode names in /etc/hosts
            if (not self.__cnc.isClusterNodeNamesInHostsFile(cca.getClusterNodeNames(), clusternode.getNetworkMaps().getListOfNetworkMaps())) :
                description = "The clusternode names were not all defined in the /etc/hosts file."
                urls = ["https://access.redhat.com/kb/docs/DOC-5935"]
                clusterNodeEvalString += StringUtil.formatBulletString(description, urls)

            # Check the networking configuration of the cluster node's
            # heartbeat network.
            hbNetworkMap = clusternode.getHeartbeatNetworkMap()
            result = self.__evaluateClusterNodeHeartbeatNetwork(hbNetworkMap)
            if (len(result) > 0):
                clusterNodeEvalString += result

            # Fencing checks
            result = self.__evaluateClusterNodeFencing(cca, clusternode)
            if (len(result) > 0):
                clusterNodeEvalString += result
            # ###################################################################
            # Distro specfic evaluations
            # ###################################################################
            # The distro release of this node
            distroRelease = clusternode.getDistroRelease()
            # RHEL5 and greater checks
            cnp = clusternode.getClusterNodeProperties()
            if ((distroRelease.getDistroName() == "RHEL") and (distroRelease.getMajorVersion() >= 5)):
                # Make sure that multicast tags are not on clusternode stanzas
                if (((len(cnp.getMulticastAddress()) > 0) or (len(cnp.getMulticastInterface()) > 0))) :
                    description = "The multicast tags should not be in the <clusternodes> stanzas. These tags are no longer supported in RHEL5."
                    urls = ["https://access.redhat.com/kb/docs/DOC-59392"]
                    clusterNodeEvalString += StringUtil.formatBulletString(description, urls)


            # ###################################################################
            # RHEL 5 Specific Checks
            # ###################################################################
            if ((distroRelease.getDistroName() == "RHEL") and (distroRelease.getMajorVersion() == 5)):
                # Check if the service openais is enabled because it should be disabled if this is a cluster node.
                serviceName = "openais"
                serviceRunlevelEnabledString = self.__evaluateServiceIsEnabled(clusternode, serviceName)
                if (len(serviceRunlevelEnabledString) > 0):
                    description =  "The service %s should be disabled if the host is part of a cluster since the service cman starts the service %s." %(serviceName, serviceName)
                    description += "The following runlevels have %s enabled: %s." %(serviceName, serviceRunlevelEnabledString.strip())
                    urls = ["https://access.redhat.com/kb/docs/DOC-5899"]
                    clusterNodeEvalString += StringUtil.formatBulletString(description, urls)

                # Check if scsi_reserve service is enabled with no scsi fencing device in cluster.conf
                serviceName = "scsi_reserve"
                if (not cca.isFenceDeviceAgentEnabledOnClusterNode(clusternode.getClusterNodeName(), "fence_scsi")):
                    serviceRunlevelEnabledString = self.__evaluateServiceIsEnabled(clusternode, serviceName)
                    if (len(serviceRunlevelEnabledString) > 0):
                        description =  "The service %s should be disabled since there was no fence_scsi device detected for this node." %(serviceName)
                        description += "The following runlevels have %s enabled: %s." %(serviceName, serviceRunlevelEnabledString.strip())
                        urls = ["https://access.redhat.com/kb/docs/DOC-47503", "https://access.redhat.com/kb/docs/DOC-17809"]
                        clusterNodeEvalString += StringUtil.formatBulletString(description, urls)

            # ###################################################################
            # RHEL6 specific
            # ###################################################################
            if ((distroRelease.getDistroName() == "RHEL") and (distroRelease.getMajorVersion() == 6)):
                # Check if the service corosync is enabled because it should be disabled if this is a cluster node.
                serviceName = "corosync"
                serviceRunlevelEnabledString = self.__evaluateServiceIsEnabled(clusternode, serviceName)
                if (len(serviceRunlevelEnabledString) > 0):
                    description =  "The service %s should be disabled if the host is part of a cluster since the service cman starts the service %s." %(serviceName, serviceName)
                    description += "The following runlevels have %s enabled: %s." %(serviceName, serviceRunlevelEnabledString.strip())
                    urls = ["https://access.redhat.com/kb/docs/DOC-5899"]
                    clusterNodeEvalString += StringUtil.formatBulletString(description, urls)
            # ###################################################################
            if (len(clusterNodeEvalString) > 0):
                if (not sectionHeaderAdded):
                    sectionHeader = "%s\nCluster Node Configuration Known Issues\n%s" %(self.__seperator, self.__seperator)
                    rstring += "%s\n%s(Cluster Node ID: %s):\n%s\n\n" %(sectionHeader, clusternode.getClusterNodeName(), clusternode.getClusterNodeID(), clusterNodeEvalString.rstrip())
                    sectionHeaderAdded = True
                else:
                    rstring += "%s(Cluster Node ID: %s):\n%s\n\n" %(clusternode.getClusterNodeName(), clusternode.getClusterNodeID(), clusterNodeEvalString.rstrip())

        # ###################################################################
        # Evaluate the Cluster Storage
        # ###################################################################
        resultString = self.__evaluateClusterStorage(cca)
        if (len(resultString) > 0):
            rstring += resultString
        # ###################################################################
        # return string
        return rstring

