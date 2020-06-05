import logging.config


# Author: ybendre
# Test: generic_vmotion
# This test will perform vmotion/svmotion/xvmotion/xclustervmotion of vm

import json
import os
from pyVmomi import vim
from pyVim.connect import SmartConnect, SmartConnectNoSSL, Disconnect
import atexit
import argparse
import getpass
import time

class Test:


    def __init__(self,testlogger):
        self.logger = testlogger
        self.logger.info('Perform __init__')
        self.param_valid = True
        self.vc=os.getenv("vcenter")
        if self.vc is None:
            self.logger.info("No vCenter provided, please set environment variable vcenter")
            self.param_valid = False
            return
        self.vm = os.getenv("testvm")
        if self.vm is None:
            self.logger.info("No vm name provided, please set environment variable testvm")
            self.param_valid = False
            return None
        self.srchost = None
        self.desthost = os.getenv("testdesthost")
        self.srcdatastore = None
        self.destdatastore = os.getenv("testdestdatastore")
        self.vmotion_type = self.decide_vMotion_Type()
        if self.vmotion_type is None:
            self.logger.info("ERROR: Invalid vMotion type. Please provide at least desthost or destdatastore or both")
            self.param_valid = False
            return None
        self.username = os.getenv("vcuser")
        if self.username is None:
            self.username = "administrator@vsphere.local"

        self.password=os.getenv("vcpassword")
        if self.password is None:
            self.password = "Admin!23"

        self.port = os.getenv("port")
        if self.port is None:
            self.port = "443"
        self.mysession = None
        self.content = None

        # Function to get the vCenter server session

        self.logger.info('Finished  __init__')

    def decide_vMotion_Type(self):
        self.logger.info('Perform decide_vMotion_Type')
        if (self.desthost is not None) and (self.destdatastore is None):
            return "vmotion"

        if (self.desthost is None) and (self.destdatastore is not None):
            return "svmotion"

        if (self.desthost is not None) and (self.destdatastore is not None):
            return "xvmotion"

        return None
        self.logger.info('Finished  decide_vMotion_Type')

    def get_vc_session(self):
        self.logger.info('Perform get_vc_session')
        try:
            si = SmartConnectNoSSL(host=self.vc, user=self.username, pwd=self.password, port=self.port)
            self.mysession = si
        except Exception as e:
            self.logger.error('Failed in get_vc_session: '+str(e))
            self.logger.exception('')
            self.logger.info("Authentication failed")
            self.mysession = None
            return None

        self.logger.info('Finished  get_vc_session')

    def wait_for_task(self, task):
        self.logger.info('Perform wait_for_task')
        """ wait for a vCenter task to finish """
        task_done = False
        success = True
        while not task_done:
            time.sleep(5)
            self.logger.info(task.info)
            if task.info.state == 'success':
                self.logger.info("Task completed successfully")
                success = True
                task_done = True

            if task.info.state == 'error':
                self.logger.info("Task failed")
                self.logger.info(task.info)
                task_done = True
                success = False

        return success

        self.logger.info('Finished  wait_for_task')

    def get_obj(self, vimtype, name):
        self.logger.info('Perform get_obj')
        """
        Return an object by name, if name is None the
        first found object is returned
        """
        obj = None
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, vimtype, True)
        for c in container.view:
            if name:
                if c.name == name:
                    obj = c
                    break
            else:
                obj = c
                break

        return obj

        self.logger.info('Finished  get_obj')

    def collect_template_disks(self, vm):
        self.logger.info('Perform collect_template_disks')
        """
            Internal method to collect template disks
            :param vm: VM object
            :return: list of template disks
        """
        template_disks = []
        for device in vm.config.hardware.device:
            if type(device).__name__ == "vim.vm.device.VirtualDisk":
                datastore = device.backing.datastore
                self.logger.info("device.deviceInfo.summary:" + device.deviceInfo.summary)
                self.logger.info("datastore.summary.type:" + datastore.summary.type)
                if hasattr(device.backing, 'fileName'):
                    disk_desc = str(device.backing.fileName)
                    self.logger.info("Disc Discription -- {}".format(disk_desc))
                    drive = disk_desc.split("]")[0].replace("[", "")
                    self.logger.info("drive:" + drive)
                    self.logger.info("device.backing.fileName:" + device.backing.fileName)
                    template_disks.append(device)
        return template_disks

        self.logger.info('Finished  collect_template_disks')

    def construct_locator(self, template_disks, datastore_dest_id):
        self.logger.info('Perform construct_locator')
        """
            Internal method to construct locator for the disks
            :param template_disks: list of template_disks
            :param datastore_dest_id: ID of destination datastore
            :return: locator
        """
        ds_disk = []
        for index, wdisk in enumerate(template_disks):
            self.logger.info("relocate index:" + str(index))
            self.logger.info("disk:" + str(wdisk))
            disk_desc = str(wdisk.backing.fileName)
            drive = disk_desc.split("]")[0].replace("[", "")
            self.logger.info("drive:" + drive)
            self.logger.info("wdisk.backing.fileName:" + wdisk.backing.fileName)
            locator = vim.vm.RelocateSpec.DiskLocator()
            locator.diskBackingInfo = wdisk.backing
            locator.diskId = int(wdisk.key)
            locator.datastore = datastore_dest_id
            ds_disk.append(locator)
        return ds_disk

        self.logger.info('Finished  construct_locator')

    def relocate_vm(self, vm_name, host_dest, datastore_dest):
        self.logger.info('Perform relocate_vm')
        try:
            vm = self.get_obj([vim.VirtualMachine], vm_name)
            self.srchost = vm.runtime.host.name
            if self.desthost is None:
                self.desthost = self.srchost
            self.srcdatastore = vm.datastore[0].info.name
            # Create Relocate Spec
            spec = vim.VirtualMachineRelocateSpec()
            # Find destination host
            destination_host = self.get_obj([vim.HostSystem], host_dest)
            spec.host = destination_host

            # Find destination Resource pool
            resource_pool = destination_host.parent.resourcePool
            spec.pool = resource_pool

            # collect disks belong to the VM
            template_disks = self.collect_template_disks(vm)
            datastore_dest_id = self.get_obj([vim.Datastore], datastore_dest)
            spec.datastore = datastore_dest_id
            spec.disk = self.construct_locator(template_disks, datastore_dest_id)

            task = vm.RelocateVM_Task(spec)
            return (self.wait_for_task(task))
        except Exception as e:
            self.logger.error('Failed in relocate_vm: '+str(e))
            self.logger.exception('')
            return False


        self.logger.info('Finished  relocate_vm')

    def vmotion_vm(self, vm_name, dest_host):
        self.logger.info('Perform vmotion_vm')
        self.logger.info("Search VM to be vmotioned "+vm_name)
        vm = self.get_obj([vim.VirtualMachine], vm_name)
        self.srchost = vm.runtime.host.name
        self.logger.info("VM Found")
        self.logger.info("Search dest host "+dest_host)
        destination_host = self.get_obj([vim.HostSystem], dest_host)
        self.logger.info("Dest host found")
        resource_pool = vm.resourcePool

        migrate_priority = vim.VirtualMachine.MovePriority.defaultPriority

        msg = "Migrating %s to destination host %s" % (vm_name, dest_host)
        self.logger.info(msg)

        # Live Migration :: Change host only
        task = vm.Migrate(pool=resource_pool, host=destination_host, priority=migrate_priority)
        self.wait_for_task(task)

        self.logger.info('Finished  vmotion_vm')

    def testSetup(self):
        self.logger.info('Perform testSetup')
        if self.param_valid:
            self.get_vc_session()
            self.content = self.mysession.RetrieveContent()
            return True
        else:
            self.logger.info("Invalid test paramaeters")
            return False

        self.logger.info('Finished  testSetup')

    def testTask(self):
        self.logger.info('Perform testTask')
        test_status = True
        if self.vmotion_type == 'vmotion':
            test_status = self.vmotion_vm(self.vm, self.desthost)
            if test_status:
                test_status = self.vmotion_vm(self.vm, self.srchost)
            return test_status

        else:
            test_status = self.relocate_vm(self.vm, self.desthost, self.destdatastore)
            if test_status:
                test_status = self.relocate_vm(self.vm, self.srchost, self.srcdatastore)
        return test_status

        self.logger.info('Finished  testTask')

    def testCleanup(self):
        self.logger.info('Perform testCleanup')
        pass

